import os
import json
import discord
import asyncio
from dotenv import load_dotenv
from src.log import logger, setup_logger
from utils.message_utils import send_split_message
from discord import app_commands
from asgiref.sync import sync_to_async
import g4f.debug
from g4f.client import Client
from g4f.stubs import ChatCompletion
from g4f.Provider import (
    AiChatOnline, AiChats, Blackbox, Airforce, Bixin123, Binjie, CodeNews, ChatGot, Chatgpt4o, ChatgptFree, Chatgpt4Online,
    DDG, DeepInfra, DeepInfraImage, FreeChatgpt, FreeGpt, Free2GPT, FreeNetfly, Koala, HuggingChat, HuggingFace, Nexra,
    ReplicateHome, Liaobots, LiteIcoding, MagickPen, Prodia, PerplexityLabs, Pi, TeachAnything, TwitterBio, Snova, You,
    Pizzagpt, RetryProvider
)

load_dotenv()

g4f.debug.logging = True
user_data_cache = {}

USER_DATA_DIR = 'user_data'
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

class DiscordClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.default_model = os.getenv("MODEL")
        self.max_history_length = int(os.getenv("MAX_HISTORY_LENGTH", 30))
        self.cache_enabled = os.getenv("CACHE_ENABLED", "True").lower() == "true"

        self.default_provider = RetryProvider([Pizzagpt, AiChatOnline, ChatgptFree, CodeNews, You, FreeNetfly, Koala, MagickPen, DDG, Liaobots], shuffle=False)
        self.chatBot = Client(provider=self.default_provider)
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
                while not self.message_queue.empty():
                    async with self.current_channel.typing():
                        message, user_message = await self.message_queue.get()
                        try:
                            await self.send_message(message, user_message)
                        except Exception as e:
                            logger.exception(f"Ошибка при обработке сообщения: {e}")
                        finally:
                            self.message_queue.task_done()
            await asyncio.sleep(1)

    async def enqueue_message(self, message, user_message):
        await self.message_queue.put((message, user_message))

    async def send_message(self, message, user_message):
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
        user_data = self.load_user_data(user_id)
        conversation_history = user_data.get('history', [])
        user_model = user_data.get('model', self.default_model)

        conversation_history.append({'role': 'user', 'content': user_message})

        if len(conversation_history) > self.max_history_length:
            conversation_history = conversation_history[3:]  # Удаляем по 3 первых сообщения при переполении памяти

        selected_provider = self.get_provider_for_model(user_model)
        self.default_provider = selected_provider 
        self.chatBot = Client(provider=selected_provider)

        async_create = sync_to_async(self.chatBot.chat.completions.create, thread_sensitive=True)
        response: ChatCompletion = await async_create(model=user_model, messages=conversation_history)

        model_response = f"> :robot: **Вам отвечает модель:** *{user_model}* \n > :wrench: **Версия Hitagi ChatGPT:** *{os.environ.get('VERSION_BOT')}*"
        bot_response = response.choices[0].message.content
        conversation_history.append({'role': 'assistant', 'content': bot_response})

        self.save_user_data(user_id, {'history': conversation_history, 'model': user_model})

        return f"{model_response}\n\n{bot_response}"
        
    async def download_conversation_history(self, user_id: int) -> str:
        if user_id is None:
            filepath = os.path.join(USER_DATA_DIR, 'system.json')
        else:
            filepath = os.path.join(USER_DATA_DIR, f'{user_id}.json')
        
        if os.path.exists(filepath):
            return filepath
        return None

    def get_provider_for_model(self, model: str):
        providers = {
            "gpt-3.5-turbo": RetryProvider([FreeChatgpt, FreeNetfly, Bixin123, Nexra, TwitterBio, Airforce], shuffle=False),
            "gpt-4": RetryProvider([Chatgpt4Online, Nexra, Binjie, FreeNetfly, AiChats, Airforce, You, Liaobots], shuffle=False),
            "gpt-4-turbo": RetryProvider([Nexra, Bixin123, Airforce, You, Liaobots], shuffle=False),
            "gpt-4o-mini": RetryProvider([Pizzagpt, AiChatOnline, ChatgptFree, CodeNews, You, FreeNetfly, Koala, MagickPen, Airforce, DDG, Liaobots], shuffle=False),
            "gpt-4o": RetryProvider([Chatgpt4o, LiteIcoding, AiChatOnline, Airforce, You, Liaobots], shuffle=False),
            "claude-3-haiku": RetryProvider([DDG, Liaobots], shuffle=False),
            "blackbox": RetryProvider([Blackbox], shuffle=False),
            "gemini-flash": RetryProvider([Blackbox, Liaobots], shuffle=False),
            "gemini-pro": RetryProvider([ChatGot, Liaobots], shuffle=False),
            "gemma-2b": RetryProvider([ReplicateHome], shuffle=False),
            "command-r-plus": RetryProvider([HuggingChat, HuggingFace], shuffle=False),
            "llama-3.1-70b": RetryProvider([HuggingChat, HuggingFace, Blackbox, DeepInfra, FreeGpt, TeachAnything, Free2GPT, Snova, DDG], shuffle=False),
            "llama-3.1-405b": RetryProvider([Blackbox, Snova], shuffle=False),
            "llama-3.1-sonar-large-128k-online": RetryProvider([PerplexityLabs], shuffle=False),
            "llama-3.1-sonar-large-128k-chat": RetryProvider([PerplexityLabs], shuffle=False),
            "pi": RetryProvider([Pi], shuffle=False),
            "qwen-turbo": RetryProvider([Bixin123], shuffle=False),
            "qwen-2-72b": RetryProvider([Airforce], shuffle=False),
            "mixtral-8x7b": RetryProvider([HuggingChat, HuggingFace, ReplicateHome, TwitterBio, DeepInfra, DDG], shuffle=False),
            "mixtral-8x7b-dpo": RetryProvider([HuggingChat, HuggingFace], shuffle=False),
            "mistral-7b": RetryProvider([HuggingChat, HuggingFace, DeepInfra], shuffle=False),
            "yi-1.5-9b": RetryProvider([FreeChatgpt], shuffle=False),
            "SparkDesk-v1.1": RetryProvider([FreeChatgpt], shuffle=False),
        }

        return providers.get(model, self.default_provider)

    def reset_conversation_history(self, user_id: int):
        self.save_user_data(user_id, {'history': [], 'model': self.default_model})

    def set_user_model(self, user_id: int, model_name: str):
        user_data = self.load_user_data(user_id)
        user_data['model'] = model_name
        self.save_user_data(user_id, user_data)

    def get_user_data_filepath(self, user_id):
        if user_id is None:
            return os.path.join(USER_DATA_DIR, 'system.json')
        return os.path.join(USER_DATA_DIR, f'{user_id}.json')

    def load_user_data(self, user_id):
        if user_id in user_data_cache:
            return user_data_cache[user_id]

        filepath = self.get_user_data_filepath(user_id)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json.load(file)
                user_data_cache[user_id] = data
                return data
        else:
            initial_data = {'history': [], 'model': os.getenv("MODEL")}
            self.save_user_data(user_id, initial_data)
            user_data_cache[user_id] = initial_data
            return initial_data

    def save_user_data(self, user_id, data):
        filepath = self.get_user_data_filepath(user_id)
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        user_data_cache[user_id] = data

discordClient = DiscordClient()
