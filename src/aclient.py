import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

# discord
import discord
from discord import app_commands, Attachment

# g4f
import g4f.debug
from g4f.client import AsyncClient
from g4f.Provider import (
    Airforce,
    Blackbox,
    ChatGptEs,
    DDG,
    DarkAI,
    Free2GPT,
    GizAI,
    TeachAnything,
    Mhystical,
    PollinationsAI,
    DeepInfraChat,
    RetryProvider
)

# local
from src.locale_manager import locale_manager as lm  # For locale later
from src.log import logger
from src.ban_manager import ban_manager
from utils.message_utils import send_split_message
from utils.files_utils import read_json, write_json
from utils.reminder_utils import check_reminders
from utils.internet_utils import search_web, get_website_info, prepare_search_results
from utils.internet_instructions_utils import get_web_search_instruction, get_image_search_instruction, get_video_search_instruction

# const
SYSTEM_DATA_FILE = 'system.json'
USER_DATA_DIR = 'user_data'
REMINDERS_DIR = 'reminders'

load_dotenv()
client = AsyncClient()
g4f.debug.logging = os.getenv("G4F_DEBUG", "True")
user_data_cache = {}

if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)
if not os.path.exists(REMINDERS_DIR):
    os.makedirs(REMINDERS_DIR)

async def check_ban_and_respond(interaction):
    try:
        is_banned, ban_message = await discordClient.check_user_ban(interaction.user.id)
        if is_banned:
            await interaction.response.send_message(ban_message, ephemeral=True)
            return True
        return False
    except Exception as e:
        logger.error(f"check_ban_and_respond: Ошибка при проверке бана пользователя {interaction.user.id}: {e}")
        await interaction.response.send_message("> :x: **ОШИБКА:** Не удалось проверить ваш статус бана. Пожалуйста, попробуйте позже.", ephemeral=True)
        return True

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
        "gpt-4o-mini": [ChatGptEs, DDG],
        "gpt-4o": [Blackbox, PollinationsAI, ChatGptEs, DarkAI],
        "claude-3-haiku": [DDG],
        "claude-3.5-sonnet": [Blackbox, PollinationsAI],
        "blackboxai": [Blackbox],
        "blackboxai-pro": [Blackbox],
        "gemini-flash": [GizAI],
        "gemini-pro": [Blackbox],
        "llama-3.1-70b": [Blackbox, DeepInfraChat, PollinationsAI, TeachAnything, Free2GPT, Airforce, DDG, DarkAI],
        "llama-3.1-405b": [Blackbox],
        "llama-3.3-70b": [Blackbox, DeepInfraChat],
        "qwq-32b": [Blackbox, DeepInfraChat],
        "deepseek-chat": [Blackbox],
        "lfm-40b": [Airforce],
        "mixtral-8x7b": [DDG]
    }

class DiscordClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.providers_dict = _initialize_providers()
        self.default_model = os.getenv("MODEL", "gpt-4o")
        self.max_history_length = int(os.getenv("MAX_HISTORY_LENGTH", 30))
        self.cache_enabled = os.getenv("CACHE_ENABLED", "True").lower() == "true"
        self.reminder_task = None

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
        
    async def setup_hook(self):
        if not hasattr(self, 'reminder_task') or self.reminder_task is None:
            self.reminder_task = asyncio.create_task(check_reminders(self))

    async def check_user_ban(self, user_id):
        is_banned, reason = await ban_manager.is_user_banned(user_id)
        
        if is_banned:
            ban_file = os.path.join(ban_manager.bans_dir, f'{user_id}_ban.json')
            
            with open(ban_file, 'r', encoding='utf-8') as f:
                ban_data = json.loads(f.read())

            if ban_data['duration'] is None:
                unban_text = "Перманентный бан"
            else:
                ban_time = datetime.fromisoformat(ban_data['timestamp'])
                duration = timedelta(**ban_data['duration'])
                unban_date = (ban_time + duration).strftime('%Y-%m-%d %H:%M:%S')
                unban_text = f"Дата разблокировки: {unban_date}"

            return True, f"Вам заблокирован доступ к использованию этим ботом.\nПричина: {reason}\n{unban_text}"

        return False, None

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
            
    async def process_request(self, query, request_type="search"):
        try:
            results = await search_web(query, request_type)
            
            if request_type == 'search':
                conversation_history = []
                for result in results:
                    instruction = get_web_search_instruction(result)
                    conversation_history.append(instruction)
                return conversation_history
            
            elif request_type == 'images':
                instructions = [get_image_search_instruction(result) for result in results]
                return instructions or [f"Не удалось найти картинки по запросу '{query}'."]
            
            elif request_type == 'videos':
                instructions = [get_video_search_instruction(result) for result in results]
                return instructions or [f"Не удалось найти видео по запросу '{query}'."]
        
        except Exception as e:
            logger.error(f"Ошибка в process_request: {e}")
            return [f"Произошла ошибка при поиске: {e}"]

    async def enqueue_message(self, message, user_message, request_type):
        await self.message_queue.put((message, user_message, request_type))

    async def send_message(self, message, user_message, request_type):
        if hasattr(message, 'user'):
            user_id = message.user.id
        elif hasattr(message, 'author'):
            user_id = message.author.id
        else:
            raise ValueError("send_message: Неподдерживаемый тип объекта message")

        try:
            response = await self.handle_response(user_id, user_message, request_type)
            response_content = f'\n{response}'
            await send_split_message(self, response_content, message)
        except Exception as e:
            error_message = (
                f"> :x: **ОШИБКА В ОБРАБОТКЕ ЗАПРОСА:** \n"
                f"```\n{str(e)}\n```\n"
                "> Пожалуйста, попробуйте еще раз или сообщите администратору."
            )
            logger.exception(f"send_message: Полная ошибка при отправке: {e}")
            try:
                await send_split_message(self, error_message, message)
            except Exception as send_error:
                logger.error(f"send_message: Критическая ошибка при попытке отправить сообщения с ошибкой: {send_error}")

    async def send_start_prompt(self):
        try:
            discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
            
            if not discord_channel_id:
                logger.warning("send_start_prompt: DISCORD_CHANNEL_ID не установлен в .env файле")
                return
                
            if not self.starting_prompt:
                logger.warning("send_start_prompt: Системные инструкции не установлены")
                return

            await self.wait_until_ready()
            
            channel = self.get_channel(int(discord_channel_id))
            if channel is None:
                logger.error(f"send_start_prompt: Не удалось найти канал с ID {discord_channel_id}")
                return

            logger.info(f"Отправка системных инструкций для ИИ с размером (байтов): {len(self.starting_prompt)}")

            response = await self.handle_response(None, self.starting_prompt)
            if response:
                await channel.send(f"{response}")
                logger.info("send_start_prompt: Ответ от ИИ получен. Функция отработала корректно!")
            else:
                logger.warning("send_start_prompt: Не получен ответ от ИИ")
                
        except ValueError as e:
            logger.error(f"send_start_prompt: Ошибка при конвертации ID канала: {e}")
        except Exception as e:
            logger.exception(f"send_start_prompt: Ошибка при отправке промта: {e}")
            
    async def handle_response(self, user_id: int, user_message: str, request_type: str = None) -> str:
        if user_id:
            is_banned, ban_message = await self.check_user_ban(user_id)
            if is_banned:
                return ban_message

        try:
            user_data = await self.load_user_data(user_id)
            conversation_history = user_data.get('history', [])
            user_model = user_data.get('model', self.default_model)
            conversation_history.append({'role': 'user', 'content': user_message})

            if len(conversation_history) > self.max_history_length:
                conversation_history = conversation_history[3:]

            if request_type:
                try:
                    search_results = await self.process_request(user_message, request_type=request_type)

                    for result in search_results:
                        conversation_history.append({'role': 'assistant', 'content': result})
                
                except Exception as search_error:
                    logger.error(f"Ошибка при поиске: {search_error}")
                    conversation_history.append({
                        'role': 'system', 
                        'content': f"ОШИБКА ПРИ ПОИСКЕ: {str(search_error)}"
                    })

            retry_provider = await self.get_provider_for_model(user_model)
            retry_provider.reset()

            attempts = 0
            max_attempts = len(retry_provider.providers)
            last_error = None
            current_provider = None

            while attempts < max_attempts:
                try:
                    current_provider = retry_provider.get_next_provider()
                    logger.info(f"handle_response: Выбран провайдер: {current_provider}")

                    self.chatBot = AsyncClient(provider=current_provider)
                    response = await self.chatBot.chat.completions.create(model=user_model, messages=conversation_history)
                    break
                
                except Exception as e:
                    logger.exception(f"handle_response: Ошибка с провайдером: {current_provider}: {e}")
                    last_error = e
                    attempts += 1

            if attempts == max_attempts:
                return (":x: **ОШИБКА:** К сожалению, все провайдеры для этой модели недоступны. "
                        "Пожалуйста, попробуйте позже или смените модель.\n\n"
                        f"**Код ошибки:** ```{last_error}```")

            model_response = (
                f"> :robot: **Вам отвечает модель:** *{user_model}* \n"
                f"> :wrench: **Версия {os.environ.get('BOT_NAME')}:** *{os.environ.get('VERSION_BOT')}*"
            )
            bot_response = response.choices[0].message.content
            conversation_history.append({'role': 'assistant', 'content': bot_response})
            await self.save_user_data(user_id, {'history': conversation_history, 'model': user_model})
            return f"{model_response}\n\n{bot_response}"
        
        except Exception as global_error:
            logger.exception(f"handle_response: Критическая ошибка: {global_error}")
            return (":x: **КРИТИЧЕСКАЯ ОШИБКА:** Не удалось обработать ваш запрос. "
                    "Пожалуйста, попробуйте еще раз или сообщите администратору.\n\n"
                    f"**Детали ошибки:** ```{str(global_error)}```")
        
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
        data = await read_json(filepath)
        
        if data:
            user_data_cache[user_id] = data
            return data
        else:
            initial_data = {'history': [], 'model': self.default_model}
            await self.save_user_data(user_id, initial_data)
            return initial_data

    async def save_user_data(self, user_id, data):
        filepath = await self.get_user_data_filepath(user_id)
        await write_json(filepath, data)
        user_data_cache[user_id] = data

discordClient = DiscordClient()
