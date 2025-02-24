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
from g4f.cookies import set_cookies_dir, read_cookie_files
from g4f.client import AsyncClient
from g4f.Provider import (
    #AmigoChat, # Quota limits
    #AutonomousAI,  # g4f error
    #Anthropic,
    #AIChatFree,
    Blackbox,  # Now request payment for other models :c
    BlackboxAPI,
    CablyAI,
    ChatGLM,
    #ChatGptEs, # data error
    #ChatGptt, # 10-30+ sec for response SSL Error
    #Cerebras,  # Cloudflare detected
    DDG,
    #DarkAI,    # Disabled in G4F SSL error
    #DeepInfraChat, # Return auth error but+ we auth
    #DeepSeek,  # Request api/g4f need add non api endpoint
    #Free2GPT,  # Old models
    #FreeGpt,    # China lang only
    GizAI,
    Glider,
    #GPROChat,
    OpenaiChat, # Experimental
    #OIVSCode, # 503 HTML Error
    #GlhfChat, # Request api
    #Groq,  # Cloudflare detected
    #TeachAnything, # Old models
    PollinationsAI,
    #Reka,  # Cloudflare detected
    #PerplexityLabs,    # Cloudflare detected
    HuggingChat,    # Request AUTH (har/cookies)
    HuggingSpace,
    #Jmuz,  # RU region block
    #Mhystical, # Cloudflare detected
    #RubiksAI, # Cloudflare detected

    RetryProvider
)

from g4f.models import __models__

# local
from src.locale_manager import locale_manager as lm  # For locale later
from src.log import logger
from src.ban_manager import ban_manager
from utils.message_utils import send_split_message
from utils.files_utils import read_json, write_json, read_file, write_file
from utils.encryption_utils import UserDataEncryptor
from utils.reminder_utils import check_reminders
from utils.internet_utils import search_web, get_website_info, prepare_search_results
from utils.internet_instructions_utils import get_web_search_instruction, get_image_search_instruction, get_video_search_instruction

# const
SYSTEM_DATA_FILE = 'system.json'
USER_DATA_DIR = 'user_data'
REMINDERS_DIR = 'reminders'
SYSTEM_INSTRUCTION_FILE = "system_prompt.txt"

load_dotenv()
client = AsyncClient()
g4f.debug.logging = os.getenv("G4F_DEBUG", "True")
user_data_cache = {}

current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
cookies_dir = os.path.join(parent_dir, "har_and_cookies")

if os.path.isdir(cookies_dir):
    set_cookies_dir(cookies_dir)
    read_cookie_files(cookies_dir)
else:
    print(f"har_and_cookies: Директория {cookies_dir} не читается или не существует.")

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
    logger.info("_initialize_providers: Начало инициализации провайдеров...")

    """
    ⚠️ EXPERIMENTAL CODE WARNING FOR API REALISE ⚠️

    This implementation is in an early experimental stage.
    - May contain significant bugs
    - Not recommended for production use
    - Requires further testing and refinement


    🤝 COMMUNITY HELP WANTED 🤝

    If you are an experienced developer and can help improve this implementation, 
    I would be extremely grateful! 

    Suggestions, code reviews, and collaborative improvements are welcome.
    Please feel free to contact me or submit improvements via GitHub/other platforms.

    Your expertise could help make this code more robust and reliable.
    """
    api_providers = {
        "Groq": os.getenv("GROQ_API_KEY"),
        #"Anthropic": os.getenv("ANTHROPIC_API_KEY"),    # import error :c
        "OpenaiChat": os.getenv("OPENAI_API_KEY"),
        #"Gemini or GeminiPro": os.getenv("GOOGLE_API_KEY") or os.environ.get("G4F_LOGIN_URL")
        "Perplexity": os.getenv("PERPLEXITY_API_KEY"),
        "DeepInfra": os.getenv("DEEPINFRA_API_KEY"),
        "HuggingFace": os.getenv("HUGGINGFACE_API_KEY")
    }

    providers_dict = {
        "gpt-4o-mini": [DDG, CablyAI, PollinationsAI],
        "gpt-4o": [PollinationsAI],
        "o3-mini-low": [CablyAI, PollinationsAI],
        "o3-mini": [DDG],
        #"claude-3.5-sonnet": [Blackbox],
        "blackboxai": [Blackbox],
        "command-r-plus": [HuggingSpace, HuggingChat],
        "command-r7b-12-2024": [HuggingSpace],
        "gemini-1.5-flash": [GizAI, Blackbox],
        #"gemini-1.5-pro": [Blackbox],
        "gemini-2.0-flash": [Blackbox, PollinationsAI],
        "gemini-2.0-flash-thinking": [PollinationsAI],
        "llama-3.1-405b": [Blackbox],
        "llama-3.2-11b": [HuggingChat],
        "llama-3.3-70b": [HuggingChat, PollinationsAI, Blackbox],
        "qwq-32b": [HuggingChat, Blackbox],
        "qwen-qvq-72b-preview": [HuggingSpace],
        "qwen-2.5-72b": [HuggingChat],
        "qwen-2.5-coder-32b": [HuggingChat, PollinationsAI],
        "nemotron-70b": [HuggingChat],
        "deepseek-chat": [PollinationsAI],
        "deepseek-v3": [Blackbox],
        "deepseek-r1": [BlackboxAPI, Blackbox, HuggingChat, Glider],
        "mixtral-8x7b": [DDG],
        #"cably-80b": [CablyAI],
        "glm-4": [ChatGLM],
        "phi-3.5-mini": [HuggingChat],
    }

    for provider_name, api_key in api_providers.items():
        logger.info(f"_initialize_providers: Проверка провайдера: {provider_name}")

        if not api_key or not api_key.strip():
            logger.warning(f"{provider_name.upper()}_API_KEY не установлен. Пропуск.")
            continue

        if api_key.lower() == 'test':
            logger.warning(f"_initialize_providers: Тестово добавлен провайдер {provider_name}. Код может работать нестабильно!")
            
        try:
            provider_class = getattr(g4f.Provider, provider_name)
            provider_added_to_models = []

            for model_name in __models__:
                if model_name in providers_dict:
                    if provider_class in __models__[model_name][1]:
                        if provider_class not in providers_dict[model_name]:
                            providers_dict[model_name].insert(0, provider_class)
                            provider_added_to_models.append(model_name)

            if provider_added_to_models:
                logger.info(f"_initialize_providers: API провайдер {provider_name} добавлен в модели: {provider_added_to_models}")
        
        except AttributeError:
            logger.warning(f"_initialize_providers: Провайдер {provider_name} не найден в g4f.Provider")
        except Exception as e:
            logger.error(f"_initialize_providers: Ошибка при добавлении API провайдера {provider_name}: {e}")

    logger.info("_initialize_providers: Инициализация провайдеров завершена")
    return providers_dict

class DiscordClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.providers_dict = _initialize_providers()
        self.default_model = os.getenv("MODEL", "gpt-4o")
        self.max_history_length = int(os.getenv("MAX_HISTORY_LENGTH", 30))
        self.apply_instruction_to_all = os.getenv("APPLY_INSTRUCTION_TO_ALL", "False").lower() == "true"
        self.cache_enabled = os.getenv("CACHE_ENABLED", "True").lower() == "true"
        self.encrypt_user_data = os.getenv('ENCRYPT_USER_DATA', 'False').lower() == 'true'
        self.reminder_task = None

        default_providers = self.providers_dict.get(self.default_model, [])
        self.default_provider = RetryProvider(default_providers, shuffle=False)
        self.chatBot = AsyncClient(provider=self.default_provider)
        self.current_channel = None
        self.activity = discord.Activity(type=discord.ActivityType.listening, name="/ask /draw /help")
        
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
                unban_text = f"Дата разблокировки: {unban_text}"

            return True, f":x: Вам заблокирован доступ к использованию этим ботом!\n**Причина**: {reason}\n{unban_text}"

        return False, None

    async def process_request(self, query, user_id: int, request_type="search"):
        self.user_id = user_id
        try:
            results = await search_web(query, request_type)
            
            if request_type == 'search':
                try:
                    user_data = await self.load_user_data(self.user_id)
                    user_instruction = user_data.get('instruction', '')

                    conversation_history = await prepare_search_results(results, user_instruction)
                    return conversation_history
                except Exception as e:
                    logger.error(f"prepare_search_results: Ошибка при подготовке результатов поиска: {e}")
                    return [f"Произошла ошибка при подготовке результатов поиска: {e}"]
            
            elif request_type == 'images':
                instructions = [get_image_search_instruction(result) for result in results]
                return instructions or [f"Не удалось найти картинки по запросу '{query}'."]
            
            elif request_type == 'videos':
                instructions = [get_video_search_instruction(result) for result in results]
                return instructions or [f"Не удалось найти видео по запросу '{query}'."]
        
        except Exception as e:
            logger.error(f"Ошибка в process_request: {e}")
            return [f"Произошла ошибка при поиске: {e}"]

    async def send_message(self, message, user_message, request_type):
        try:
            if hasattr(message, 'user'):
                user_id = message.user.id
            elif hasattr(message, 'author'):
                user_id = message.author.id
            else:
                raise ValueError("send_message: Неподдерживаемый тип объекта message")

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
                
            await self.wait_until_ready()
            
            channel = self.get_channel(int(discord_channel_id))
            if channel is None:
                logger.error(f"send_start_prompt: Не удалось найти канал с ID {discord_channel_id}")
                return

            user_data = await self.load_user_data(None)
            starting_prompt = user_data.get('instruction', '')

            logger.info(f"Отправка системных инструкций для ИИ с размером (байтов): {len(starting_prompt)}")

            response = await self.handle_response(None, starting_prompt)
            if response:
                await channel.send(f"{response}")
                logger.info("send_start_prompt: Ответ от ИИ получен. Функция отработала корректно!")
            else:
                logger.warning("send_start_prompt: Ошибка получения ответа от ИИ!")
                
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
            user_instruction = user_data.get('instruction', '')

            conversation_history.append({'role': 'user', 'content': user_message})

            if len(conversation_history) > self.max_history_length:
                system_message = next((msg for msg in conversation_history if msg['role'] == 'system'), None)
                
                if system_message:
                    conversation_history = [system_message] + conversation_history[-(self.max_history_length-1):]
                else:
                    conversation_history = conversation_history[-self.max_history_length:]

            if request_type:
                try:
                    search_results = await self.process_request(user_message, user_id, request_type=request_type)

                    for result in search_results:
                        conversation_history.append({'role': 'assistant', 'content': result})
                
                except Exception as search_error:
                    logger.error(f"handle_response: Ошибка при поиске: {search_error}")
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
                    response = await self.chatBot.chat.completions.create(
                        model=user_model, 
                        messages=conversation_history,
                        provider=current_provider
                    )
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

            await self.save_user_data(user_id, {
                'history': conversation_history, 
                'model': user_model, 
                'instruction': user_instruction
            })
            
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

    async def load_user_data(self, user_id):
        if user_id is not None and user_id in user_data_cache:
            return user_data_cache[user_id]

        filepath = await self.get_user_data_filepath(user_id)
        
        if self.encrypt_user_data:
            try:
                encrypted_data = await read_file(filepath)
                
                if not encrypted_data:
                    raise FileNotFoundError("load_user_data: Файл пуст")

                encryptor = await UserDataEncryptor(user_id).initialize()
                data = await encryptor.decrypt(encrypted_data)

                if not data:
                    raise ValueError("load_user_data: Не удалось расшифровать данные")

            except Exception as e:
                logger.error(f"load_user_data: Ошибка при расшифровке: {e}")
                data = None
        else:
            data = await read_json(filepath)

        if not data:
            instruction = await self.load_instruction_from_file(SYSTEM_INSTRUCTION_FILE) \
                if self.apply_instruction_to_all or user_id is None else ""
            
            data = {
                'history': [{'role': 'system', 'content': instruction}] if instruction else [], 
                'model': self.default_model, 
                'instruction': instruction
            }

            await self.save_user_data(user_id, data)
            logger.info(f"load_user_data: Создан новый файл данных {filepath} (user_id: {user_id})")
        return data

    async def save_user_data(self, user_id, data):
        filepath = await self.get_user_data_filepath(user_id)
        
        if self.encrypt_user_data:
            encryptor = await UserDataEncryptor(user_id).initialize()
            encrypted_data = await encryptor.encrypt(data)
            await write_file(filepath, encrypted_data)
        else:
            await write_json(filepath, data)

        user_data_cache[user_id] = data
        
    async def set_user_instruction(self, user_id: int, instruction: str):
        user_data = await self.load_user_data(user_id)
        user_data['history'] = [
            msg for msg in user_data.get('history', []) 
            if msg['role'] not in ['system']
        ]

        if instruction:
            user_data['history'].insert(0, {'role': 'system', 'content': instruction})

        user_data['instruction'] = instruction
        await self.save_user_data(user_id, user_data)

    async def reset_user_instruction(self, user_id: int):
        user_data = await self.load_user_data(user_id)
        user_data['history'] = [
            msg for msg in user_data.get('history', []) 
            if msg['role'] not in ['system']
        ]
        user_data['instruction'] = ""
        await self.save_user_data(user_id, user_data)

    async def get_user_data_filepath(self, user_id):
        filename = SYSTEM_DATA_FILE if user_id is None else f'{user_id}.json'
        filepath = os.path.join(USER_DATA_DIR, filename)
        return filepath

    async def load_instruction_from_file(self, filepath):
        try:
            instruction = await read_file(filepath)
            return instruction or ""
        except FileNotFoundError:
            logger.warning(f"load_instruction_from_file: Файл инструкций не найден: {filepath}")
            return ""
        except Exception as e:
            logger.error(f"load_instruction_from_file: Ошибка чтения файла инструкций: {e}")
            return ""

discordClient = DiscordClient()
