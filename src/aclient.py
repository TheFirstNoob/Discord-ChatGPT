import os
import json
import discord
import asyncio

from src.log import logger, setup_logger
from utils.message_utils import send_split_message

from dotenv import load_dotenv
from discord import app_commands
from asgiref.sync import sync_to_async

import g4f.debug
from g4f.client import Client
from g4f.stubs import ChatCompletion
from g4f.Provider import RetryProvider, DDG, Pizzagpt

g4f.debug.logging = True

USER_DATA_DIR = 'user_data'
if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

class discordClient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.chatBot = Client(
            provider=RetryProvider([Pizzagpt, DDG], shuffle=False),
        )
        self.chatModel = os.getenv("MODEL")
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
        conversation_history = load_user_history(user_id)
        conversation_history.append({'role': 'user', 'content': user_message})

        if len(conversation_history) > 30:
            conversation_history = conversation_history[3:]  # Удаляем по 3 первых сообщения при переполении памяти

        async_create = sync_to_async(self.chatBot.chat.completions.create, thread_sensitive=True)

        response: ChatCompletion = await async_create(model=self.chatModel, messages=conversation_history)
        model_response = f"> :robot: **Вам отвечает модель:** *{self.chatModel}* \n > :wrench: **Версия ИИ:** *{os.environ.get('VERSION_BOT')}*"
        bot_response = response.choices[0].message.content
        conversation_history.append({'role': 'assistant', 'content': bot_response})

        save_user_history(user_id, conversation_history)

        return f"{model_response}\n\n{bot_response}"

    def reset_conversation_history(self, user_id: int):
        save_user_history(user_id, [])

# Функции для работы с JSON-файлами
def get_user_data_filepath(user_id):
    return os.path.join(USER_DATA_DIR, f'{user_id}.json')

def load_user_history(user_id):
    filepath = get_user_data_filepath(user_id)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file).get('history', [])
    else:
        return []

def save_user_history(user_id, history):
    filepath = get_user_data_filepath(user_id)
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump({'history': history}, file, ensure_ascii=False, indent=4)

discordClient = discordClient()
