import os
import json
import discord
import asyncio
import aiofiles
import aiohttp
from dotenv import load_dotenv
from src.log import logger
from utils.message_utils import send_split_message
from discord import app_commands
from duckduckgo_search import AsyncDDGS
from bs4 import BeautifulSoup
import g4f.debug
from g4f.client import AsyncClient
from g4f.stubs import ChatCompletion
from g4f.Provider import (
    AIUncensored,
    Airforce,
    Blackbox,
    ChatGptEs,
    DDG,
    DarkAI,
    Free2GPT,
    GizAI,
    PerplexityLabs,
    TeachAnything,
    Mhystical,
    ReplicateHome,
    
    RetryProvider
)

client = AsyncClient()
load_dotenv()

g4f.debug.logging = os.getenv("G4F_DEBUG", "True")
user_data_cache = {}

SYSTEM_DATA_FILE = 'system.json'
USER_DATA_DIR = 'user_data'
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

class RetryProvider:
    def __init__(self, providers, shuffle=False):
        self.providers = providers
        self.shuffle = shuffle
        self.current_index = 0

    def get_next_provider(self):
        if self.current_index >= len(self.providers):
            raise Exception("Все провайдеры не ответили!")
        provider = self.providers[self.current_index]
        self.current_index += 1
        return provider

    def reset(self):
        self.current_index = 0

def _initialize_providers():
    return {
        # Chat providers
        "gpt-3.5-turbo": [DarkAI],
        "gpt-4": [Mhystical],
        "gpt-4o-mini": [Airforce, ChatGptEs, DDG],
        "gpt-4o": [Blackbox, ChatGptEs, Airforce, DarkAI],
        "claude-3-haiku": [DDG],
        "claude-3.5-sonnet": [Blackbox],
        "blackbox": [Blackbox],
        "blackbox-pro": [Blackbox],
        "gemini-flash": [Blackbox, GizAI],
        "gemini-pro": [Blackbox],
        "llama-3.1-70b": [Blackbox, TeachAnything, Free2GPT, Airforce, DDG, DarkAI],
        "llama-3.1-405b": [Blackbox, DarkAI],
        "sonar-chat": [PerplexityLabs],
        "lfm-40b": [PerplexityLabs],
        "mixtral-8x7b": [DDG],

        "llava-13b": [ReplicateHome], # vision for later
    }

class DiscordClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.providers_dict = _initialize_providers()
        self.default_model = os.getenv("MODEL", "blackbox")
        self.max_history_length = int(os.getenv("MAX_HISTORY_LENGTH", 30))
        self.cache_enabled = os.getenv("CACHE_ENABLED", "True").lower() == "true"

        default_providers = self.providers_dict.get(self.default_model, [])
        self.default_provider = RetryProvider(default_providers, shuffle=False)
        self.chatBot = AsyncClient(provider=self.default_provider)
        self.current_channel = None
        self.activity = discord.Activity(type=discord.ActivityType.listening, name="/ask /draw /help")

        config_dir = os.path.abspath(f"{__file__}/../../")
        prompt_name = 'system_prompt.txt'
        prompt_path = os.path.join(config_dir, prompt_name)

        with open(prompt_path, "r", encoding="utf-8") as f:
            self.starting_prompt = f.read()

        self.message_queue = asyncio.Queue()

    async def process_messages(self):
        while True:
            if self.current_channel is not None:
                tasks = []
                while not self.message_queue.empty():
                    async with self.current_channel.typing():
                        message, user_message, request_type = await self.message_queue.get()
                        tasks.append(self.send_message(message, user_message, request_type))
                        self.message_queue.task_done()
                if tasks:
                    await asyncio.gather(*tasks)
            await asyncio.sleep(1)
            
    async def process_request(self, query, request_type="search", max_results=3):
        if request_type == 'search':
            logger.info(f"Поиск по запросу: {query}")
            results = await AsyncDDGS().atext(query, max_results=max_results)
            tasks = [self.get_website_info(result.get('href')) for result in results if result.get('href')]
            website_info = await asyncio.gather(*tasks)
            conversation_history = []
            for title, paragraphs in website_info:
                if title and paragraphs:
                    conversation_history.append(f"Ссылка на ресурс: {result.get('href')}\nНазвание: {title}\nСодержимое:\n{paragraphs}\n")
            return conversation_history
        elif request_type == 'images':
            logger.info(f"Картинки по запросу: {query}")
            results = await AsyncDDGS().aimages(query, max_results=5)
            image_links = [result['image'] for result in results if result.get('image')]
            if not image_links:
                return [f"Не удалось найти картинки по запросу '{query}'."]
            return [
                f"Картинки по запросу '{query}':\n" +
                "\n".join(image_links)
            ]
        elif request_type == 'videos':
            logger.info(f"Поиск видео по запросу: {query}")
            results = await AsyncDDGS().avideos(query, max_results=5)
            media_links = [result['content'] for result in results if result.get('content')]
            if not media_links:
                return [f"Не удалось найти видео по запросу '{query}'."]
            return [
                f"Видео по запросу '{query}':\n" +
                "\n".join(media_links)
            ]

    async def get_website_info(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    title = soup.title.text if soup.title else "Без названия"
                    paragraphs = [p.text for p in soup.find_all('p')]
                    return title, '\n'.join(paragraphs)
        except aiohttp.ClientError as e:
            logger.error(f"get_website_info: Ошибка сети при получении информации с {url}: {e}")
            return None, "Ошибка сети. Пожалуйста, попробуйте позже."
        except Exception as e:
            logger.exception(f"get_website_info: Не удалось получить информацию с сайта {url}: {e}")
            return None, f"Мне не удалось найти информацию на сайте из-за ошибки. Попробуйте еще раз позже или сообщите {os.environ.get('ADMIN_NAME')} если ошибка повторяется несколько раз."
        async def enqueue_message(self, message, user_message, request_type):
            await self.message_queue.put((message, user_message, request_type))

    async def send_message(self, message, user_message, request_type):
        user_id = message.user.id

        try:
            response = await self.handle_response(user_id, user_message, request_type)
            response_content = f'\n{response}'
            await send_split_message(self, response_content, message)
        except Exception as e:
            logger.exception(f"send_message: Ошибка при отправке: {e}")

    async def send_start_prompt(self):
        discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
        try:
            if self.starting_prompt and discord_channel_id:
                channel = self.get_channel(int(discord_channel_id))
                logger.info(f"Отправка системных инструкций для ИИ с размером (байтов): {len(self.starting_prompt)}")

                response = await self.handle_response(None, self.starting_prompt)
                await channel.send(f"{response}")

                logger.info("send_start_prompt: Ответ от ИИ получен. Функция отработала корректно!")
            else:
                logger.info("send_start_prompt: Не установлены системные инструкции или не выбран Discord канал. Пропуск отправки `send_start_prompt` функции.")
        except Exception as e:
            logger.exception(f"send_start_prompt: Ошибка при отправке промта: {e}")

    async def handle_response(self, user_id: int, user_message: str, request_type: str = None) -> str:
        user_data = await self.load_user_data(user_id)
        conversation_history = user_data.get('history', [])
        user_model = user_data.get('model', self.default_model)

        conversation_history.append({'role': 'user', 'content': user_message})

        if len(conversation_history) > self.max_history_length:
            conversation_history = conversation_history[3:]

        if request_type:
            search_results = await self.process_request(user_message, request_type=request_type, max_results=3)
            for result in search_results:
                instruction = (
                    "[СИСТЕМНАЯ ИНСТРУКЦИЯ] ПОЛЬЗОВАТЕЛЬ ЗАПРОСИЛ ИНФОРМАЦИЮ ИЗ ИНТЕРНЕТА. "
                    "ОБРАБОТАЙ ПОЛУЧЕННУЮ ИНФОРМАЦИЮ, ОТВЕТЬ ПОЛЬЗОВАТЕЛЮ КАК СЧИТАЕШЬ ПРАВИЛЬНЫМ И БЕЗОПАСНЫМ, "
                    "И ОБЯЗАТЕЛЬНО УКАЖИ ПОЛУЧЕННЫЕ ИСТОЧНИКИ, ЕСЛИ НЕ МОЖЕШЬ ОТВЕТИТЬ ИЗ ПОЛУЧЕННЫХ ДАННЫХ САЙТА, "
                    "ТО СООБЩИ ПОЛЬЗОВАТЕЛЮ ОБ ЭТОМ, ЧТО МАЛО ИНФОРМАЦИИ ИЛИ ИМЕЮТСЯ ПРОБЛЕМЫ. "
                    "ЕСЛИ ПОЛЬЗОВАТЕЛЬ ЗАПРОСИЛ КАРТИНКИ ИЛИ ВИДЕО, ТО ПРОСТО ОТПРАВЬ ЕМУ ПОЛУЧЕННЫЕ ССЫЛКИ И ОТВЕТЬ В РАМКАХ ЕГО ЗАПРОСА!]: "
                    f"Результат поиска: {result}"
                )
                conversation_history.append({'role': 'assistant', 'content': instruction})

        retry_provider = await self.get_provider_for_model(user_model)
        retry_provider.reset()
        
        attempts = 0
        max_attempts = len(retry_provider.providers)
        last_error = None

        while attempts < max_attempts:
            try:
                provider = retry_provider.get_next_provider()
                logger.info(f"handle_response: Текущий провайдер выбран: {provider}")
                self.chatBot = AsyncClient(provider=provider)
                response: ChatCompletion = await self.chatBot.chat.completions.create(model=user_model, messages=conversation_history)
                break
            except Exception as e:
                logger.exception(f"handle_response: Ошибка с провайдером {provider}: {e}")
                last_error = e
                attempts += 1

        if attempts == max_attempts:
            return (":x: **ОШИБКА:** К сожалению, все провайдеры для этой модели недоступны. "
                    "Пожалуйста, попробуйте позже или смените модель.\n\n"
                    f"**Код ошибки:** ```{last_error}```")

        model_response = f"> :robot: **Вам отвечает модель:** *{user_model}* \n > :wrench: **Версия {os.environ.get('BOT_NAME')}:** *{os.environ.get('VERSION_BOT')}*"
        bot_response = response.choices[0].message.content
        conversation_history.append({'role': 'assistant', 'content': bot_response})

        await self.save_user_data(user_id, {'history': conversation_history, 'model': user_model})
        return f"{model_response}\n\n{bot_response}"
        
    async def download_conversation_history(self, user_id: int) -> str:
        filename = SYSTEM_DATA_FILE if user_id is None else f'{user_id}.json'
        filepath = os.path.join(USER_DATA_DIR, filename)
        return filepath if os.path.exists(filepath) else None

    async def get_provider_for_model(self, model: str):
        providers = self.providers_dict.get(model, self.default_provider)
        return RetryProvider(providers, shuffle=False)

    async def reset_conversation_history(self, user_id: int):
        await self.save_user_data(user_id, {'history': [], 'model': self.default_model})

    async def set_user_model(self, user_id: int, model_name: str):
        user_data = await self.load_user_data(user_id)
        user_data['model'] = model_name
        await self.save_user_data(user_id, user_data)

    async def get_user_data_filepath(self, user_id):
        filename = SYSTEM_DATA_FILE if user_id is None else f'{user_id}.json'
        return os.path.join(USER_DATA_DIR, filename)

    async def load_user_data(self, user_id):
        if user_id in user_data_cache:
            return user_data_cache[user_id]

        filepath = await self.get_user_data_filepath(user_id)
        if os.path.exists(filepath):
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as file:
                data = await file.read()
                user_data_cache[user_id] = json.loads(data)
                return user_data_cache[user_id]
        else:
            initial_data = {'history': [], 'model': self.default_model}
            await self.save_user_data(user_id, initial_data)
            return initial_data

    async def save_user_data(self, user_id, data):
        filepath = await self.get_user_data_filepath(user_id)
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as file:
            await file.write(json.dumps(data, ensure_ascii=False, indent=4))
        user_data_cache[user_id] = data

discordClient = DiscordClient()