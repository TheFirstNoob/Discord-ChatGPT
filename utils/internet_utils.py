import aiohttp
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from src.log import logger

async def search_web(query, request_type="search"):
    try:
        if request_type == 'search':
            logger.info(f"Поиск по запросу: {query}")
            results = DDGS().text(query, max_results=3, region="wt-wt", safesearch="moderate", backend="auto")
            return results
                
        elif request_type == 'images':
            logger.info(f"Картинки по запросу: {query}")
            results = DDGS().images(query, max_results=5, region="wt-wt", safesearch="moderate")
            return [result['image'] for result in results if result.get('image')]
        
        elif request_type == 'videos':
            logger.info(f"Поиск видео по запросу: {query}")
            results = DDGS().videos(query, max_results=5, region="wt-wt", safesearch="moderate")
            return [result['content'] for result in results if result.get('content')]
    
    except Exception as e:
        logger.error(f"Ошибка в search_web: {e}")
        return [f"Произошла ошибка при поиске: {e}"]

async def get_website_info(url, max_paragraphs=5, max_chars=2000):

    try:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response.raise_for_status()

                    content = await response.read()
                    if len(content) > 500 * 1024:
                        return None, "Слишком большой объем контента для обработки."
                    
                    html = content.decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(html, 'html.parser')

                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    title = soup.title.text if soup.title else "Без названия"

                    paragraphs = soup.find_all('p')
                    processed_paragraphs = []
                    total_chars = 0
                    
                    for p in paragraphs:
                        if total_chars > max_chars:
                            break
                        
                        text = p.get_text(strip=True)
                        if text and len(text) > 30:
                            processed_paragraphs.append(text)
                            total_chars += len(text)
                        
                        if len(processed_paragraphs) >= max_paragraphs:
                            break
                    
                    return title, '\n'.join(processed_paragraphs)
            
            except aiohttp.ClientTimeout:
                logger.error(f"get_website_info: Превышено время ожидания для {url}")
                return None, "Время загрузки сайта истекло. Попробуйте позже."
            
            except aiohttp.ClientError as e:
                logger.error(f"get_website_info: Ошибка сети при получении информации с {url}: {e}")
                return None, f"Не удалось загрузить сайт. Возможно, он недоступен. Ошибка: {e}"
    
    except Exception as e:
        logger.exception(f"get_website_info: Не удалось получить информацию с сайта {url}: {e}")
        return None, f"Произошла неизвестная ошибка при обработке сайта. Попробуйте еще раз."

async def prepare_search_results(results, get_website_info_func=get_website_info):
    tasks = [get_website_info_func(result.get('href')) for result in results if result.get('href')]
    website_info = await asyncio.gather(*tasks)
    conversation_history = []
    
    for result, (title, paragraphs) in zip(results, website_info):
        if title and paragraphs:
            conversation_history.append(
                f"Ссылка на ресурс: {result.get('href', 'Ссылка не указана')}\n"
                f"Название: {title}\n"
                f"Содержимое:\n{paragraphs}\n"
            )
    
    return conversation_history or [f"По запросу ничего не найдено."]