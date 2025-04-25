import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dotenv import load_dotenv

# discord
import discord
from discord import app_commands

# g4f
import g4f.debug
from g4f.cookies import set_cookies_dir, read_cookie_files
from g4f.client import AsyncClient
from g4f.Provider import (
    #Anthropic,
    #AIChatFree,
    Blackbox,           # Now request payment for other models :c
    #CablyAI,           # Now request api_key
    ChatGLM,
    #ChatGptEs,         # data error
    #Cerebras,          # Cloudflare detected
    Cloudflare,
    DDG,
    #DarkAI,            # Disabled in G4F SSL error
    #DeepInfraChat,     # Return auth error but we auth
    #DeepSeek,          # Request api/g4f need add non api endpoint
    Free2GPT,
    #FreeGpt,           # China lang only :c
    GizAI,
    Glider,
    OpenaiChat,         # Experimental
    #OIVSCode,          # 503 HTML Error
    #GlhfChat,          # Request api
    #Groq,              # Cloudflare detected
    #HailuoAI,
    #MiniMax,
    TeachAnything,
    PollinationsAI,
    #Reka,              # Request AUTH (har/cookies)
    #PerplexityLabs,    # Cloudflare detected
    #PerplexityApi,
    HuggingChat,        # Request AUTH (har/cookies)
    HuggingSpace,       # Request AUTH (har/cookies)
    #Jmuz,              # RU region block
    #Mhystical,         # Cloudflare detected
    Websim,

    RetryProvider
)

# This is example for api_key later
#from g4f.Provider.needs_auth import DeepSeekAPI    # use if you have dsk.api lib

from g4f.models import __models__

# local
from src.locale_manager import locale_manager as lm
from src.log import logger
from utils.message_utils import send_split_message
from utils.files_utils import read_json, write_json, read_file, write_file
from utils.encryption_utils import UserDataEncryptor
from utils.reminder_utils import init_reminder_scheduler, run_reminder_scheduler
from utils.ban_utils import ban_manager
from utils.internet_utils import search_web, prepare_search_results
from utils.internet_instructions_utils import get_web_search_instruction, get_image_search_instruction, get_video_search_instruction

# Constants
SYSTEM_DATA_FILE = 'system.json'
USER_DATA_DIR = 'user_data'
REMINDERS_DIR = 'reminders'
BANS_DIR = 'bans'
SYSTEM_INSTRUCTION_FILE = "system_prompt.txt"

# Initialize environment
load_dotenv()
client = AsyncClient()
g4f.debug.logging = os.getenv("G4F_DEBUG", "True")

# Setup directories
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
cookies_dir = os.path.join(parent_dir, "har_and_cookies")

# Initialize cookies if directory exists
if os.path.isdir(cookies_dir):
    set_cookies_dir(cookies_dir)
    read_cookie_files(cookies_dir)
else:
    print(lm.get('log_cookies_dir_error').format(dir=cookies_dir))

# Create necessary directories
for directory in [USER_DATA_DIR, REMINDERS_DIR, BANS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

def _initialize_providers() -> Dict[str, List[Any]]:
    """
    Initialize and configure AI providers.
    
    Returns:
        Dictionary mapping model names to their available providers
    """
    logger.info(lm.get('log_providers_init'))

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
        "gpt-4o-mini": [DDG, PollinationsAI, Blackbox],
        "gpt-4o": [PollinationsAI],
        "o3-mini": [DDG, PollinationsAI, Blackbox],
        "blackboxai": [Blackbox],
        "command-r-plus": [HuggingSpace, HuggingChat],
        "command-r7b-12-2024": [HuggingSpace],
        "command-a": [HuggingSpace],
        "claude-3-haiku": [DDG],    # working. i disable for new models space
        "claude-3.5-sonnet": [Blackbox],
        "claude-3.7-sonnet": [Blackbox],
        "gemini-1.5-flash": [GizAI, Blackbox, TeachAnything, Websim],
        "gemini-1.5-pro": [Blackbox, Free2GPT, TeachAnything, Websim],
        "gemini-2.0-flash": [Blackbox, PollinationsAI],
        "gemini-2.0-flash-thinking": [PollinationsAI],
        "llama-3.1-405b": [Blackbox],
        "llama-3.2-11b": [HuggingChat], # Vision
        "llama-3.3-70b": [HuggingChat, Blackbox],
        "llama-4-scout": [Cloudflare, PollinationsAI],
        "qwq-32b": [Blackbox, HuggingChat], # HuggingChat has Starting resoning only, idk at this moment how to fix
        "qwen-qvq-72b-preview": [HuggingSpace],
        "qwen-2.5-72b": [HuggingChat],
        "qwen-2.5-coder-32b": [HuggingChat, PollinationsAI],
        "qwen-2.5-coder": [Cloudflare],
        "qwen-2.5-1m-demo": [HuggingSpace],
        "qwen-2.5-max": [HuggingSpace],
        #"nemotron-70b": [HuggingChat], # working. i disable for new models space
        "deepseek-chat": [Blackbox],
        "deepseek-v3": [Blackbox, PollinationsAI],
        "deepseek-r1": [HuggingChat, Glider, Blackbox, PollinationsAI],
        "mixtral-small-24b": [DDG, Blackbox],
        "glm-4": [ChatGLM],
        "phi-3.5-mini": [HuggingChat],
        "phi-4": [PollinationsAI, HuggingSpace],
        "google/gemma-3-27b-it": [PollinationsAI],
    }

    for provider_name, api_key in api_providers.items():
        if not api_key or not api_key.strip():
            logger.warning(lm.get('log_provider_skip').format(provider=provider_name.upper()))
            continue

        is_test = api_key.lower() == 'test'
        if is_test:
            logger.warning(lm.get('log_provider_warning').format(provider=provider_name))
            
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
                if is_test:
                    logger.info(lm.get('log_provider_test_added').format(provider=provider_name, models=provider_added_to_models))
                else:
                    logger.info(lm.get('log_provider_added').format(provider=provider_name, models=provider_added_to_models))
        
        except AttributeError:
            logger.warning(lm.get('log_provider_not_found').format(provider=provider_name))
        except Exception as e:
            logger.error(lm.get('log_provider_add_error').format(provider=provider_name, error=e))

    logger.info(lm.get('log_providers_complete'))
    return providers_dict

class UserCache:
    """Cache for user data with sliding and absolute TTL."""
    
    def __init__(self, sliding_ttl: timedelta = timedelta(hours=1), absolute_ttl: timedelta = timedelta(hours=24)):
        """
        Initialize the user cache.
        
        Args:
            sliding_ttl: Time of inactivity after which cache is removed
            absolute_ttl: Maximum time data can be stored from load time
        """
        self.cache: Dict[int, Tuple[Any, datetime, datetime]] = {}
        self.sliding_ttl = sliding_ttl
        self.absolute_ttl = absolute_ttl

    def get(self, user_id: int) -> Optional[Any]:
        """
        Get cached data for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Cached data or None if not found/expired
        """
        if user_id in self.cache:
            data, load_time, last_access = self.cache[user_id]
            now = datetime.now()

            if now - load_time > self.absolute_ttl:
                del self.cache[user_id]
                return None

            if now - last_access > self.sliding_ttl:
                del self.cache[user_id]
                return None
                
            self.cache[user_id] = (data, load_time, now)
            return data
        return None

    def set(self, user_id: int, data: Any) -> None:
        """
        Set data in cache for a user.
        
        Args:
            user_id: Discord user ID
            data: Data to cache
        """
        now = datetime.now()
        self.cache[user_id] = (data, now, now)

    def clear_expired(self) -> None:
        """Clear all expired entries from cache."""
        now = datetime.now()
        for user_id in list(self.cache.keys()):
            data, load_time, last_access = self.cache[user_id]
            if now - load_time > self.absolute_ttl or now - last_access > self.sliding_ttl:
                del self.cache[user_id]

class DiscordClient(discord.Client):
    """Discord client with AI chat capabilities."""
    
    def __init__(self) -> None:
        """Initialize the Discord client with necessary configurations."""
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        # Initialize components
        self.tree = app_commands.CommandTree(self)
        self.providers_dict = _initialize_providers()
        self.default_model = os.getenv("MODEL", "gpt-4o")
        self.max_history_length = int(os.getenv("MAX_HISTORY_LENGTH", 30))
        self.apply_instruction_to_all = os.getenv("APPLY_INSTRUCTION_TO_ALL", "False").lower() == "true"
        self.cache_enabled = os.getenv("CACHE_ENABLED", "True").lower() == "true"
        self.encrypt_user_data = os.getenv('ENCRYPT_USER_DATA', 'False').lower() == 'true'
        self.encrypt_channels = os.getenv('ENCRYPT_CHANNELS', 'False').lower() == 'true'
        
        # Initialize tasks
        self.reminder_task = None
        self.ban_cleanup_task = None
        
        # Initialize providers
        default_providers = self.providers_dict.get(self.default_model, [])
        self.default_provider = RetryProvider(default_providers, shuffle=False)
        self.clients_by_provider = {}
        self.chatBot = AsyncClient(provider=self.default_provider)
        
        # Initialize state
        self.current_channel = None
        self.activity = discord.Activity(type=discord.ActivityType.listening, name="/ask /draw /help")
        self.user_cache = UserCache(sliding_ttl=timedelta(hours=1), absolute_ttl=timedelta(hours=24))

    async def setup_hook(self) -> None:
        """Set up the client's background tasks."""
        logger.info(lm.get('log_discord_init'))
        logger.info(lm.get('log_reminder_scheduler_prepare'))
        await init_reminder_scheduler(self)

        async def run_reminders_check():
            while True:
                try:
                    await run_reminder_scheduler()
                except Exception as e:
                    logger.error(lm.get('log_request_error').format(error=e))
                await asyncio.sleep(30)

        async def run_bans_check():
            while True:
                try:
                    await ban_manager.check_bans()
                except Exception as e:
                    logger.error(lm.get('log_request_error').format(error=e))
                await asyncio.sleep(1800)

        if not hasattr(self, 'reminder_task') or self.reminder_task is None:
            logger.info(lm.get('log_reminder_task_init'))
            self.reminder_task = asyncio.create_task(run_reminders_check())

        if not hasattr(self, 'ban_cleanup_task') or self.ban_cleanup_task is None:
            logger.info(lm.get('log_ban_task_init'))
            self.ban_cleanup_task = asyncio.create_task(run_bans_check())

        logger.info(lm.get('log_tasks_init_complete'))

    async def process_request(self, query: str, user_id: int, request_type: str = "search") -> List[str]:
        """
        Process a user's request and return appropriate responses.
        
        Args:
            query: User's query
            user_id: Discord user ID
            request_type: Type of request (search, images, videos)
            
        Returns:
            List of response messages
        """
        self.user_id = user_id
        try:
            results = await search_web(query, request_type)
            if not results:
                return [lm.get('error_no_results').format(query=query)]

            if request_type == 'search':
                try:
                    processed_results = await prepare_search_results(results)
                    return [
                        get_web_search_instruction(result) 
                        for result in processed_results
                        if result.get('content')
                    ] or [lm.get('error_no_content').format(query=query)]
                
                except Exception as e:
                    logger.error(lm.get('log_request_error').format(error=e))
                    return [lm.get('error_processing_results').format(error=str(e))]
            elif request_type == 'images':
                return [
                    get_image_search_instruction(img_url)
                    for img_url in results
                    if img_url
                ] or [lm.get('error_no_images').format(query=query)]
            elif request_type == 'videos':
                return [
                    get_video_search_instruction(video_url)
                    for video_url in results
                    if video_url
                ] or [lm.get('error_no_videos').format(query=query)]

            return [lm.get('error_unsupported_request_type').format(type=request_type)]

        except Exception as e:
            logger.error(lm.get('log_request_error').format(error=e))
            return [
                lm.get('error_critical_request_processing').format(query=query, error=str(e)),
                lm.get('error_try_later_or_change_query')
            ]

    async def send_message(self, message: Any, user_message: str, request_type: str) -> None:
        """
        Send a message to the user.
        
        Args:
            message: Discord message object
            user_message: User's message
            request_type: Type of request
        """
        try:
            if hasattr(message, 'user'):
                user_id = message.user.id
                username = str(message.user)
            elif hasattr(message, 'author'):
                user_id = message.author.id
                username = str(message.author)
            else:
                raise ValueError(lm.get('error_unsupported_message_type'))
                
            response = await self.handle_response(user_id, user_message, request_type)
            if not response:
                error_message = (
                    f"> :x: **{lm.get('error_request_processing')}** \n"
                    f"> {lm.get('error_try_again_or_contact_admin')}"
                )
                logger.error(lm.get('log_user_ask_error').format(username=username, error=lm.get('error_empty_ai_response')))
                await send_split_message(self, error_message, message)
                return
                
            response_content = f'\n{response}'
            await send_split_message(self, response_content, message)
        except Exception as e:
            error_message = (
                f"> :x: **{lm.get('error_request_processing')}** \n"
                f"```\n{str(e)}\n```\n"
                f"> {lm.get('error_try_again_or_contact_admin')}"
            )
            logger.exception(lm.get('log_send_error').format(error=e))
            try:
                await send_split_message(self, error_message, message)
            except Exception as send_error:
                logger.error(lm.get('log_send_critical_error').format(error=send_error))

    async def send_start_prompt(self) -> None:
        """Send the initial system prompt to the configured channel."""
        try:
            discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")
            if not discord_channel_id:
                logger.error(lm.get('log_channel_error'))
                return
                
            await self.wait_until_ready()
            channel = self.get_channel(int(discord_channel_id))
            if channel is None:
                logger.error(lm.get('log_channel_error').format(channel_id=discord_channel_id))
                return
                
            user_data = await self.load_user_data(None, int(discord_channel_id))
            starting_prompt = user_data.get('instruction', '')
            logger.info(lm.get('log_system_instructions').format(size=len(starting_prompt)))
            
            if not starting_prompt:
                logger.error(lm.get('log_system_instructions_empty'))
                return
                
            response = await self.handle_response(None, starting_prompt, channel_id=int(discord_channel_id))
            if response:
                await channel.send(f"{response}")
                logger.info(lm.get('log_start_prompt_success'))
            else:
                logger.warning(lm.get('log_start_prompt_empty'))
        except ValueError as e:
            logger.error(lm.get('log_channel_convert_error').format(error=str(e)))
        except Exception as e:
            logger.error(lm.get('log_start_prompt_critical').format(error=str(e)))

    async def handle_response(self, user_id: int, user_message: str, request_type: str = None, channel_id: Optional[int] = None) -> str:
        """
        Handle user message and generate response.
        
        Args:
            user_id: Discord user ID
            user_message: User's message
            request_type: Type of request
            channel_id: Discord channel ID
            
        Returns:
            Generated response
        """
        try:
            user_data = await self.load_user_data(user_id, channel_id)
            history = user_data.get('history', [])
            model = user_data.get('model', self.default_model)
            user_instruction = user_data.get('instruction', '')
            
            # Update history with user message
            history = self._update_conversation_history(history, user_message)
            
            # Append search results if request_type is provided
            if request_type:
                history = await self._append_search_results(history, user_message, request_type, user_id)
            
            # Get response from provider
            response_data = await self._get_response_from_provider(model, history)
            
            if 'error' in response_data:
                logger.error(f"handle_response: {response_data['error']}")
                return response_data['error']
                
            response_content = response_data['bot_response']
            
            # Update history with response
            history.append({'role': 'assistant', 'content': response_content})
            
            # Save updated history
            user_data['history'] = history
            user_data['instruction'] = user_instruction
            await self.save_user_data(user_id, user_data, channel_id)
            
            # Format response with model info
            model_response = lm.get('model_response').format(
                model=model,
                bot_name=os.environ.get('BOT_NAME'),
                version=os.environ.get('VERSION_BOT')
            )
            return f"{model_response}\n\n{response_content}"
            
        except Exception as e:
            logger.exception(lm.get('log_handle_response_critical').format(error=e))
            return (
                f":x: **{lm.get('error_critical')}:** {lm.get('error_request_processing_failed')}\n\n"
                f"**{lm.get('error_details')}:** ```{str(e)}```"
            )

    def _update_conversation_history(self, history: List[Dict[str, str]], user_message: str) -> List[Dict[str, str]]:
        """
        Update conversation history with new message.
        
        Args:
            history: Current conversation history
            user_message: New user message
            
        Returns:
            Updated conversation history
        """
        history.append({'role': 'user', 'content': user_message})
        if len(history) > self.max_history_length:
            system_message = next((msg for msg in history if msg['role'] == 'system'), None)
            if system_message:
                history = [system_message] + history[-(self.max_history_length - 1):]
            else:
                history = history[-self.max_history_length:]
        return history

    async def _append_search_results(self, history: List[Dict[str, str]], user_message: str, request_type: str, user_id: int) -> List[Dict[str, str]]:
        """
        Append search results to conversation history.
        
        Args:
            history: Current conversation history
            user_message: User's message
            request_type: Type of request
            user_id: Discord user ID
            
        Returns:
            Updated conversation history
        """
        try:
            search_results = await self.process_request(user_message, user_id, request_type=request_type)
            for result in search_results:
                history.append({'role': 'assistant', 'content': result})
        except Exception as e:
            logger.error(lm.get('log_search_error').format(error=e))
            history.append({'role': 'system', 'content': f"{lm.get('error_search_failed')}: {str(e)}"})
        return history

    async def _get_response_from_provider(
        self,
        user_model: str,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Attempt providers in sequence, starting with the one that last successfully responded.

        Args:
            user_model: The name of the model to use.
            conversation_history: The list of past messages (role/content dicts).

        Returns:
            A dict with either:
              - "bot_response": the text reply from the AI, or
              - "error": an error message if all providers failed.
        """
        # Copy the list of providers for this model
        providers = list(self.providers_dict.get(user_model, []))
        last_error = None

        for provider in providers:
            try:
                logger.info(lm.get('log_provider_trying').format(provider=provider))

                # get or create a client for this provider
                client = self.clients_by_provider.get(provider)
                if not client:
                    client = AsyncClient(provider=provider)
                    self.clients_by_provider[provider] = client

                # send the request
                response = await client.chat.completions.create(
                    model=user_model,
                    messages=conversation_history,
                    provider=provider
                )

                # on success, move this provider to the front of the list
                lst = self.providers_dict[user_model]
                lst.remove(provider)
                lst.insert(0, provider)

                return {"bot_response": response.choices[0].message.content}

            except Exception as e:
                logger.exception(lm.get('log_provider_failed').format(provider=provider, error=e))
                last_error = e
                # try next provider

        # all providers failed
        return {
            "error": (
                f":x: **{lm.get('error_all_providers_failed')}**\n"
                f"> {lm.get('error_try_different_model')}\n\n"
                f"**{lm.get('error_last_error')}:** ```{last_error}```"
            )
        }

    async def get_provider_for_model(self, model: str) -> RetryProvider:
        """
        Get provider for a specific model.
        
        Args:
            model: Model name
            
        Returns:
            RetryProvider instance
        """
        providers = self.providers_dict.get(model)
        if providers is None or not providers:
            providers = self.default_provider.providers
        return RetryProvider(providers, shuffle=False)

    async def reset_conversation_history(self, user_id: int) -> None:
        """
        Reset conversation history for a user.
        
        Args:
            user_id: Discord user ID
        """
        await self.save_user_data(user_id, {'history': [], 'model': self.default_model})

    async def set_user_model(self, user_id: int, model_name: str) -> None:
        """
        Set model for a user.
        
        Args:
            user_id: Discord user ID
            model_name: Model name
        """
        user_data = await self.load_user_data(user_id)
        user_data['model'] = model_name
        await self.save_user_data(user_id, user_data)

    async def load_user_data(self, user_id: Optional[int], channel_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Load user data from storage.
        
        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            
        Returns:
            User data dictionary
        """

        if self.cache_enabled and user_id is not None:
            cached = self.user_cache.get(user_id)
            if cached:
                return cached

        filepath = await self.get_user_data_filepath(user_id, channel_id)
        data = None

        try:
            raw = await read_file(filepath)
            if not raw:
                raise FileNotFoundError(lm.get('error_empty_file'))

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                encryptor = await UserDataEncryptor(user_id, channel_id).initialize()
                data = await encryptor.decrypt(raw)
                if data is None:
                    raise ValueError(lm.get('error_decryption_failed'))
        except Exception as e:
            logger.error(lm.get('log_load_data_error').format(error=e))
            data = None

        if not data:
            instruction = ""
            if self.apply_instruction_to_all or user_id is None:
                instruction = await self.load_instruction_from_file(SYSTEM_INSTRUCTION_FILE)

            data = {
                'history': [{'role': 'system', 'content': instruction}] if instruction else [],
                'model': self.default_model,
                'instruction': instruction
            }
            try:
                await self.save_user_data(user_id, data, channel_id)

                if channel_id is not None and channel_id == int(os.getenv("DISCORD_CHANNEL_ID", "")):
                    logger.info(lm.get('log_new_system_file').format(filepath=filepath))
                else:
                    logger.info(lm.get('log_new_data_file').format(filepath=filepath, user_id=user_id))
            except Exception as e:
                logger.error(lm.get('file_write_error').format(filepath=filepath, error=e))

        if self.cache_enabled and user_id is not None:
            self.user_cache.set(user_id, data)
        return data

    async def save_user_data(self, user_id: Optional[int], data: Dict[str, Any], channel_id: Optional[int] = None) -> None:
        """
        Save user data to storage.
        
        Args:
            user_id: Discord user ID
            data: User data dictionary
            channel_id: Discord channel ID
        """

        if not data:
            filepath = await self.get_user_data_filepath(user_id, channel_id)
            logger.error(lm.get('file_write_error').format(filepath=filepath, error="No data to save"))
            return

        filepath = await self.get_user_data_filepath(user_id, channel_id)

        should_encrypt = (
            channel_id is None and self.encrypt_user_data or
            channel_id is not None and self.encrypt_channels
        )

        if should_encrypt:
            encryptor = await UserDataEncryptor(user_id, channel_id).initialize()
            raw = await encryptor.encrypt(data)
            if not raw:
                logger.error(lm.get('encryption_encrypt_error').format(error="Failed to encrypt data"))
                return
            await write_file(filepath, raw)
        else:
            await write_json(filepath, data)

        if self.cache_enabled and user_id is not None:
            self.user_cache.set(user_id, data)

    async def set_user_instruction(self, user_id: int, instruction: str) -> None:
        """
        Set instruction for a user.
        
        Args:
            user_id: Discord user ID
            instruction: Instruction text
        """
        user_data = await self.load_user_data(user_id)
        user_data['history'] = [msg for msg in user_data.get('history', []) if msg['role'] not in ['system']]
        if instruction:
            user_data['history'].insert(0, {'role': 'system', 'content': instruction})
        user_data['instruction'] = instruction
        await self.save_user_data(user_id, user_data)

    async def reset_user_instruction(self, user_id: int) -> None:
        """
        Reset instruction for a user.
        
        Args:
            user_id: Discord user ID
        """
        user_data = await self.load_user_data(user_id)
        user_data['history'] = [msg for msg in user_data.get('history', []) if msg['role'] not in ['system']]
        user_data['instruction'] = ""
        await self.save_user_data(user_id, user_data)

    async def get_user_data_filepath(self, user_id: Optional[int], channel_id: Optional[int] = None) -> str:
        """
        Get filepath for user data.
        
        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            
        Returns:
            Filepath string
        """
        # For system channel, use system.json
        if channel_id is not None and channel_id == int(os.getenv("DISCORD_CHANNEL_ID", "")):
            filename = SYSTEM_DATA_FILE
        # For DMs, use user-specific file with encryption
        elif channel_id is None:
            filename = f'user_{user_id}.json'
        # For other channels, use channel-specific file without encryption
        else:
            filename = f'channel_{channel_id}.json'
            
        filepath = os.path.join(USER_DATA_DIR, filename)
        return filepath

    async def load_instruction_from_file(self, filepath: str) -> str:
        """
        Load instruction from file.
        
        Args:
            filepath: Path to instruction file
            
        Returns:
            Instruction text
        """
        try:
            instruction = await read_file(filepath)
            return instruction or ""
        except FileNotFoundError:
            logger.warning(lm.get('log_instruction_not_found').format(filepath=filepath))
            return ""
        except Exception as e:
            logger.error(lm.get('log_load_instruction_error').format(error=e))
            return ""

# Initialize Discord client
discordClient = DiscordClient()
