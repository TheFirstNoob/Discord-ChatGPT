import os
import json
import discord
import asyncio
import aiofiles
from dotenv import load_dotenv
from src.log import logger, setup_logger
from utils.message_utils import send_split_message
from discord import app_commands
from duckduckgo_search import AsyncDDGS
from bs4 import BeautifulSoup
import g4f.debug
from g4f.client import AsyncClient
from g4f.stubs import ChatCompletion
from g4f.Provider import (
    Airforce, Blackbox, Bixin123, Binjie, ChatGot, ChatgptFree, ChatGptEs,
    DDG, FreeChatgpt, Free2GPT, HuggingChat, Nexra,
    ReplicateHome, Liaobots, LiteIcoding, PerplexityLabs, TeachAnything,
    Pizzagpt, RetryProvider
)

load_dotenv()

g4f.debug.logging = True
user_data_cache = {}

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
            raise Exception("All providers failed")
        provider = self.providers[self.current_index]
        self.current_index += 1
        return provider

    def reset(self):
        self.current_index = 0

def _initialize_providers():
    return {
        # Chat providers
        "gpt-3.5-turbo": [FreeChatgpt, Nexra],
        "gpt-4": [Nexra, Binjie, Airforce, Liaobots],
        "gpt-4-turbo": [Nexra, Airforce, Liaobots],
        "gpt-4o-mini": [Pizzagpt, ChatgptFree, ChatGptEs, Airforce, DDG, Liaobots],
        "gpt-4o": [LiteIcoding, ChatGptEs, Airforce, Liaobots],
        "claude-3-haiku": [ DDG, Liaobots],
        "blackbox": [Blackbox],
        "gemini-flash": [Blackbox, Liaobots],
        "gemini-pro": [ChatGot, Liaobots],
        "gemma-2b": [ReplicateHome],
        "command-r-plus": [HuggingChat],
        "llama-3.1-70b": [HuggingChat, Blackbox, TeachAnything, Free2GPT, DDG],
        "llama-3.1-405b": [Blackbox],
        "llama-3.1-sonar-large-128k-online": [PerplexityLabs],
        "llama-3.1-sonar-large-128k-chat": [PerplexityLabs],
        "qwen-turbo": [Bixin123],
        "qwen-2-72b": [Airforce],
        "mixtral-8x7b": [HuggingChat, ReplicateHome, DDG],
        "mixtral-8x7b-dpo": [HuggingChat],
        "mistral-7b": [HuggingChat],
        "yi-1.5-9b": [FreeChatgpt],
        "SparkDesk-v1.1": [FreeChatgpt],
    }

class DiscordClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.default_model = os.getenv("MODEL")
        self.max_history_length = int(os.getenv("MAX_HISTORY_LENGTH", 30))
        self.cache_enabled = os.getenv("CACHE_ENABLED", "True").lower() == "true"

        self.default_provider = RetryProvider([Pizzagpt, ChatgptFree, ChatGptEs, Airforce, DDG, Liaobots], shuffle=False)
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
                    await asyncio.gather(*tasks)  # Параллельная обработка сообщений
            await asyncio.sleep(1)

    async def enqueue_message(self, message, user_message, request_type):
        await self.message_queue.put((message, user_message, request_type))

    async def send_message(self, message, user_message, request_type):
        user_id = message.user.id

        try:
            response = await self.handle_response(user_id, user_message)
            response_content = f'\n{response}'
            await send_split_message(self, response_content, message)
        except Exception as e:
            logger.exception(f"Ошибка при отправке: {e}")

    async def send_start_prompt(self):
        discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
        try:
            if self.starting_prompt and discord_channel_id:
                channel = self.get_channel(int(discord_channel_id))
                logger.info(f"Отправка системных инструкций для ИИ с размером (байтов): {len(self.starting_prompt)}")

                response = await self.handle_response(None, self.starting_prompt)
                await channel.send(f"{response}")

                logger.info("Ответ от ИИ получен. Функция отработала корректно!")
            else:
                logger.info("Не установлены системные инструкции или не выбран Discord канал. Пропуск отправки `send_start_prompt` функции.")
        except Exception as e:
            logger.exception(f"Ошибка при отправке промта: {e}")

    async def handle_response(self, user_id: int, user_message: str) -> str:
        user_data = await self.load_user_data(user_id)
        conversation_history = user_data.get('history', [])
        user_model = user_data.get('model', self.default_model)

        conversation_history.append({'role': 'user', 'content': user_message})

        if len(conversation_history) > self.max_history_length:
            conversation_history = conversation_history[3:]  # Удаляем по 3 первых сообщения при переполении памяти

        retry_provider = await self.get_provider_for_model(user_model)
        retry_provider.reset()
        while True:
            try:
                provider = retry_provider.get_next_provider()
                self.chatBot = AsyncClient(provider=provider)
                response: ChatCompletion = await self.chatBot.chat.completions.create(model=user_model, messages=conversation_history)
                break
            except Exception as e:
                print(f"Error with provider {provider}: {e}")
                continue

        model_response = f"> :robot: **Вам отвечает модель:** *{user_model}* \n > :wrench: **Версия Hitagi ChatGPT:** *{os.environ.get('VERSION_BOT')}*"
        bot_response = response.choices[0].message.content
        conversation_history.append({'role': 'assistant', 'content': bot_response})

        await self.save_user_data(user_id, {'history': conversation_history, 'model': user_model})

        return f"{model_response}\n\n{bot_response}"
        
    async def download_conversation_history(self, user_id: int) -> str:
        filename = SYSTEM_DATA_FILE if user_id is None else f'{user_id}.json'
        filepath = os.path.join(USER_DATA_DIR, filename)
        return filepath if os.path.exists(filepath) else None

    async def get_provider_for_model(self, model: str):
        providers_dict = _initialize_providers()
        providers = providers_dict.get(model, self.default_provider)
        return RetryProvider(providers, shuffle=False)

    async def reset_conversation_history(self, user_id: int):
        await self.save_user_data(user_id, {'history': [], 'model': self.default_model})

    async def set_user_model(self, user_id: int, model_name: str):
        user_data = await self.load_user_data(user_id)
        user_data['model'] = model_name
        await self.save_user_data(user_id, user_data)

    async def get_user_data_filepath(self, user_id):
        filename = 'system.json' if user_id is None else f'{user_id}.json'
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
            initial_data = {'history': [], 'model': os.getenv("MODEL")}
            await self.save_user_data(user_id, initial_data)
            return initial_data

    async def save_user_data(self, user_id, data):
        filepath = await self.get_user_data_filepath(user_id)
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as file:
            await file.write(json.dumps(data, ensure_ascii=False, indent=4))
        user_data_cache[user_id] = data

discordClient = DiscordClient()