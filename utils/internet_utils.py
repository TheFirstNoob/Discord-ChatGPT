import asyncio
import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Comment as BS4Comment
from typing import Tuple, List, Optional, Callable, Dict, Any, Set
from dataclasses import dataclass
from duckduckgo_search import DDGS
from src.log import logger
from src.locale_manager import locale_manager as lm

# Constants
MAX_RESULTS = 5
REQUEST_TIMEOUT = 15
MAX_PARAGRAPHS = 10
MAX_CHARS = 3000
MAX_HTML_SIZE = 1000 * 1024  # 1 MB
SKIP_HTTP_ERRORS = {403, 404, 410}
RETRY_ATTEMPTS = 3
CONCURRENT_REQUESTS = 5

# HTML Processing
UNWANTED_ELEMENTS = {
    'script', 'style', 'nav', 'footer', 'header', 'aside',
    'noscript', 'iframe', 'button', 'input', 'select', 'textarea', 'form'
}

# Semaphore for concurrent requests
semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

class HTMLTooLargeError(Exception):
    """Raised when HTML content exceeds maximum size limit."""
    pass

@dataclass
class SearchResult:
    """Data class representing a search result."""
    type: str
    url: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchResult':
        """Create a SearchResult instance from a dictionary."""
        return cls(
            type=data['type'],
            url=data.get('url'),
            title=data.get('title'),
            content=data.get('content'),
            error=data.get('error')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert SearchResult instance to a dictionary."""
        return {
            'type': self.type,
            'url': self.url,
            'title': self.title,
            'content': self.content,
            'error': self.error
        }

async def search_web(query: str, request_type: str = "search") -> List[Dict[str, Any]]:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: Search query
        request_type: Type of search (search, images, videos)
    
    Returns:
        List of search results
    """
    try:
        ddgs = DDGS()
        if request_type == 'search':
            logger.info(lm.get('search_web_info').format(query=query))
            results = ddgs.text(
                query,
                max_results=MAX_RESULTS,
                region="wt-wt",
                safesearch="moderate",
                backend="auto"
            )
            return list(results)
        elif request_type == 'images':
            logger.info(lm.get('search_images_info').format(query=query))
            results = ddgs.images(
                query,
                max_results=MAX_RESULTS,
                region="wt-wt",
                safesearch="moderate"
            )
            return [result['image'] for result in results if result.get('image')]
        elif request_type == 'videos':
            logger.info(lm.get('search_videos_info').format(query=query))
            results = ddgs.videos(
                query,
                max_results=MAX_RESULTS,
                region="wt-wt",
                safesearch="moderate"
            )
            return [result['content'] for result in results if result.get('content')]
        return []
    except Exception as e:
        logger.error(lm.get('search_web_error').format(error=e))
        return []

async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    """
    Fetch HTML content from a URL.
    
    Args:
        session: aiohttp ClientSession
        url: URL to fetch
    
    Returns:
        HTML content as string
    
    Raises:
        HTMLTooLargeError: If HTML content exceeds size limit
        aiohttp.ClientError: If HTTP request fails
    """
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
            if response.status in SKIP_HTTP_ERRORS:
                logger.warning(lm.get('fetch_html_skip').format(status=response.status, url=url))
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=lm.get('fetch_html_skip').format(status=response.status, url=url),
                    headers=response.headers
                )
            response.raise_for_status()
            html = await response.text(encoding='utf-8', errors='ignore')
            if len(html) > MAX_HTML_SIZE:
                logger.warning(lm.get('fetch_html_too_large').format(url=url))
                raise HTMLTooLargeError(lm.get('fetch_html_too_large').format(url=url))
            return html
    except aiohttp.ClientError as e:
        logger.error(lm.get('fetch_html_error').format(url=url, error=e))
        raise
    except Exception as e:
        logger.exception(lm.get('fetch_html_unknown_error').format(url=url, error=e))
        raise

def clean_html(soup: BeautifulSoup, unwanted_elements: Set[str]) -> None:
    """
    Remove unwanted elements from HTML.
    
    Args:
        soup: BeautifulSoup object
        unwanted_elements: Set of element tags to remove
    """
    for element in soup.find_all(unwanted_elements):
        element.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, BS4Comment)):
        comment.extract()

def extract_table_data(soup: BeautifulSoup) -> List[List[str]]:
    """
    Extract data from HTML tables.
    
    Args:
        soup: BeautifulSoup object
    
    Returns:
        List of table rows, each containing list of cell values
    """
    table = soup.find('table')
    if not table:
        return []
    return [
        [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
        for row in table.find_all('tr')
    ]

def extract_text(soup: BeautifulSoup) -> List[str]:
    """
    Extract meaningful text from HTML.
    
    Args:
        soup: BeautifulSoup object
    
    Returns:
        List of text elements
    """
    text_elements = []
    
    # Extract headers
    for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        text = header.get_text(strip=True)
        if len(text) > 10:
            text_elements.append(f"### {text}")
    
    # Extract paragraphs and other text elements
    for element in soup.find_all(['p', 'b', 'div']):
        text = element.get_text(strip=True)
        if len(text) > 40:
            text_elements.append(text)
    
    # Extract lists
    for lst in soup.find_all(['ul', 'ol']):
        items = lst.find_all('li')
        list_text = [
            f"• {item.get_text(strip=True)}"
            for item in items
            if len(item.get_text(strip=True)) > 20
        ]
        if list_text:
            text_elements.extend(list_text)
    
    # Extract table data
    table_data = extract_table_data(soup)
    if table_data:
        text_elements.extend(" | ".join(row) for row in table_data)
    
    return list(dict.fromkeys(text_elements))

def summarize_text(text_elements: List[str], max_paragraphs: int, max_chars: int) -> str:
    """
    Summarize text by limiting paragraphs and characters.
    
    Args:
        text_elements: List of text elements
        max_paragraphs: Maximum number of paragraphs
        max_chars: Maximum number of characters
    
    Returns:
        Summarized text
    """
    final_text = []
    chars_count = 0
    
    for element in text_elements:
        if len(final_text) >= max_paragraphs or chars_count >= max_chars:
            break
        final_text.append(element)
        chars_count += len(element)
    
    return '\n\n'.join(final_text)

async def get_website_info(
    session: aiohttp.ClientSession,
    url: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Get website information including title and content.
    
    Args:
        session: aiohttp ClientSession
        url: URL to fetch
    
    Returns:
        Tuple of (title, content)
    """
    async with semaphore:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                html = await fetch_html(session, url)
                soup = BeautifulSoup(html, 'html.parser')
                clean_html(soup, UNWANTED_ELEMENTS)
                
                title = soup.title.text.strip() if soup.title else lm.get('website_no_title')
                text_elements = extract_text(soup)
                paragraphs = summarize_text(text_elements, MAX_PARAGRAPHS, MAX_CHARS)
                
                if not paragraphs:
                    logger.warning(lm.get('get_website_info_no_content').format(url=url))
                    return None, lm.get('website_no_content')
                
                return title, paragraphs
            except (aiohttp.ClientResponseError, HTMLTooLargeError) as e:
                logger.warning(lm.get('get_website_info_skip').format(url=url, error=e))
                return None, lm.get('website_error').format(error=e)
            except aiohttp.ClientError as e:
                logger.warning(lm.get('get_website_info_retry').format(
                    url=url, attempt=attempt + 1, max_attempts=RETRY_ATTEMPTS, error=e
                ))
            except Exception as e:
                logger.exception(lm.get('get_website_info_error').format(url=url, error=e))
                return None, lm.get('website_unknown_error').format(error=e)
            
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(2 ** attempt)
        
        logger.error(lm.get('get_website_info_max_retries').format(url=url))
        return None, lm.get('website_max_retries')

async def prepare_search_results(
    results: List[Dict[str, Any]],
    user_instruction: str = "",
    get_website_info_func: Callable[[aiohttp.ClientSession, str], Tuple[Optional[str], Optional[str]]] = get_website_info,
    cancel_on_error: bool = False
) -> List[Dict[str, Any]]:
    """
    Prepare search results by fetching website information.
    
    Args:
        results: List of search results
        user_instruction: Optional user instruction
        get_website_info_func: Function to get website info
        cancel_on_error: Whether to cancel remaining tasks on error
    
    Returns:
        List of processed search results
    """
    search_results = []
    if user_instruction:
        search_results.append(SearchResult(
            type="instruction",
            content=user_instruction
        ).to_dict())

    valid_results = [result for result in results if result.get('href')]
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            (result, asyncio.create_task(get_website_info_func(session, result.get('href'))))
            for result in valid_results
        ]
        
        if cancel_on_error:
            done, pending = await asyncio.wait(
                [t[1] for t in tasks],
                return_when=asyncio.FIRST_EXCEPTION
            )
            for task in pending:
                task.cancel()
        
        for result, task in tasks:
            try:
                title, paragraphs = await task
            except Exception as e:
                logger.error(lm.get('prepare_search_results_error').format(url=result.get('href'), error=e))
                search_results.append(SearchResult(
                    type="error",
                    url=result.get('href'),
                    error=str(e)
                ).to_dict())
                continue

            if title is None or paragraphs is None:
                search_results.append(SearchResult(
                    type="skipped",
                    url=result.get('href'),
                    title=title,
                    content=paragraphs
                ).to_dict())
            else:
                search_results.append(SearchResult(
                    type="website",
                    url=result.get('href', lm.get('website_no_url')),
                    title=title,
                    content=paragraphs
                ).to_dict())
    
    return search_results or [SearchResult(
        type="no_results",
        content=lm.get('search_no_results')
    ).to_dict()]
