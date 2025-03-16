import asyncio
import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Comment as BS4Comment
from typing import Tuple, List, Optional, Callable, Dict, Any
from duckduckgo_search import DDGS
from src.log import logger

class HTMLTooLargeError(Exception):
    pass

MAX_RESULTS = 5
REQUEST_TIMEOUT = 15
MAX_PARAGRAPHS = 10
MAX_CHARS = 3000
MAX_HTML_SIZE = 1000 * 1024  # 1 МБ
SKIP_HTTP_ERRORS = [403, 404, 410]

UNWANTED_ELEMENTS = [
    'script', 'style', 'nav', 'footer', 'header', 'aside',
    'noscript', 'iframe', 'button', 'input', 'select', 'textarea', 'form'
]
RETRY_ATTEMPTS = 3
CONCURRENT_REQUESTS = 5

semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)


async def search_web(query: str, request_type: str = "search") -> List[Dict[str, Any]]:
    try:
        ddgs = DDGS()
        if request_type == 'search':
            logger.info(f"Поиск по запросу: {query}")
            results = ddgs.text(query, max_results=MAX_RESULTS, region="wt-wt", safesearch="moderate", backend="auto")
            return list(results)
        elif request_type == 'images':
            logger.info(f"Картинки по запросу: {query}")
            results = ddgs.images(query, max_results=MAX_RESULTS, region="wt-wt", safesearch="moderate")
            return [result['image'] for result in results if result.get('image')]
        elif request_type == 'videos':
            logger.info(f"Поиск видео по запросу: {query}")
            results = ddgs.videos(query, max_results=MAX_RESULTS, region="wt-wt", safesearch="moderate")
            return [result['content'] for result in results if result.get('content')]
    except Exception as e:
        logger.error(f"search_web: Ошибка: {e}")

        return []


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
            if response.status in SKIP_HTTP_ERRORS:
                logger.warning(f"fetch_html: Ошибка {response.status} при получении {url}: Пропускаем сайт.")
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"Ошибка {response.status}: Пропускаем сайт.",
                    headers=response.headers
                )
            response.raise_for_status()
            html = await response.text(encoding='utf-8', errors='ignore')
            if len(html) > MAX_HTML_SIZE:
                logger.warning(f"fetch_html: Слишком большой объем контента для обработки: {url}")
                raise HTMLTooLargeError("Слишком большой объем контента для обработки.")
            return html
    except aiohttp.ClientError as e:
        logger.error(f"fetch_html: Ошибка при получении {url}: {e}")
        raise
    except Exception as e:
        logger.exception(f"fetch_html: Неизвестная ошибка при получении {url}: {e}")
        raise


def clean_html(soup: BeautifulSoup, unwanted_elements: List[str]) -> None:
    for element in soup.find_all(unwanted_elements):
        element.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, BS4Comment)):
        comment.extract()


def extract_table_data(soup: BeautifulSoup) -> List[List[str]]:
    table = soup.find('table')
    if not table:
        return []
    data = []
    rows = table.find_all('tr')
    for row in rows:
        cells = row.find_all(['td', 'th'])
        row_data = [cell.get_text(strip=True) for cell in cells]
        data.append(row_data)
    return data


def extract_text(soup: BeautifulSoup) -> List[str]:
    text_elements = []
    for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        text = header.get_text(strip=True)
        if len(text) > 10:
            text_elements.append(f"### {text}")
    for element in soup.find_all(['p', 'b', 'div']):
        text = element.get_text(strip=True)
        if len(text) > 40:
            text_elements.append(text)
    for lst in soup.find_all(['ul', 'ol']):
        items = lst.find_all('li')
        list_text = []
        for item in items:
            item_text = item.get_text(strip=True)
            if len(item_text) > 20:
                list_text.append(f"• {item_text}")
        if list_text:
            text_elements.extend(list_text)
    table_data = extract_table_data(soup)
    if table_data:
        for row in table_data:
            text_elements.append(" | ".join(row))

    return list(dict.fromkeys(text_elements))


def summarize_text(text_elements: List[str], max_paragraphs: int, max_chars: int) -> str:
    final_text = []
    chars_count = 0
    for element in text_elements:
        if len(final_text) >= max_paragraphs or chars_count >= max_chars:
            break
        final_text.append(element)
        chars_count += len(element)
    return '\n\n'.join(final_text)


async def get_website_info(session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], Optional[str]]:
    async with semaphore:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                html = await fetch_html(session, url)
                soup = BeautifulSoup(html, 'html.parser')
                clean_html(soup, UNWANTED_ELEMENTS)
                title = soup.title.text.strip() if soup.title else "Без названия"
                text_elements = extract_text(soup)
                paragraphs = summarize_text(text_elements, MAX_PARAGRAPHS, MAX_CHARS)
                if not paragraphs:
                    logger.warning(f"get_website_info: Не удалось извлечь значимый контент: {url}")
                    return None, "Не удалось извлечь значимый контент."
                return title, paragraphs
            except (aiohttp.ClientResponseError, HTMLTooLargeError) as e:
                logger.warning(f"get_website_info: Пропускаем сайт {url} из-за ошибки: {e}")
                return None, f"Ошибка: {e}"
            except aiohttp.ClientError as e:
                logger.warning(
                    f"get_website_info: Ошибка aiohttp при обработке {url} (попытка {attempt + 1}/{RETRY_ATTEMPTS}): {e}"
                )
            except Exception as e:
                logger.exception(f"get_website_info: Ошибка при обработке {url}: {e}")
                return None, f"Неизвестная ошибка: {e}"
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(2 ** attempt)
        logger.error(f"get_website_info: Превышено количество повторных попыток для {url}.")
        return None, "Превышено количество повторных попыток."


async def prepare_search_results(
    results: List[Dict[str, Any]],
    user_instruction: str = "",
    get_website_info_func: Callable[[aiohttp.ClientSession, str], Tuple[Optional[str], Optional[str]]] = get_website_info,
    cancel_on_error: bool = False
) -> List[Dict[str, Any]]:
    search_results = []
    if user_instruction:
        search_results.append({"type": "instruction", "content": user_instruction})

    # Отбираем результаты, где указан 'href'
    valid_results = [result for result in results if result.get('href')]
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for result in valid_results:
            task = asyncio.create_task(get_website_info_func(session, result.get('href')))
            tasks.append((result, task))
        
        # Если требуется отмена при ошибке, используем asyncio.wait
        if cancel_on_error:
            done, pending = await asyncio.wait(
                [t[1] for t in tasks], return_when=asyncio.FIRST_EXCEPTION
            )
            # При первой критической ошибке отменяем оставшиеся задачи
            for task in pending:
                task.cancel()
        
        # Обрабатываем результаты
        for result, task in tasks:
            try:
                title, paragraphs = await task
            except Exception as e:
                logger.error(f"prepare_search_results: Ошибка при получении информации с сайта {result.get('href')}: {e}")
                search_results.append({
                    "type": "error",
                    "url": result.get('href'),
                    "error": str(e)
                })
                continue

            # Явная проверка на None для title и paragraphs
            if title is None or paragraphs is None:
                search_results.append({
                    "type": "skipped",
                    "url": result.get('href'),
                    "title": title,
                    "content": paragraphs
                })
            else:
                search_results.append({
                    "type": "website",
                    "url": result.get('href', 'Ссылка не указана'),
                    "title": title,
                    "content": paragraphs
                })
    return search_results or [{"type": "no_results", "content": "По запросу ничего не найдено."}]
