import os
import re
import json
import base64
import asyncio
import aiohttp
import aiofiles
import mimetypes
import fitz  # PyMuPDF

import discord
from discord import app_commands, Attachment

from datetime import datetime, timedelta
from typing import Optional

# local
from src.locale_manager import locale_manager as lm # For locale later
from src.log import logger
from src.aclient import discordClient
from utils.files_utils import read_file, write_file
from utils.reminder_utils import reminder_manager
from utils.ban_utils import ban_manager

# g4f
from g4f.client import AsyncClient

client = AsyncClient()

async def run_discord_bot():
    @discordClient.event
    async def on_ready():
        await discordClient.send_start_prompt()
        await discordClient.tree.sync()
        logger.info(f'{discordClient.user} успешно запущена!')

    @discordClient.tree.command(name="ask", description=lm.get('ask_description'))
    @app_commands.describe(
        message=lm.get('message_describe'),
        request_type=lm.get('request_type_describe')
    )
    @app_commands.choices(request_type=[
        app_commands.Choice(name=lm.get('request_type_search_name'), value="search"),
        app_commands.Choice(name=lm.get('request_type_images_name'), value="images"),
        app_commands.Choice(name=lm.get('request_type_videos_name'), value="videos")
    ])
    async def ask(
        interaction: discord.Interaction,
        *,
        message: str,
        request_type: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=False)

        is_banned = await ban_manager.check_ban_and_respond(interaction)
        if is_banned:
            return

        if interaction.user == discordClient.user:
            return

        username = str(interaction.user)
        discordClient.current_channel = interaction.channel

        user_id = interaction.user.id
        user_data = await discordClient.load_user_data(user_id)
        user_model = user_data.get('model', discordClient.default_model)

        logger.info(f"\x1b[31m{username}\x1b[0m : /ask [{message}] ({request_type or 'None'}) в ({discordClient.current_channel})")
        asyncio.create_task(discordClient.send_message(interaction, message, request_type))

    @discordClient.tree.command(name="asklong", description=lm.get('asklong_description'))
    @app_commands.describe(
        message=lm.get('message_describe'),
        file=lm.get('asklong_file_describe'),
        request_type=lm.get('request_type_describe')
    )
    @app_commands.choices(request_type=[
        app_commands.Choice(name=lm.get('request_type_search_name'), value="search"),
        app_commands.Choice(name=lm.get('request_type_images_name'), value="images"),
        app_commands.Choice(name=lm.get('request_type_videos_name'), value="videos")
    ])
    async def asklong(
        interaction: discord.Interaction,
        message: str,
        file: Attachment,
        request_type: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=False)

        is_banned = await ban_manager.check_ban_and_respond(interaction)
        if is_banned:
            return

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
        asyncio.create_task(discordClient.send_message(interaction, message, request_type))

    @discordClient.tree.command(name="askpdf", description="Извлечь текст из PDF-файла и задать вопрос ИИ")
    @app_commands.describe(
        message="Введите ваш запрос",
        file="Загрузите PDF-файл для извлечения текста"
    )
    async def askpdf(
        interaction: discord.Interaction,
        message: str,
        file: Attachment
    ):
        await interaction.response.defer(ephemeral=False)

        is_banned = await ban_manager.check_ban_and_respond(interaction)
        if is_banned:
            return

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

            doc = fitz.open(pdf_path)
            extracted_text = ""
            for page in doc:
                extracted_text += page.get_text()

            doc.close()
            os.remove(pdf_path)

            full_message = f"{message}\n\n{extracted_text}"
            logger.info(f"\x1b[31m{username}\x1b[0m : /askpdf [Текст: {message}, PDF: {file.filename}] в ({discordClient.current_channel})")
            asyncio.create_task(discordClient.send_message(interaction, full_message, request_type=None))

        except Exception as e:
            logger.exception(f"askpdf: Ошибка при обработке PDF-файла: {e}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** {str(e)}")

    @discordClient.tree.command(name="chat-model", description="Сменить модель чата")
    @app_commands.choices(model=[
        app_commands.Choice(name="GPT 4o-Mini (OpenAI)", value="gpt-4o-mini"),
        app_commands.Choice(name="GPT 4o (OpenAI)", value="gpt-4o"),
        app_commands.Choice(name="o3-Mini low (OpenAI)", value="o3-mini-low"),
        app_commands.Choice(name="o3-Mini (OpenAI)", value="o3-mini"),
        #app_commands.Choice(name="Claude 3.5 Sonnet (Anthropic)", value="claude-3.5-sonnet"),
        app_commands.Choice(name="Blackbox (Blackbox AI)", value="blackboxai"),
        app_commands.Choice(name="Gemini 1.5 Flash (Google)", value="gemini-1.5-flash"),
        app_commands.Choice(name="Gemini 2.0 Flash (Google)", value="gemini-2.0-flash"),
        app_commands.Choice(name="Gemini 2.0 Flash Thinking (Google)", value="gemini-2.0-flash-thinking"),
        #app_commands.Choice(name="Gemini 1.5 Pro (Google)", value="gemini-pro"),
        app_commands.Choice(name="Command R+ (Cohere)", value="command-r-plus"),
        app_commands.Choice(name="Command R7B+ (Cohere)", value="command-r7b-12-2024"),
        app_commands.Choice(name="LLaMa v3.1 405B (MetaAI)", value="llama-3.1-405b"),
        app_commands.Choice(name="LLaMa v3.2 11B Vision (MetaAI)", value="llama-3.2-11b"),
        app_commands.Choice(name="LLaMa v3.3 70B (MetaAI)", value="llama-3.3-70b"),
        app_commands.Choice(name="QwQ 32B Thinking (Qwen Team)", value="qwq-32b"),
        app_commands.Choice(name="QvQ 72B Vision (Qwen Team)", value="qwen-qvq-72b-preview"),
        app_commands.Choice(name="Qwen 2.5 72B (Qwen Team)", value="qwen-2.5-72b"),
        app_commands.Choice(name="Qwen 2.5 Coder 32B (Qwen Team)", value="qwen-2.5-coder-32b"),
        app_commands.Choice(name="DeepSeek LLM 67B (DeepSeek AI)", value="deepseek-chat"),
        app_commands.Choice(name="DeepSeek v3 (DeepSeek AI)", value="deepseek-v3"),
        app_commands.Choice(name="DeepSeek R1 Thinking (DeepSeek AI)", value="deepseek-r1"),
        app_commands.Choice(name="Nemotron 70B Llama (Nvidia)", value="nemotron-70b"),
        app_commands.Choice(name="GLM-4 230B (GLM Team)", value="glm-4"),
        app_commands.Choice(name="Mixtral-8x7B (Mistral)", value="mixtral-8x7b"),
        app_commands.Choice(name="Phi 3.5 Mini (Microsoft)", value="phi-3.5-mini"),
    ])
    async def chat_model(
        interaction: discord.Interaction,
        model: app_commands.Choice[str]
    ):
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        await discordClient.set_user_model(user_id, model.value)

        selected_provider = await discordClient.get_provider_for_model(model.value)
        discordClient.chatBot = AsyncClient(provider=selected_provider)

        await interaction.followup.send(f"> :white_check_mark: **УСПЕШНО:** Чат-модель изменена на: **{model.name}**")
        logger.info(f"Смена модели на {model.name} для пользователя {interaction.user}")

    @discordClient.tree.command(name="instruction-set", description="Установить инструкцию для ИИ")
    @app_commands.describe(instruction="Инструкция для ИИ")
    async def instruction_set(interaction: discord.Interaction, instruction: str):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        await discordClient.set_user_instruction(user_id, instruction)
        await interaction.followup.send("> :white_check_mark: **УСПЕШНО:** Инструкция установлена!")
        logger.info(f"Пользователь {interaction.user} установил инструкцию.")

    @discordClient.tree.command(name="instruction-reset", description="Сбросить инструкцию для ИИ")
    async def instruction_reset(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        await discordClient.reset_user_instruction(user_id)
        await interaction.followup.send("> :white_check_mark: **УСПЕШНО:** Инструкция сброшена!")
        logger.info(f"Пользователь {interaction.user} сбросил инструкцию.")

    @discordClient.tree.command(name="reset", description="Сброс всех параметров и истории диалога")
    async def reset(
        interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        await discordClient.reset_conversation_history(user_id)
        await discordClient.reset_user_instruction(user_id)
        await interaction.followup.send("> :white_check_mark: **УСПЕШНО:** Ваша история и параметры ИИ сброшены!")
        logger.warning(f"\x1b[31mПользователь {interaction.user} сбросил историю и параметры ИИ.\x1b[0m")

    @discordClient.tree.command(name="help", description="Информация как пользоваться ботом")
    async def help_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        help_file_path = 'texts/help.txt'
        
        help_text = await read_file(help_file_path)
        if not help_text:
            await interaction.followup.send(f"> :x: **ОШИБКА:** Файл help.txt не найден! Пожалуйста, свяжитесь с {os.environ.get('ADMIN_NAME')} и сообщите ему об этой ошибке.**")
            logger.error(f"help: Файл справки не найден: {help_file_path}")
            return

        await interaction.followup.send(help_text)
        logger.info(f"\x1b[31m{username} использовал(а) команду help!\x1b[0m")

    @discordClient.tree.command(name="about", description="Информация о боте")
    async def about_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        about_file_path = 'texts/about.txt'

        about_text = await read_file(about_file_path)
        if not about_text:
            await interaction.followup.send(f"> :x: **ОШИБКА:** Файл about.txt не найден! Пожалуйста, свяжитесь с {os.environ.get('ADMIN_NAME')} и сообщите ему об этой ошибке.**")
            logger.error(f"about: Файл информации не найден: {about_file_path}")
            return

        about_text = about_text.format(username=username)
        await interaction.followup.send(about_text)
        logger.info(f"\x1b[31m{username} использовал(а) команду about!\x1b[0m")

    @discordClient.tree.command(name="changelog", description="Журнал изменений бота")
    @app_commands.choices(version=[
        app_commands.Choice(name="4.4.0", value="4.4.0"),
        app_commands.Choice(name="4.3.0", value="4.3.0"),
        app_commands.Choice(name="4.2.0", value="4.2.0"),
        app_commands.Choice(name="4.1.0", value="4.1.0"),
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
        
        changelog_text = await read_file(version_file)
        if not changelog_text:
            await interaction.followup.send(f"> :x: **ОШИБКА: Файл журнала изменений для версии {version.name} не найден! Пожалуйста, свяжитесь с {os.environ.get('ADMIN_NAME')} и сообщите ему об этой ошибке.**")
            logger.error(f"changelog: Файл журнала изменений для версии {version.name} не найден: {version_file}")
            return
        
        await interaction.followup.send(changelog_text)
        logger.info(f"\x1b[31m{username} запросил(а) журнал изменений для версии {version.name} бота\x1b[0m")
        
    @discordClient.tree.command(name="history", description="Получить историю сообщений")
    async def history(
        interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=False)
        username = str(interaction.user)

        if interaction.user == discordClient.user:
            return

        user_id = interaction.user.id

        try:
            user_data = await discordClient.load_user_data(user_id)
            
            if not user_data or not user_data.get('history'):
                await interaction.followup.send("> :x: **ОШИБКА:** История сообщений пуста!")
                return

            temp_filepath = f'temp_history_{user_id}.json'

            async with aiofiles.open(temp_filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(user_data, ensure_ascii=False, indent=4))

            try:
                with open(temp_filepath, 'rb') as file:
                    await interaction.followup.send(
                        "> :white_check_mark: **УСПЕШНО:** Ваша история диалога:", 
                        file=discord.File(file, filename=f'{user_id}_history.json')
                    )
            except Exception as e:
                logger.error(f"history: Ошибка при отправке файла: {e}")
                await interaction.followup.send(f"> :x: **ОШИБКА:** Не удалось отправить файл. {e}")

            os.remove(temp_filepath)

            logger.info(f"\x1b[31m{username} запросил(а) историю сообщений с ботом\x1b[0m")

        except Exception as e:
            logger.error(f"history: Критическая ошибка: {e}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** Не удалось получить историю. {e}")
    

    async def generate_and_send_image(
        interaction: discord.Interaction, 
        prompt: str, 
        image_model: str, 
        model_name: str, 
        count: int = 1
    ):
        try:
            await interaction.response.defer()

            images_data = []
            for _ in range(count):
                response = await client.images.generate(model=image_model, prompt=prompt, response_format="b64_json")

                if response.data:
                    base64_text = response.data[0].b64_json
                    image_data = base64.b64decode(base64_text)
                    image_path = f"temp_image_{interaction.user.id}_{len(images_data)}.png"

                    with open(image_path, 'wb') as f:
                        f.write(image_data)
    
                    images_data.append(image_path)
                else:
                    await interaction.followup.send("> :x: **ОШИБКА:** Не удалось сгенерировать изображение. Ответ не содержит данных.")
                    logger.error(f"generate_and_send_image: Не удалось сгенерировать изображение. Ответ не содержит данных.")

            if images_data:
                if count > 1:
                    files = [discord.File(image_path, filename=f"image_{i+1}.png") for i, image_path in enumerate(images_data)]
                    model_message = f":paintbrush: **Изображения от модели**: {model_name}"
                    await interaction.followup.send(model_message, files=files)
                else:
                    with open(images_data[0], 'rb') as f:
                        model_message = f":paintbrush: **Изображение от модели**: {model_name}"
                        await interaction.followup.send(model_message, file=discord.File(f, filename=images_data[0]))
                for image_path in images_data:
                    os.remove(image_path)
            else:
                await interaction.followup.send("> :x: **ОШИБКА:** Не удалось сгенерировать ни одного изображения.")
                logger.error(f"generate_and_send_image: Не удалось сгенерировать изображения.")

        except Exception as e:
            logger.error(f"generate_and_send_image: Ошибка при выполнении: {str(e)}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** {str(e)}")

    @discordClient.tree.command(name="draw", description="Сгенерировать изображение от модели ИИ")
    @app_commands.describe(
        prompt="Введите ваш запрос (На Английском языке)",
        image_model="Выберите модель для генерации изображения",
        count="Количество изображений для генерации (необязательно, по умолчанию - 1)"
    )
    @app_commands.choices(image_model=[
        app_commands.Choice(name="Stable Diffusion XL", value="sdxl-turbo"),
        app_commands.Choice(name="Stable Diffusion v3.5", value="sd-3.5"),
        app_commands.Choice(name="FLUX", value="flux"),
        app_commands.Choice(name="FLUX Pro", value="flux-pro"),
        app_commands.Choice(name="FLUX Dev", value="flux-dev"),
        app_commands.Choice(name="FLUX Realism", value="flux-realism"),
        app_commands.Choice(name="FLUX Schnell", value="flux-schnell"),
        app_commands.Choice(name="Midjourney", value="midjourney"),
        app_commands.Choice(name="Dall-E V3", value="dall-e-3"),
    ])
    @app_commands.choices(count=[
        app_commands.Choice(name="1", value=1),
        app_commands.Choice(name="2", value=2),
        app_commands.Choice(name="3", value=3),
        app_commands.Choice(name="4", value=4),
    ])
    async def draw(
        interaction: discord.Interaction,
        prompt: str,
        image_model: app_commands.Choice[str],
        count: Optional[int] = 1
    ):
        is_banned = await ban_manager.check_ban_and_respond(interaction)
        if is_banned:
            return

        if interaction.user == discordClient.user:
            return

        username = str(interaction.user)
        channel = str(interaction.channel)
        logger.info(f"\x1b[31m{username}\x1b[0m : /draw [{prompt}] в ({channel}) через [{image_model.value}] Кол-во: [{count}]")

        await generate_and_send_image(
            interaction, 
            prompt, 
            image_model.value, 
            image_model.name,
            count=count
        )

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

        try:
            reminder_time = datetime(year, month, day, hour, minute)
            reminder_time = reminder_time + timedelta(hours=offset)

            if reminder_time < datetime.now():
                await interaction.followup.send("> :x: **ОШИБКА:** Вы не можете установить напоминание на время в прошлом.")
                return
                
            max_future_date = datetime.now() + timedelta(days=365)
            if reminder_time > max_future_date:
                await interaction.followup.send("> :x: **ОШИБКА:** Вы не можете установить напоминание больше чем на год.")
                return

            reminder_id = await reminder_manager.add_reminder(user_id, message, reminder_time)
            if reminder_id:
                await interaction.followup.send(f"> :white_check_mark: **Напоминание установлено на {reminder_time.strftime('%Y-%m-%d %H:%M')}!** \n Вы получите сообщение от меня когда настанет требуемое время :wink:")
                logger.info(f"\x1b[31m{username} установил себе напоминание\x1b[0m")
        except ValueError as ve:
            logger.exception(f"remind: Ошибка при установке напоминания: {str(ve)}")
            await interaction.followup.send("> :x: **ОШИБКА:** Неверный формат времени. Пожалуйста, убедитесь, что все значения корректны.")
        except Exception as e:
            logger.exception(f"remind: Ошибка при установке напоминания: {str(e)}")
            await interaction.followup.send(f"> :x: **ОШИБКА:** {str(e)}")

    @discordClient.tree.command(name="remind-list", description="Показать все ваши напоминания")
    async def show_reminders(
        interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        user_id = interaction.user.id

        reminders = await reminder_manager.load_reminders(user_id)
        if not reminders:
            await interaction.followup.send("> :warning: **У вас нет активных напоминаний.**")
            return

        reminder_list = "\n".join(
            [f"{index + 1}. {datetime.fromisoformat(reminder['time']).strftime('%Y-%m-%d %H:%M')} - {reminder['message']} (ID: {reminder['id']})"
             for index, reminder in enumerate(reminders)]
        )
        await interaction.followup.send(f"> :page_with_curl: **Список напоминаний:**\n{reminder_list}")
        logger.info(f"\x1b[31m{username} запросил список своих напоминаний\x1b[0m")

    @discordClient.tree.command(name="remind-delete", description="Удалить напоминание")
    @app_commands.describe(reminder_id="ID напоминания для удаления")
    async def delete_reminder(
        interaction: discord.Interaction,
        reminder_id: str
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        username = str(interaction.user)

        success = await reminder_manager.remove_reminder(user_id, reminder_id)
        if success:
            await interaction.followup.send(f"> :white_check_mark: **Напоминание удалено!**")
            logger.info(f"\x1b[31m{username} удалил напоминание с ID {reminder_id}\x1b[0m")
        else:
            await interaction.followup.send("> :x: **ОШИБКА:** Не удалось удалить напоминание. Проверьте правильность ID.")

    @discordClient.tree.command(name="ban", description="Забанить пользователя")
    @app_commands.describe(
        user_id="ID пользователя, которого нужно забанить",
        reason="Причина бана (необязательно)",
        days="Количество дней бана (необязательно, по умолчанию - перманентный бан)"
    )
    async def ban_user(
        interaction: discord.Interaction, 
        user_id: str,  # it should be int but discord bug?
        reason: Optional[str] = "Нарушение правил",
        days: Optional[int] = None
    ):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != ban_manager.admin_id:
            await interaction.followup.send("> :x: **У вас нет прав для этой команды!**")
            return

        logger.info(f"ban_user: Попытка бана пользователя {user_id} администратором {interaction.user.id}. Причина: {reason}")

        try:
            await ban_manager.ban_user(
                int(user_id),
                reason, 
                days=days
            )
            logger.info(f"ban_user: Команда бана для пользователя {user_id} выполнена успешно.")
            await interaction.followup.send(f"> :white_check_mark: **Пользователь {user_id} успешно забанен**")
        except Exception as e:
            logger.error(f"ban_user: Ошибка при выполнении команды бана для пользователя {user_id}: {e}")
            await interaction.followup.send(
                f"> :x: **Произошла ошибка при бане:**\n"
                f"```\n{str(e)}\n```"
            )

    @discordClient.tree.command(name="unban", description="Разбанить пользователя")
    @app_commands.describe(
        user_id="ID пользователя, которого нужно разбанить"
    )
    async def unban_user(
        interaction: discord.Interaction, 
        user_id: str  # it should be int but discord bug?
    ):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != ban_manager.admin_id:
            await interaction.followup.send("> :x: **У вас нет прав для этой команды!**")
            return

        logger.info(f"unban_user: Попытка разбана пользователя {user_id} администратором {interaction.user.id}")

        try:
            result = await ban_manager.unban_user(int(user_id))
            if result:
                await interaction.followup.send(f"> :white_check_mark: **Пользователь {user_id} успешно разбанен**")
            else:
                await interaction.followup.send(f"> :warning: **Пользователь {user_id} не был забанен**")
        except Exception as e:
            logger.error(f"unban_user: Ошибка при выполнении команды разбана для пользователя {user_id}: {e}")
            await interaction.followup.send(
                f"> :x: **Произошла ошибка при разбане:**\n"
                f"```\n{str(e)}\n```"
            )

    @discordClient.tree.command(name="ban-info", description="Проверить блокировку и показать информацию о бане")
    @app_commands.describe(
        user_id="ID пользователя (необязательно, по умолчанию - Вы)"
    )
    async def ban_info(
        interaction: discord.Interaction, 
        user_id: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)

        target_user_id = int(user_id) if user_id else interaction.user.id

        try:
            is_banned, reason = await ban_manager.is_user_banned(target_user_id)

            if is_banned:
                ban_file = os.path.join(ban_manager.bans_dir, f'{target_user_id}_ban.json')
                ban_data = await read_json(ban_file)
                ban_time = datetime.fromisoformat(ban_data['timestamp'])
                duration = ban_data['duration']

                if duration:
                    unban_time = ban_time + timedelta(**duration)
                    unban_text = f"**Дата разбана:** {unban_time.strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    unban_text = "**Бан перманентный!**"

                await interaction.followup.send(
                    f"> :x: **Пользователю {target_user_id} запрещен доступ к боту!**\n"
                    f"**Причина:** {reason}\n"
                    f"**Дата бана:** {ban_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"{unban_text}"
                )
            else:
                await interaction.followup.send(f"> :white_check_mark: **Пользователь {target_user_id} не забанен и может пользоваться ботом. **")
        except Exception as e:
            logger.error(f"ban_info: Ошибка при получении информации о бане для пользователя {target_user_id}: {e}")
            await interaction.followup.send(
                f"> :x: **Произошла ошибка при получении информации о бане:**\n"
                f"```\n{str(e)}\n```"
            )

    @discordClient.tree.command(name="banned-list", description="Список забаненных пользователей")
    async def list_banned_users(
        interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != ban_manager.admin_id:
            await interaction.followup.send("> :x: **У вас нет прав для этой команды!**")
            return

        banned_users = await ban_manager.get_banned_users(interaction.user.id)

        if not banned_users:
            await interaction.followup.send("> :white_check_mark: **Нет забаненных пользователей.**")
            return

        banned_list = "\n".join([
            f"**ID:** {user['user_id']}, **Причина:** {user['reason']}" 
            for user in banned_users
        ])

        logger.info(f"Администратор {user_id} запросил список забаненных")
        await interaction.followup.send(f"### Забаненные пользователи:\n{banned_list}")

    @discordClient.event
    async def on_message(message):
        if message.author == discordClient.user:
            return

        if discordClient.user in message.mentions:
            clean_message = message.content.replace(f'<@{discordClient.user.id}>', '').strip()

            if clean_message:
                discordClient.current_channel = message.channel

                logger.info(f"\x1b[31m{message.author}\x1b[0m : Упоминание бота [{clean_message}] в ({message.channel})")
                asyncio.create_task(discordClient.send_message(message, clean_message, None))

    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    await discordClient.start(TOKEN)
