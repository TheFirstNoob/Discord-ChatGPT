import asyncio
import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Comment as BS4Comment
from typing import Tuple, List, Optional, Callable
from duckduckgo_search import DDGS
from src.log import logger

# Internet config will be moved in .env later
MAX_RESULTS = 5
REQUEST_TIMEOUT = 15
MAX_PARAGRAPHS = 10
MAX_CHARS = 3000
UNWANTED_ELEMENTS = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'iframe', 'button', 'input', 'select', 'textarea', 'form']
RETRY_ATTEMPTS = 3
CONCURRENT_REQUESTS = 5

semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)


async def search_web(query: str, request_type: str = "search") -> list[dict]:
    try:
        if request_type == 'search':
            logger.info(f"Поиск по запросу: {query}")
            results = DDGS().text(query, max_results=MAX_RESULTS, region="wt-wt", safesearch="moderate", backend="auto")
            return list(results)

        elif request_type == 'images':
            logger.info(f"Картинки по запросу: {query}")
            results = DDGS().images(query, max_results=MAX_RESULTS, region="wt-wt", safesearch="moderate")
            return [result['image'] for result in results if result.get('image')]

        elif request_type == 'videos':
            logger.info(f"Поиск видео по запросу: {query}")
            results = DDGS().videos(query, max_results=MAX_RESULTS, region="wt-wt", safesearch="moderate")
            return [result['content'] for result in results if result.get('content')]

    except Exception as e:
        logger.error(f"search_web: Ошибка: {e}")
        return [f"Произошла ошибка при поиске: {e}"]


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
            response.raise_for_status()
            return await response.text(encoding='utf-8', errors='ignore')
    except aiohttp.ClientError as e:
        logger.error(f"fetch_html: Ошибка при получении {url}: {e}")
        raise
    except Exception as e:
        logger.exception(f"fetch_html: Неизвестная ошибка при получении {url}: {e}")
        raise


def clean_html(soup: BeautifulSoup, unwanted_elements: list[str]) -> None:
    for element in soup.find_all(unwanted_elements):
        element.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, BS4Comment)):
        comment.extract()


def extract_table_data(soup: BeautifulSoup) -> list[list[str]]:
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


def extract_text(soup: BeautifulSoup) -> list[str]:
    """Извлечение текста из HTML."""
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


def summarize_text(text_elements: list[str], max_paragraphs: int, max_chars: int) -> str:
    final_text = []
    chars_count = 0

    for element in text_elements:
        if len(final_text) >= max_paragraphs or chars_count >= max_chars:
            break
        final_text.append(element)
        chars_count += len(element)

    return '\n\n'.join(final_text)


async def get_website_info(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Получение информации с веб-сайта, включая заголовок и текст, с повторными попытками."""
    async with semaphore:
        async with aiohttp.ClientSession() as session:
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
                        if response.status == 403:
                            logger.warning(f"get_website_info: Ошибка 403 при получении {url}: Доступ запрещен. Пропускаем сайт.")
                            return None, "Доступ к сайту запрещен."

                        response.raise_for_status()

                        html = await response.text(encoding='utf-8', errors='ignore')

                        if len(html) > 1000 * 1024:
                            logger.warning(f"get_website_info: Слишком большой объем контента для обработки: {url}")
                            return None, "Слишком большой объем контента для обработки."

                        soup = BeautifulSoup(html, 'html.parser')
                        clean_html(soup, UNWANTED_ELEMENTS)

                        title = soup.title.text.strip() if soup.title else "Без названия"
                        text_elements = extract_text(soup)
                        paragraphs = summarize_text(text_elements, MAX_PARAGRAPHS, MAX_CHARS)

                        if not paragraphs:
                            logger.warning(f"get_website_info: Не удалось извлечь значимый контент: {url}")
                            return None, "Не удалось извлечь значимый контент."

                        return title, paragraphs

                except aiohttp.ClientError as e:
                    logger.warning(f"get_website_info: Ошибка aiohttp при обработке {url} (попытка {attempt + 1}/{RETRY_ATTEMPTS}): {e}")
                    if attempt < RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        logger.error(f"get_website_info: Не удалось получить {url} после {RETRY_ATTEMPTS} попыток.")
                        return None, f"Не удалось загрузить сайт после нескольких попыток: {e}"
                except Exception as e:
                    logger.exception(f"get_website_info: Ошибка при обработке {url}: {e}")
                    return None, f"Неизвестная ошибка: {e}"

            logger.error(f"get_website_info: Превышено количество повторных попыток для {url}.")
            return None, "Превышено количество повторных попыток."

async def prepare_search_results(results: list[dict], user_instruction: str = "", get_website_info_func: Callable[[str], Tuple[Optional[str], Optional[str]]] = get_website_info) -> list[dict]:
    search_results = []

    if user_instruction:
        search_results.append({"type": "instruction", "content": user_instruction})

    tasks = [get_website_info_func(result.get('href')) for result in results if result.get('href')]
    website_info_results = await asyncio.gather(*tasks, return_exceptions=True)

    for result, website_info in zip(results, website_info_results):
        if isinstance(website_info, Exception):
            logger.error(f"prepare_search_results: Ошибка при получении информации с сайта {result.get('href')}: {website_info}")
            search_results.append({
                "type": "error",
                "url": result.get('href'),
                "error": str(website_info)
            })
            continue

        if website_info:
            title, paragraphs = website_info
        else:
            title, paragraphs = None, None

        if title and paragraphs:
            search_results.append({
                "type": "website",
                "url": result.get('href', 'Ссылка не указана'),
                "title": title,
                "content": paragraphs
            })
        else:
            search_results.append({
                "type": "skipped",
                "url": result.get('href'),
                "title": title,
                "paragraphs": paragraphs
            })

    return search_results or [{"type": "no_results", "content": "По запросу ничего не найдено."}]
