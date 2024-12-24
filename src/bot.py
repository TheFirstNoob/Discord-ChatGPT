import os
import re
import base64
import asyncio
import discord
import aiohttp
import mimetypes
from datetime import datetime, timedelta
from src.log import logger
from typing import Optional
from pdfminer.high_level import extract_text
from g4f.client import AsyncClient
from src.aclient import discordClient
from src.aclient import load_reminders, save_reminders
from discord import app_commands, Attachment
from g4f.Provider import Prodia

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
        app_commands.Choice(name="o1 Mini (OpenAI)", value="o1-mini"),
        app_commands.Choice(name="Claude 3 Haiku (Anthropic)", value="claude-3-haiku"),
        app_commands.Choice(name="Claude 3.5 Sonnet (Anthropic)", value="claude-3.5-sonnet"),
        app_commands.Choice(name="Blackbox (Blackbox AI)", value="blackboxai"),
        app_commands.Choice(name="Blackbox PRO (Blackbox AI)", value="blackboxai-pro"),
        app_commands.Choice(name="Gemini Flash (Google)", value="gemini-flash"),
        app_commands.Choice(name="Gemini Pro (Google)", value="gemini-pro"),
        app_commands.Choice(name="LLaMa v3.1 70B (MetaAI)", value="llama-3.1-70b"),
        app_commands.Choice(name="LLaMa v3.3 70B (MetaAI)", value="llama-3.3-70b"),
        app_commands.Choice(name="LLaMa v3.1 405B (MetaAI)", value="llama-3.1-405b"),
        app_commands.Choice(name="QwQ 32B Preview (Qwen Team)", value="qwq-32b"),
        app_commands.Choice(name="DeepSeek LLM 67B (DeepSeek AI)", value="deepseek-chat"),
        app_commands.Choice(name="Mixtral-8x7B (Mistral)", value="mixtral-8x7b"),
        app_commands.Choice(name="LFM 40B (Liquid)", value="lfm-40b"),
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
        app_commands.Choice(name="4.0.0", value="4.0.0"),
        app_commands.Choice(name="3.5.1", value="3.5.1"),
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
        app_commands.Choice(name="FLUX Pro", value="flux-pro"),
        app_commands.Choice(name="FLUX 4o", value="flux-4o"),
        app_commands.Choice(name="FLUX Realism", value="flux-realism"),
        app_commands.Choice(name="FLUX Anime", value="flux-anime"),
        app_commands.Choice(name="FLUX 3D", value="flux-3d"),
        app_commands.Choice(name="FLUX Disney", value="flux-disney"),
        app_commands.Choice(name="FLUX Pixel", value="flux-pixel"),
        app_commands.Choice(name="Midjourney", value="midjourney"),
        app_commands.Choice(name="Dall-E V3", value="dall-e-3"),
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

            response = await client.images.generate(model=image_model.value, prompt=prompt, response_format="b64_json")

            if response.data:
                base64_text = response.data[0].b64_json
                image_data = base64.b64decode(base64_text)
                image_path = f"temp_image_{interaction.user.id}.png"

                with open(image_path, 'wb') as f:
                    f.write(image_data)

                with open(image_path, 'rb') as f:
                    model_message = f":paintbrush: **Изображение от модели**: {image_model.name}"
                    await interaction.followup.send(model_message, file=discord.File(f, filename=image_path))

                os.remove(image_path)
            else:
                await interaction.followup.send("> :x: **ОШИБКА:** Не удалось сгенерировать изображение.")
                logger.error("draw: Не удалось сгенерировать изображение. Ответ не содержит данных.")
        except Exception as e:
            logger.error(f"draw: Ошибка при выполнении команды: {str(e)}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** {str(e)}")
            
    @discordClient.tree.command(name="draw-prodia", description="Сгенерировать изображение от модели ИИ с использованием Prodia")
    @app_commands.describe(
        prompt="Введите ваш запрос (На Английском языке)",
        image_model="Выберите модель для генерации изображения"
    )
    @app_commands.choices(image_model=[
        app_commands.Choice(name="3 Guofeng3 v3.4", value="3Guofeng3_v34.safetensors [50f420de]"),
        app_commands.Choice(name="Absolute Reality v1.8.1", value="absolutereality_v181.safetensors [3d9d4d2b]"),
        app_commands.Choice(name="Am I Real v4.1", value="amIReal_V41.safetensors [0a8a2e61]"),
        app_commands.Choice(name="Anything v5", value="anythingV5_PrtRE.safetensors [893e49b9]"),
        app_commands.Choice(name="Blazing Drive v10g", value="blazing_drive_v10g.safetensors [ca1c1eab]"),
        app_commands.Choice(name="Cetus Mix v3.5", value="cetusMix_Version35.safetensors [de2f2560]"),
        app_commands.Choice(name="Childrens Stories 3D", value="childrensStories_v13D.safetensors [9dfaabcb]"),
        app_commands.Choice(name="Childrens Stories Semi-Real", value="childrensStories_v1SemiReal.safetensors [a1c56dbb]"),
        app_commands.Choice(name="Childrens Stories Toon-Anime", value="childrensStories_v1ToonAnime.safetensors [2ec7b88b]"),
        app_commands.Choice(name="CuteYukimix MidChapter3", value="cuteyukimixAdorable_midchapter3.safetensors [04bdffe6]"),
        app_commands.Choice(name="Cyber Realistic v3.3", value="cyberrealistic_v33.safetensors [82b0d085]"),
        app_commands.Choice(name="Dalcefo v4", value="dalcefo_v4.safetensors [425952fe]"),
        app_commands.Choice(name="DreamLike Anime v1.0", value="dreamlike-anime-1.0.safetensors [4520e090]"),
        app_commands.Choice(name="DreamLike Diffusion v1.0", value="dreamlike-diffusion-1.0.safetensors [5c9fd6e0]"),
        app_commands.Choice(name="DreamLike Photoreal v2.0", value="dreamlike-photoreal-2.0.safetensors [fdcf65e7]"),
        app_commands.Choice(name="Dreamshaper v8", value="dreamshaper_8.safetensors [9d40847d]"),
        app_commands.Choice(name="Eimis Anime Diffusion v1.0", value="EimisAnimeDiffusion_V1.ckpt [4f828a15]"),
        app_commands.Choice(name="Elldreth`s Vivid", value="elldreths-vivid-mix.safetensors [342d9d26]"),
        app_commands.Choice(name="EpicPhotoGasm x Plus Plus", value="epicphotogasm_xPlusPlus.safetensors [1a8f6d35]"),
        app_commands.Choice(name="EpicRealism Natural Sin RC1", value="epicrealism_naturalSinRC1VAE.safetensors [90a4c676]'"),
        app_commands.Choice(name="EpicRealism Pure Evolution V3", value="epicrealism_pureEvolutionV3.safetensors [42c8440c]"),
        app_commands.Choice(name="I Cant Believe Its Not Photography Seco", value="ICantBelieveItsNotPhotography_seco.safetensors [4e7a3dfd]"),
        app_commands.Choice(name="Openjourney V4", value="openjourney_V4.ckpt [ca2f377f]"),
        app_commands.Choice(name="Pastel Mix Stylized Anime", value="pastelMixStylizedAnime_pruned_fp16.safetensors [793a26e8]"),
        app_commands.Choice(name="Realistic Vision V5.1", value="Realistic_Vision_V5.1.safetensors [a0f13c83]"),
    ])
    async def draw_prodia(interaction: discord.Interaction, prompt: str, image_model: app_commands.Choice[str]):
        if interaction.user == discordClient.user:
            return

        username = str(interaction.user)
        channel = str(interaction.channel)
        logger.info(f"\x1b[31m{username}\x1b[0m : /draw-prodia [{prompt}] в ({channel}) через [{image_model.name}]")

        try:
            await interaction.response.defer()

            prodia_client = AsyncClient(image_provider=Prodia)
            response = await prodia_client.images.generate(model=image_model.value, prompt=prompt, response_format="b64_json")

            if response.data:
                base64_text = response.data[0].b64_json
                image_data = base64.b64decode(base64_text)
                image_path = f"temp_image_{interaction.user.id}.png"

                with open(image_path, 'wb') as f:
                    f.write(image_data)

                with open(image_path, 'rb') as f:
                    model_message = f":paintbrush: **Изображение Prodia от модели**: {image_model.name}"
                    await interaction.followup.send(model_message, file=discord.File(f, filename=image_path))

                os.remove(image_path)
            else:
                await interaction.followup.send("> :x: **ОШИБКА:** Не удалось сгенерировать изображение.")
                logger.error("draw-prodia: Не удалось сгенерировать изображение. Ответ не содержит данных.")
        except Exception as e:
            logger.error(f"draw-prodia: Ошибка при выполнении команды: {str(e)}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** {str(e)}")

    @discordClient.tree.command(name="remind-add", description="Создать напоминание")
    @app_commands.describe(
        day="День (1-31)",
        month="Месяц (1-12)",
        year="Год (например, 2023)",
        hour="Часы (0-23)",
        minute="Минуты (0-59)",
        offset="Часовое смещение от времени МСК (например, +3 или -7)",
        message="Сообщение напоминания"
    )
    async def remind(
        interaction: discord.Interaction,
        day: int,
        month: int,
        year: int,
        hour: int,
        minute: int,
        offset: int,
        message: str
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        username = str(interaction.user)
        reminders = await load_reminders(user_id)

        try:
            reminder_time = datetime(year, month, day, hour, minute)
            reminder_time = reminder_time + timedelta(hours=offset)

            if reminder_time < datetime.now():
                await interaction.followup.send("> :x: **ОШИБКА:** Вы не можете установить напоминание на время в прошлом.")
                return

            reminders.append({"time": reminder_time.isoformat(), "message": message})
            await save_reminders(user_id, reminders)
            await interaction.followup.send(f"> :white_check_mark: **Напоминание установлено на {reminder_time.strftime('%Y-%m-%d %H:%M')}!** \n Вы получите сообщение от меня когда настанет требуемое время :wink:")
            logger.info(f"\x1b[31m{username} установил себе напоминание\x1b[0m")
        except ValueError as ve:
            logger.exception(f" remind: Ошибка при установке напоминания: {str(ve)}")
            await interaction.followup.send("> :x: **ОШИБКА:** Неверный формат времени. Пожалуйста, убедитесь, что все значения корректны.")
        except Exception as e:
            logger.exception(f" remind: Ошибка при установке напоминания: {str(e)}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** {str(e)}")

    @discordClient.tree.command(name="remind-list", description="Показать все ваши напоминания")
    async def show_reminders(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        reminders = await load_reminders(user_id)

        if not reminders:
            await interaction.followup.send("> :warning: **У вас нет активных напоминаний.**")
            return

        reminder_list = "\n".join([f"{index + 1}. {reminder['time']} - {reminder['message']}" for index, reminder in enumerate(reminders)])
        await interaction.followup.send(f"> :page_with_curl: **Список напоминаний:**\n{reminder_list}")
        logger.info(f"\x1b[31m{username} запросил список своих напоминаний\x1b[0m")

    @discordClient.tree.command(name="remind-delete", description="Удалить напоминание")
    @app_commands.describe(index="Индекс напоминания для удаления")
    async def delete_reminder(interaction: discord.Interaction, index: int):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        reminders = await load_reminders(user_id)

        if index < 1 or index > len(reminders):
            await interaction.followup.send("> :x: **ОШИБКА:** Неверный индекс напоминания.")
            return

        reminders.pop(index - 1)
        await save_reminders(user_id, reminders)
        await interaction.followup.send(f"> :white_check_mark: **Напоминание удалено!**")
        logger.info(f"\x1b[31m{username} удалил напомнание\x1b[0m")

    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    await discordClient.start(TOKEN)
