import os
import re
import json
import asyncio
import discord
import requests
import base64
import uuid
from src.log import logger, setup_logger
from typing import Optional

from g4f.client import Client
from g4f.Provider import (
    RetryProvider, Chatgpt4o, FreeChatgpt, DDG, Liaobots, Blackbox, ChatGot, FreeGpt,
    HuggingChat, HuggingFace, PerplexityLabs, Pi, LiteIcoding, AiChatOnline, Pizzagpt,
    FreeNetfly, MagickPenAsk, MagickPenChat, TeachAnything, DeepInfra, ChatgptFree,
    DeepInfraImage
)

from src.aclient import discordClient
from discord import app_commands
from src import log

def run_discord_bot():
    @discordClient.event
    async def on_ready():
        await discordClient.send_start_prompt()
        await discordClient.tree.sync()
        loop = asyncio.get_event_loop()
        loop.create_task(discordClient.process_messages())
        logger.info(f'{discordClient.user} успешно запущена!')

    @discordClient.tree.command(name="ask", description="Задать вопрос ChatGPT")
    async def ask(interaction: discord.Interaction, *, message: str, additionalmessage: Optional[str] = None):
        await interaction.response.defer(ephemeral=False)

        if interaction.user == discordClient.user:
            return
        username = str(interaction.user)
        discordClient.current_channel = interaction.channel

        if additionalmessage:
            combined_message = f"{message} {additionalmessage}"
            logger.info(f"\x1b[31m{username}\x1b[0m : /ask [{combined_message}] в ({discordClient.current_channel})")
            message = combined_message

        logger.info(f"\x1b[31m{username}\x1b[0m : /ask [{message}] в ({discordClient.current_channel})")
        await discordClient.enqueue_message(interaction, message)

    @discordClient.tree.command(name="chat-model", description="Сменить модель чата")
    @app_commands.choices(model=[
        app_commands.Choice(name="GPT 3.5-Turbo", value="gpt-3.5-turbo"),
        app_commands.Choice(name="GPT 4", value="gpt-4"),
        app_commands.Choice(name="GPT 4 (0613)", value="gpt-4-0613"),
        app_commands.Choice(name="GPT 4-Turbo", value="gpt-4-turbo-2024-04-09"),
        app_commands.Choice(name="GPT 4o Mini", value="gpt-4o-mini"),
        app_commands.Choice(name="GPT 4o", value="gpt-4o"),
        app_commands.Choice(name="GPT 4o Free (Liao)", value="gpt-4o-free"),
        app_commands.Choice(name="Claude 3 Haiku", value="claude-3-haiku-20240307"),
        app_commands.Choice(name="Blackbox", value="blackbox"),
        app_commands.Choice(name="Gemini", value="Gemini-Pro"),
        app_commands.Choice(name="Command R+", value="CohereForAI/c4ai-command-r-plus"),
        app_commands.Choice(name="Pi", value="pi"),
        app_commands.Choice(name="LLaMa v3.1 70B Turbo", value="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"),
        app_commands.Choice(name="LLaMa v3.1 70B-Instruct", value="meta-llama/Meta-Llama-3.1-70B-Instruct"),
        app_commands.Choice(name="LLaMa v3.1 405B Instruct", value="meta-llama/Meta-Llama-3.1-405B-Instruct-FP8"),
        app_commands.Choice(name="LLaMa v3.1 Sonar 128k (Online)", value="llama-3.1-sonar-large-128k-online"),
        app_commands.Choice(name="LLaMa v3.1 Sonar 128k Chat", value="llama-3.1-sonar-large-128k-chat"),
        app_commands.Choice(name="Nous Hermes 2 Mixtral-8x7B-DPO", value="NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO"),
        app_commands.Choice(name="Mixtral-8x7B", value="mistralai/Mixtral-8x7B-Instruct-v0.1"),
        app_commands.Choice(name="Mixtral-7B v2", value="mistralai/Mistral-7B-Instruct-v0.2"),
        app_commands.Choice(name="Phi v3 Mini", value="microsoft/Phi-3-mini-4k-instruct"),
        app_commands.Choice(name="Yi v1.5 9B", value="Yi-1.5-9B-Chat"),
        app_commands.Choice(name="Yi v1.5 34B", value="01-ai/Yi-1.5-34B-Chat"),
        app_commands.Choice(name="SparkDesk v1.1", value="SparkDesk-v1.1"),
        app_commands.Choice(name="Qwen2 7B Instruct", value="Qwen2-7B-Instruct"),
    ])
    async def chat_model(interaction: discord.Interaction, model: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        
        # Думаю нужно уже использовать alias для некоторых моделей, лимиты дискорда уже близко...
        providers = {
            "gpt-3.5-turbo": RetryProvider([FreeChatgpt, FreeNetfly], shuffle=False),
            "gpt-4": RetryProvider([FreeNetfly], shuffle=False),
            "gpt-4-0613": RetryProvider([Liaobots], shuffle=False),
            "gpt-4-turbo-2024-04-09": RetryProvider([Liaobots], shuffle=False),
            "gpt-4o-mini": RetryProvider([Pizzagpt, AiChatOnline, ChatgptFree, DDG, Liaobots, MagickPenChat, MagickPenAsk], shuffle=False),
            "gpt-4o": RetryProvider([Chatgpt4o, Liaobots, LiteIcoding, AiChatOnline], shuffle=False),
            "gpt-4o-free": RetryProvider([Liaobots], shuffle=False),
            "claude-3-haiku-20240307": RetryProvider([DDG, Liaobots], shuffle=False),
            "blackbox": RetryProvider([Blackbox], shuffle=False),
            "Gemini-Pro": RetryProvider([ChatGot], shuffle=False),
            "CohereForAI/c4ai-command-r-plus": RetryProvider([HuggingChat, HuggingFace], shuffle=False),
            "pi": RetryProvider([Pi], shuffle=False),
            "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": RetryProvider([DDG], shuffle=False),
            "meta-llama/Meta-Llama-3.1-70B-Instruct": RetryProvider([HuggingChat, HuggingFace, Blackbox, DeepInfra, FreeGpt], shuffle=False),
            "meta-llama/Meta-Llama-3.1-405B-Instruct-FP8": RetryProvider([HuggingChat, HuggingFace, Blackbox], shuffle=False),
            "llama-3.1-sonar-large-128k-online": RetryProvider([PerplexityLabs], shuffle=False),
            "llama-3.1-sonar-large-128k-chat": RetryProvider([PerplexityLabs], shuffle=False),
            "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO": RetryProvider([HuggingChat, HuggingFace], shuffle=False),
            "mistralai/Mixtral-8x7B-Instruct-v0.1": RetryProvider([HuggingChat, DDG, HuggingFace], shuffle=False),
            "mistralai/Mistral-7B-Instruct-v0.2": RetryProvider([HuggingChat], shuffle=False),
            "microsoft/Phi-3-mini-4k-instruct": RetryProvider([HuggingChat], shuffle=False),
            "Yi-1.5-9B-Chat": RetryProvider([FreeChatgpt], shuffle=False),
            "01-ai/Yi-1.5-34B-Chat": RetryProvider([HuggingChat, HuggingFace], shuffle=False),
            "SparkDesk-v1.1": RetryProvider([FreeChatgpt], shuffle=False),
            "Qwen2-7B-Instruct": RetryProvider([FreeChatgpt], shuffle=False),
        }

        exclusive_models = []  # Если есть эксклюзивные модели, добавьте их сюда

        if model.value in exclusive_models:
            user_id = interaction.user.id

            if user_id in []:
                await interaction.followup.send(f"> **ИНФО: Вам доступна эта эксклюзивная модель, но она может быть нестабильна. Используйте на свой страх и риск!**")
            else:
                await interaction.followup.send(f"> **Ошибка: Выбранная модель в данный момент доступна только TheFirstNoob. Скорее всего он отключил ее из-за нестабильности работы или она перестала работать. Пожалуйста, воспользуйтесь другой моделью!**")
                return

        # Оно нам сейчас не надо, оставил как заплатка на текущий момент
        #user_id = interaction.user.id
        #discordClient.reset_conversation_history(user_id)
        
        selected_provider = providers.get(model.value)
        # Обновление провайдера и модели
        discordClient.chatBot = Client(provider=selected_provider)
        discordClient.chatModel = model.value

        # Вызов стартового промта при смене модели
        # Не отсылаем стартовый промпт для этих моделей из-за особенностей провайдера
        if model.value not in ["llama-3.1-sonar-large-128k-online", "llama-3.1-sonar-large-128k-chat"]:
            await discordClient.send_start_prompt()

        await interaction.followup.send(f"> **ИНФО: Чат-модель изменена на: {model.name}.**")

        if model.value == "Gemini-Pro":
            await interaction.followup.send("> :warning: **Провайдеры этой модели могут быть нестабильны и могут отваливаться!**")
        if model.value == "claude-3-haiku-20240307":
            await interaction.followup.send("> :warning: **Провайдер этой модели не поддерживает историю общения и не имеет памяти. Это особенность провайдера, а не моя ошибка!**")
        if model.value == "meta-llama/Meta-Llama-3.1-405B-Instruct-FP8":
            await interaction.followup.send("> :warning: **Генерация ответов от этой модели может быть долгой. Данная модель требует больших ресурсов для генерации!**")
        if model.value == "pi":
            await interaction.followup.send("> :warning: **Ответы от этой модели могут долго приходить, провайдеру нужно что-то типо проснуться для инициализации!**")
        if model.value == "llama-3.1-sonar-large-128k-online":
            await interaction.followup.send("> :warning: **Эта модель имеет доступ в интернет для поиска, но не поддерживает контекст диалога и, вроде как, не имеет памяти!**")
            await interaction.followup.send("> :warning: **Эта модель пока что работает нестабильно :с**")

        logger.info(f"Смена модели на {model.name} для пользователя {interaction.user}")

    @discordClient.tree.command(name="reset", description="Сброс истории запросов")
    async def reset(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        user_id = interaction.user.id
        discordClient.reset_conversation_history(user_id)
        await discordClient.send_start_prompt()
        await interaction.followup.send("> **ИНФО: Сброс выполнен в вашей сессии!**")
        logger.warning(f"\x1b[31mПользователь {interaction.user} сбросил историю.\x1b[0m")

    @discordClient.tree.command(name="help", description="Информация как пользоваться Hitagi ChatGPT")
    async def help_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        help_file_path = 'texts/help.txt'
        if not os.path.exists(help_file_path):
            await interaction.followup.send("> **Ошибка:** Файл справки не найден! Пожалуйста, свяжитесь с TheFirstNoob и сообщите ему об этой ошибке.**")
            logger.error(f"Файл справки не найден: {help_file_path}")
            return
        with open(help_file_path, 'r', encoding='utf-8') as file:
            help_text = file.read()
        await interaction.followup.send(help_text)
        logger.info(f"\x1b[31m{username} использовал(а) команду help!\x1b[0m")
        
    @discordClient.tree.command(name="info", description="Информация о боте")
    async def info_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        info_file_path = 'texts/info.txt'
        if not os.path.exists(info_file_path):
            await interaction.followup.send("> **Ошибка:** Файл информации не найден! Пожалуйста, свяжитесь с TheFirstNoob и сообщите ему об этой ошибке, возможно он еще не добавил информацию об этой моделе.**")
            logger.error(f"Файл информации не найден: {info_file_path}")
            return
        with open(info_file_path, 'r', encoding='utf-8') as file:
            info_text = file.read().format(username=username)
        await interaction.followup.send(info_text)
        logger.info(f"\x1b[31m{username} использовал(а) команду info!\x1b[0m")
        
    @discordClient.tree.command(name="modelinfo", description="Информация о моделях чата")
    @app_commands.choices(model=[
        app_commands.Choice(name="Blackbox", value="blackbox"),
        app_commands.Choice(name="Gemini", value="Gemini-Pro"),
        app_commands.Choice(name="Mixtral 8x7B", value="Mixtral-8x7B-Instruct-v0.1"),
        app_commands.Choice(name="Mixtral 7B v2", value="Mistral-7B-Instruct-v0.2"),
        app_commands.Choice(name="Command R+", value="c4ai-command-r-plus"),
        app_commands.Choice(name="LLaMa v3 70B", value="Meta-Llama-3-70B-Instruct"),
        app_commands.Choice(name="Phi v3 Mini", value="Phi-3-mini-4k-instruct"),
        app_commands.Choice(name="Yi v1.5 34B", value="Yi-1.5-34B-Chat"),
        # Добавьте другие модели и их названия здесь
    ])
    async def modelinfo(interaction: discord.Interaction, model: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        model_name = model.name
        model_file = f"texts/model_info/{re.sub(r'[^a-zA-Z0-9_]', '_', model_name.lower())}.txt"
        
        if not os.path.exists(model_file):
            await interaction.followup.send(f"> **Ошибка: Файл описания для модели {model_name} не найден!**")
            logger.error(f"Файл описания для модели {model_name} не найден: {model_file}")
            return
        
        with open(model_file, 'r', encoding='utf-8') as file:
            model_info = file.read()
        
        await interaction.followup.send(model_info)
        logger.info(f"\x1b[31m{username} запросил(а) информацию о модели {model_name}\x1b[0m")
        
    @discordClient.tree.command(name="changelog", description="Журнал изменений бота")
    @app_commands.choices(version=[
        app_commands.Choice(name="3.0.0", value="3.0.0"),
        app_commands.Choice(name="2.6.0", value="2.6.0"),
        app_commands.Choice(name="2.5.1", value="2.5.1"),
        app_commands.Choice(name="2.5.0", value="2.5.0"),
        app_commands.Choice(name="2.4.0", value="2.4.0"),
        app_commands.Choice(name="2.3.0", value="2.3.0"),
        app_commands.Choice(name="2.2.0", value="2.2.0"),
        app_commands.Choice(name="2.1.0", value="2.1.0"),
        app_commands.Choice(name="2.0.0", value="2.0.0"),
        # Добавьте другие версии и их названия здесь
    ])
    async def changelog(interaction: discord.Interaction, version: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        version_file = f"texts/change_log/{version.value}.txt"
        
        if not os.path.exists(version_file):
            await interaction.followup.send(f"> **Ошибка: Файл журнала изменений для версии {version.name} не найден!**")
            logger.error(f"Файл журнала изменений для версии {version.name} не найден: {version_file}")
            return
        
        with open(version_file, 'r', encoding='utf-8') as file:
            changelog_text = file.read()
        
        await interaction.followup.send(changelog_text)
        logger.info(f"\x1b[31m{username} запросил(а) журнал изменений для версии {version.name} бота\x1b[0m")

    @discordClient.tree.command(name="draw", description="Сгенерировать изображение от модели ИИ")
    @app_commands.describe(prompt="Описание изображения", service="Выберите сервис", height="Высота изображения", width="Ширина изображения")
    @app_commands.choices(service=[
        app_commands.Choice(name="SDXL DeepInfra", value="sdxl"),
        app_commands.Choice(name="FLUX DeepInfra", value="flux"),
    ])
    async def draw(interaction: discord.Interaction, prompt: str, service: app_commands.Choice[str], height: Optional[int] = 1024, width: Optional[int] = 1024):
        if service.value == "flux":
            # Проверка для модели FLUX
            if height is None or width is None or height < 256 or height > 1440 or width < 256 or width > 1440:
                await interaction.response.send_message("**Ошибка:** Высота и ширина изображения для модели FLUX поддерживают от 256 до 1440 пикселей. Мы установили стандартное значение 1024 на 1024, чтобы вы все равно могли посмотреть результат.")
                height = 1024
                width = 1024

        else:
            # Проверка для других моделей
            if height is not None and (height < 128 or height > 1920) or width is not None and (width < 128 or width > 1920):
                await interaction.response.send_message("**Ошибка:** Высота и ширина изображения для данной модели поддерживают от 128 до 1920 пикселей. Мы установили стандартное значение 1024 на 1024, чтобы вы все равно могли посмотреть результат.")
                height = 1024
                width = 1024
            if (height is not None and height % 8 != 0) or (width is not None and width % 8 != 0):
                await interaction.response.send_message("**Ошибка:** Высота и Ширина изображения должны быть кратны/делимы на 8.")
                return

        if interaction.user == discordClient.user:
            return

        username = str(interaction.user)
        channel = str(interaction.channel)
        logger.info(f"\x1b[31m{username}\x1b[0m : /draw [{prompt}] в ({channel}) через [{service.value}]")

        await interaction.response.defer(thinking=True)

        image_url = None
        try:
            headers = {
                "Authorization": f"Bearer {os.environ.get('DEEPINFRA_API_KEY')}"
            }

            # Используем URL изображения в ответе
            if service.value == "sdxl":
                model = "stability-ai/sdxl"
                data = {
                    "input": {
                        "prompt": prompt,
                        "height": height,
                        "width": width
                    }
                }
                response = requests.post('https://api.deepinfra.com/v1/inference/stability-ai/sdxl', json=data, headers=headers)
                response.raise_for_status()

                response_json = response.json()
                if "error" in response_json and response_json["error"]:
                    error_message = response_json["error"]
                    await interaction.followup.send(f"**Ошибка:** {error_message}")
                else:
                    image_urls = response_json.get("output", [])
                    if image_urls:
                        image_url = image_urls[0]
                        await interaction.followup.send(image_url)

            # Используем base64 в ответе
            elif service.value == "flux":
                model = "black-forest-labs/FLUX-1-schnell"
                data = {
                    'prompt': prompt,
                }
                response = requests.post('https://api.deepinfra.com/v1/inference/black-forest-labs/FLUX-1-schnell', headers=headers, json=data)
                response.raise_for_status()

                response_json = response.json()
                if "error" in response_json and response_json["error"]:
                    error_message = response_json["error"]
                    await interaction.followup.send(f"**Ошибка:** {error_message}")
                else:
                    image_urls = response_json.get("images", [])
                    if image_urls:
                        base64_image = image_urls[0].split(",")[1]
                        image_data = base64.b64decode(base64_image)

                        # Генерация уникального имени файла
                        unique_filename = f'generated_image_{uuid.uuid4().hex}.png'
                        image_path = unique_filename
                        with open(image_path, 'wb') as image_file:
                            image_file.write(image_data)
                        await interaction.followup.send(file=discord.File(image_path))

                        # Удаление файла после отправки
                        os.remove(image_path)
                    else:
                        await interaction.followup.send("**Ошибка:** Изображение не было сгенерировано.")

        except Exception as err:
            await interaction.followup.send(f'> **Ошибка:** {err}')
            logger.error(f"\x1b[31m{username}\x1b[0m : {err}")

    TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    discordClient.run(TOKEN)
