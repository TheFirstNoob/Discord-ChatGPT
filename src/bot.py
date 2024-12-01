import os
import re
import asyncio
import discord
import aiohttp
import mimetypes
from src.log import logger
from typing import Optional
from pdfminer.high_level import extract_text
from g4f.client import AsyncClient
from src.aclient import discordClient
from discord import app_commands, Attachment

client = AsyncClient()

async def run_discord_bot():
    @discordClient.event
    async def on_ready():
        await discordClient.send_start_prompt()
        await discordClient.tree.sync()
        loop = asyncio.get_event_loop()
        loop.create_task(discordClient.process_messages())
        logger.info(f'{discordClient.user} успешно запущена!')

    @discordClient.tree.command(name="ask", description="Задать вопрос ChatGPT")
    @app_commands.describe(
        message="Введите ваш запрос",
        request_type="Тип запроса через интернет (Поисковик, Изображение, Видео)"
    )
    @app_commands.choices(request_type=[
        app_commands.Choice(name="Поисковик", value="search"),
        app_commands.Choice(name="Изображение", value="images"),
        app_commands.Choice(name="Видео", value="videos")
    ])
    async def ask(interaction: discord.Interaction, *, message: str, request_type: Optional[str] = None):
        await interaction.response.defer(ephemeral=False)

        if interaction.user == discordClient.user:
            return

        username = str(interaction.user)
        discordClient.current_channel = interaction.channel

        user_id = interaction.user.id
        user_data = await discordClient.load_user_data(user_id)
        user_model = user_data.get('model', discordClient.default_model)

        logger.info(f"\x1b[31m{username}\x1b[0m : /ask [{message}] ({request_type or 'None'}) в ({discordClient.current_channel})")
        await discordClient.enqueue_message(interaction, message, request_type)

    @discordClient.tree.command(name="asklong", description="Задать длинный вопрос ChatGPT через текст и файл")
    @app_commands.describe(
        message="Введите ваш запрос",
        file="Загрузите текстовый файл с вашим запросом/кодом и т.п.",
        request_type="Тип запроса через интернет (Поисковик, Изображение, Видео)"
    )
    @app_commands.choices(request_type=[
        app_commands.Choice(name="Поисковик", value="search"),
        app_commands.Choice(name="Изображение", value="images"),
        app_commands.Choice(name="Видео", value="videos")
    ])
    async def asklong(interaction: discord.Interaction, message: str, file: Attachment, request_type: Optional[str] = None):
        await interaction.response.defer(ephemeral=False)

        if interaction.user == discordClient.user:
            return

        username = str(interaction.user)
        discordClient.current_channel = interaction.channel
        mime_type, _ = mimetypes.guess_type(file.filename)

        if mime_type is None or not mime_type.startswith('text/'):
            await interaction.followup.send(f"> :x: **ОШИБКА:** Поддерживаются только текстовые форматы! Загруженный файл: {file.filename}")
            return

        try:
            file_content = await file.read()
            file_message = file_content.decode('utf-8')
            message = f"{message}\n\n{file_message}"
        except Exception as e:
            logger.exception(f"asklong: Не удалось прочитать файл: {str(e)}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** Не удалось прочитать файл. Поддерживаются только текстовые форматы! {str(e)}")
            return

        logger.info(f"\x1b[31m{username}\x1b[0m : /asklong [Текст: {message}, Файл: {file.filename}] ({request_type or 'None'}) в ({discordClient.current_channel})")
        await discordClient.enqueue_message(interaction, message, request_type)

    @discordClient.tree.command(name="askpdf", description="Извлечь текст из PDF-файла и задать вопрос ИИ")
    @app_commands.describe(
        message="Введите ваш запрос к ИИ",
        file="Загрузите PDF-файл для извлечения текста"
    )
    async def askpdf(interaction: discord.Interaction, message: str, file: Attachment):
        await interaction.response.defer(ephemeral=False)

        if interaction.user == discordClient.user:
            return

        username = str(interaction.user)
        discordClient.current_channel = interaction.channel
        mime_type, _ = mimetypes.guess_type(file.filename)

        if mime_type != 'application/pdf':
            await interaction.followup.send(f"> :x: **ОШИБКА:** Поддерживается только PDF-файлы! Загруженный файл: {file.filename}")
            return

        try:
            pdf_content = await file.read()
            pdf_path = f'temp_pdf_{interaction.user.id}.pdf'
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content)

            extracted_text = extract_text(pdf_path)
            os.remove(pdf_path)

            full_message = f"{message}\n\n{extracted_text}"
            logger.info(f"\x1b[31m{username}\x1b[0m : /askpdf [Текст: {message}, PDF: {file.filename}] в ({discordClient.current_channel})")
            await discordClient.enqueue_message(interaction, full_message, request_type=None)
            
            await interaction.followup.send("> :white_check_mark: **Ваш запрос и текст из PDF отправлены на обработку! Пожалуйста ожидайте...**")
        except Exception as e:
            logger.exception(f"askpdf: Ошибка при обработке PDF-файла: {e}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** {str(e)}")

    @discordClient.tree.command(name="chat-model", description="Сменить модель чата")
    @app_commands.choices(model=[
        app_commands.Choice(name="GPT 3.5-Turbo (OpenAI)", value="gpt-3.5-turbo"),
        app_commands.Choice(name="GPT 4 (OpenAI)", value="gpt-4"),
        app_commands.Choice(name="GPT 4o-Mini (OpenAI)", value="gpt-4o-mini"),
        app_commands.Choice(name="GPT 4o (OpenAI)", value="gpt-4o"),
        app_commands.Choice(name="Claude 3 Haiku (Anthropic)", value="claude-3-haiku"),
        app_commands.Choice(name="Claude 3.5 Sonnet (Anthropic)", value="claude-3.5-sonnet"),
        app_commands.Choice(name="Blackbox", value="blackbox"),
        app_commands.Choice(name="Blackbox PRO", value="blackbox-pro"),
        app_commands.Choice(name="Gemini Flash (Google)", value="gemini-flash"),
        app_commands.Choice(name="Gemini Pro (Google)", value="gemini-pro"),
        app_commands.Choice(name="LLaMa v3.1 70B (MetaAI)", value="llama-3.1-70b"),
        app_commands.Choice(name="LLaMa v3.1 405B (MetaAI)", value="llama-3.1-405b"),
        app_commands.Choice(name="LLaMa v3.1 Sonar 128k Chat (MetaAI)", value="sonar-chat"),
        app_commands.Choice(name="Mixtral-8x7B", value="mixtral-8x7b"),
        app_commands.Choice(name="LFM 40B", value="lfm-40b"),
        app_commands.Choice(name="LLaVa 13B Vision", value="llava-13b"),
    ])
    async def chat_model(interaction: discord.Interaction, model: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        await discordClient.set_user_model(user_id, model.value)

        selected_provider = await discordClient.get_provider_for_model(model.value)
        discordClient.chatBot = AsyncClient(provider=selected_provider)

        await interaction.followup.send(f"> **ИНФО: Чат-модель изменена на: {model.name}.**")
        logger.info(f"Смена модели на {model.name} для пользователя {interaction.user}")

    @discordClient.tree.command(name="reset", description="Сброс истории запросов")
    async def reset(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        await discordClient.reset_conversation_history(user_id)
        await interaction.followup.send("> :white_check_mark: **УСПЕШНО:** Ваша история и модели ИИ сброшены!")
        logger.warning(f"\x1b[31mПользователь {interaction.user} сбросил историю.\x1b[0m")

    @discordClient.tree.command(name="help", description="Информация как пользоваться ботом")
    async def help_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        help_file_path = 'texts/help.txt'
        if not os.path.exists(help_file_path):
            await interaction.followup.send(f"> :x: **ОШИБКА:** Файл help.txt не найден! Пожалуйста, свяжитесь с {os.environ.get('ADMIN_NAME')} и сообщите ему об этой ошибке.**")
            logger.error(f"help: Файл справки не найден: {help_file_path}")
            return
        with open(help_file_path, 'r', encoding='utf-8') as file:
            help_text = file.read()
        await interaction.followup.send(help_text)
        logger.info(f"\x1b[31m{username} использовал(а) команду help!\x1b[0m")

    @discordClient.tree.command(name="about", description="Информация о боте")
    async def about_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        about_file_path = 'texts/about.txt'
        if not os.path.exists(about_file_path):
            await interaction.followup.send(f"> :x: **ОШИБКА:** Файл about.txt не найден! Пожалуйста, свяжитесь с {os.environ.get('ADMIN_NAME')} и сообщите ему об этой ошибке.**")
            logger.error(f"about: Файл информации не найден: {about_file_path}")
            return
        with open(about_file_path, 'r', encoding='utf-8') as file:
            about_text = file.read().format(username=username)
        await interaction.followup.send(about_text)
        logger.info(f"\x1b[31m{username} использовал(а) команду about!\x1b[0m")

    @discordClient.tree.command(name="changelog", description="Журнал изменений бота")
    @app_commands.choices(version=[
        app_commands.Choice(name="3.5.0", value="3.5.0"),
        app_commands.Choice(name="3.4.0", value="3.4.0"),
        app_commands.Choice(name="3.3.2", value="3.3.2"),
        app_commands.Choice(name="3.3.1", value="3.3.1"),
        app_commands.Choice(name="3.3.0", value="3.3.0"),
        app_commands.Choice(name="3.2.0", value="3.2.0"),
        app_commands.Choice(name="3.1.1", value="3.1.1"),
        app_commands.Choice(name="3.1.0", value="3.1.0"),
        app_commands.Choice(name="3.0.0", value="3.0.0"),
        app_commands.Choice(name="2.6.0", value="2.6.0"),
        app_commands.Choice(name="2.5.1", value="2.5.1"),
        app_commands.Choice(name="2.5.0", value="2.5.0"),
        app_commands.Choice(name="2.4.0", value="2.4.0"),
        app_commands.Choice(name="2.3.0", value="2.3.0"),
        app_commands.Choice(name="2.2.0", value="2.2.0"),
        app_commands.Choice(name="2.1.0", value="2.1.0"),
        app_commands.Choice(name="2.0.0", value="2.0.0"),
    ])
    async def changelog(interaction: discord.Interaction, version: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        version_file = f"texts/change_log/{version.value}.txt"
        
        if not os.path.exists(version_file):
            await interaction.followup.send(f"> :x: **ОШИБКА: Файл журнала изменений для версии {version.name} не найден! Пожалуйста, свяжитесь с {os.environ.get('ADMIN_NAME')} и сообщите ему об этой ошибке.**")
            logger.error(f"changelog: Файл журнала изменений для версии {version.name} не найден: {version_file}")
            return
        
        with open(version_file, 'r', encoding='utf-8') as file:
            changelog_text = file.read()
        
        await interaction.followup.send(changelog_text)
        logger.info(f"\x1b[31m{username} запросил(а) журнал изменений для версии {version.name} бота\x1b[0m")
        
    @discordClient.tree.command(name="history", description="Получить историю сообщений")
    async def history(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        username = str(interaction.user)

        if interaction.user == discordClient.user:
            return

        user_id = interaction.user.id
        filepath = await discordClient.download_conversation_history(user_id)

        if filepath:
            with open(filepath, 'rb') as file:
                await interaction.followup.send("> :white_check_mark: **УСПЕШНО:** Ваша история диалога:")
                await interaction.followup.send(file=discord.File(file, filename=f'{user_id}_history.json'))
        else:
            await interaction.followup.send("> :x: **ОШИБКА:** История сообщений не найдена!")
            
        logger.info(f"\x1b[31m{username} запросил(а) историю сообщений с ботом\x1b[0m")
    
    @discordClient.tree.command(name="draw", description="Сгенерировать изображение от модели ИИ")
    @app_commands.describe(
        prompt="Введите ваш запрос (На Английском языке)",
        image_model="Выберите модель для генерации изображения"
    )
    @app_commands.choices(image_model=[
        app_commands.Choice(name="Stable Diffusion XL", value="sdxl"),
        app_commands.Choice(name="Stable Diffusion v3", value="sd-3"),
        app_commands.Choice(name="Playground v2.5", value="playground-v2.5"),
        app_commands.Choice(name="FLUX Pro", value="flux"),
        app_commands.Choice(name="FLUX 4o", value="flux-4o"),
        app_commands.Choice(name="FLUX Realism", value="flux-realism"),
        app_commands.Choice(name="FLUX Anime", value="flux-anime"),
        app_commands.Choice(name="FLUX 3D", value="flux-3d"),
        app_commands.Choice(name="FLUX Disney", value="flux-disney"),
        app_commands.Choice(name="FLUX Pixel", value="flux-pixel"),
        app_commands.Choice(name="Any Dark", value="any-dark"),
    ])
    
    async def draw(interaction: discord.Interaction, prompt: str, image_model: app_commands.Choice[str]):
        if interaction.user == discordClient.user:
            return

        username = str(interaction.user)
        channel = str(interaction.channel)
        logger.info(f"\x1b[31m{username}\x1b[0m : /draw [{prompt}] в ({channel}) через [{image_model.value}]")

        try:
            await interaction.response.defer()

            response = await client.images.generate(model=image_model.value, prompt=prompt)
            print(response)

            if response.data:
                print(response.data)
                image_url = response.data[0].url

                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as image_response:
                        if image_response.status == 200:
                            image_data = await image_response.read()
                            image_path = f"temp_image_{interaction.user.id}.png"
                            with open(image_path, 'wb') as f:
                                f.write(image_data)

                            with open(image_path, 'rb') as f:
                                model_message = f":paintbrush: **Изображение от модели**: {image_model.name}"
                                await interaction.followup.send(model_message, file=discord.File(f, filename=image_path))

                            os.remove(image_path)
                        else:
                            await interaction.followup.send(f"> :x: **ОШИБКА:** Не удалось загрузить изображение. Код ошибки: {image_response.status}")
                            logger.error(f"draw: Не удалось загрузить изображение. Код ошибки: {image_response.status}")
            else:
                await interaction.followup.send("> :x: **ОШИБКА:** Не удалось сгенерировать изображение.")
                logger.error("draw: Не удалось сгенерировать изображение. Ответ не содержит данных.")
        except Exception as e:
            logger.error(f"draw: Ошибка при выполнении команды: {str(e)}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** {str(e)}")

    TOKEN = os.getenv("DISCORD_BOT_TOKEN")

    await discordClient.start(TOKEN)