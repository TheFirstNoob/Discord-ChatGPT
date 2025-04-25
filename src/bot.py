import os
import base64
import asyncio
import mimetypes
import fitz  # PyMuPDF

import discord
from discord import app_commands, Attachment, SelectOption, ButtonStyle
from discord.ui import View, Select, Button

from datetime import datetime, timedelta
from typing import Optional

# local
import utils.reminder_utils as reminders_utils
from src.locale_manager import locale_manager as lm
from src.log import logger
from src.aclient import discordClient
from utils.files_utils import read_file, write_json
from utils.ban_utils import ban_manager
from utils.encryption_utils import UserDataEncryptor

# g4f
from g4f.client import AsyncClient

client = AsyncClient()

async def run_discord_bot():
    @discordClient.event
    async def on_ready():
        logger.info(lm.get('log_discord_ready'))
        logger.info(lm.get('log_discord_sync'))
        await discordClient.tree.sync()
        await discordClient.send_start_prompt()
        logger.info(lm.get('bot_start_log').format(user=discordClient.user))

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
        user_data.get('model', discordClient.default_model)

        logger.info(lm.get('log_user_ask').format(
            username=username,
            message=message,
            request_type=request_type or 'None',
            channel=discordClient.current_channel
        ))
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
            await interaction.followup.send(lm.get('asklong_file_error').format(filename=file.filename))
            return

        try:
            file_content = await file.read()
            file_message = file_content.decode('utf-8')
            message = f"{message}\n\n{file_message}"
        except Exception as e:
            logger.exception(lm.get('asklong_read_error_log').format(error=str(e)))
            await interaction.followup.send(lm.get('asklong_read_error').format(error=str(e)))
            return

        logger.info(lm.get('log_user_asklong').format(
            username=username,
            message=message,
            filename=file.filename,
            request_type=request_type or 'None',
            channel=discordClient.current_channel
        ))
        asyncio.create_task(discordClient.send_message(interaction, message, request_type))

    @discordClient.tree.command(name="askpdf", description=lm.get('askpdf_description'))
    @app_commands.describe(
        message=lm.get('askpdf_message_describe'),
        file=lm.get('askpdf_file_describe')
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
            await interaction.followup.send(lm.get('askpdf_file_error').format(filename=file.filename))
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
            logger.info(lm.get('askpdf_log').format(
                username=username,
                message=message,
                filename=file.filename,
                channel=discordClient.current_channel
            ))
            asyncio.create_task(discordClient.send_message(interaction, full_message, request_type=None))

        except Exception as e:
            logger.exception(lm.get('askpdf_error_log').format(error=str(e)))
            await interaction.followup.send(lm.get('askpdf_error').format(error=str(e)))

    @discordClient.tree.command(name="chat-model", description=lm.get('chat_model_description'))
    async def chat_model(interaction: discord.Interaction):
        # Сборка списка моделей: провайдер -> список моделей
        models = [
            ("GPT 4o-Mini", "gpt-4o-mini", "OpenAI"),
            ("GPT 4o", "gpt-4o", "OpenAI"),
            ("o3-Mini Thinking", "o3-mini", "OpenAI"),
            ("Claude 3.7 Sonnet", "claude-3.7-sonnet", "Anthropic"),
            ("Gemini 1.5 Pro", "gemini-1.5-pro", "Google"),
            ("Gemini 1.5 Flash", "gemini-1.5-flash", "Google"),
            ("Gemini 2.0 Flash", "gemini-2.0-flash", "Google"),
            ("Gemini 2.0 Flash Thinking", "gemini-2.0-flash-thinking", "Google"),
            ("Command R+", "command-r-plus", "Cohere"),
            ("Command R7B+", "command-r7b-12-2024", "Cohere"),
            ("LLaMa v3.1 405B", "llama-3.1-405b", "MetaAI"),
            ("LLaMa v3.2 11B Vision", "llama-3.2-11b", "MetaAI"),
            ("LLaMa v3.3 70B", "llama-3.3-70b", "MetaAI"),
            ("QwQ 32B Thinking", "qwq-32b", "Qwen Team"),
            ("QvQ 72B Vision", "qwen-qvq-72b-preview", "Qwen Team"),
            ("Qwen 2.5 72B", "qwen-2.5-72b", "Qwen Team"),
            ("Qwen 2.5 1M-Demo", "qwen-2.5-1m-demo", "Qwen Team"),
            ("Qwen 2.5 Coder 32B", "qwen-2.5-coder-32b", "Qwen Team"),
            ("DeepSeek LLM 67B", "deepseek-chat", "DeepSeek AI"),
            ("DeepSeek v3", "deepseek-v3", "DeepSeek AI"),
            ("DeepSeek R1 Thinking", "deepseek-r1", "DeepSeek AI"),
            ("GLM-4 230B", "glm-4", "GLM Team"),
            ("Mixtral Small 24B", "mixtral-small-24b", "Mistral"),
            ("Phi 3.5 Mini", "phi-3.5-mini", "Microsoft")
        ]
        provider_map = {}
        for name, value, provider in models:
            provider_map.setdefault(provider, []).append((name, value))

        def create_provider_embed():
            embed = discord.Embed(
                title=lm.get('chat_model_title'),
                description=lm.get('chat_model_full_description'),
                color=discord.Color.blue()
            )
            for prov, items in provider_map.items():
                lines = "\n".join(f"\u2022 {n}" for n, _ in items)
                embed.add_field(name=f"**{prov}**", value=lines or "—", inline=False)
            return embed

        class ProviderSelect(Select):
            def __init__(self):
                options = []
                for prov in provider_map:
                    options.append(SelectOption(label=prov, value=prov))
                super().__init__(placeholder=lm.get('select_provider_placeholder'), min_values=1, max_values=1, options=options)

            async def callback(self, interaction: discord.Interaction):
                selected = self.values[0]
                models_for = provider_map[selected]
                model_lines = "\n".join(f"\u2022 {n}" for n, _ in models_for)

                model_embed = discord.Embed(
                    title=f"{lm.get('chat_model_choose_model')} {selected}",
                    description=model_lines,
                    color=discord.Color.purple()
                )

                class ModelSelect(Select):
                    def __init__(self):
                        opts = [SelectOption(label=n, value=v) for n, v in models_for]
                        super().__init__(placeholder=lm.get('select_model_placeholder'), min_values=1, max_values=1, options=opts)

                    async def callback(self, model_inter: discord.Interaction):
                        model = self.values[0]
                        await discordClient.set_user_model(model_inter.user.id, model)
                        success_embed = discord.Embed(
                            title=lm.get('chat_model_success').format(model=model),
                            color=discord.Color.green()
                        )
                        button = Button(label=lm.get('chat_model_change_button'), style=ButtonStyle.secondary)

                        async def back_callback(back_inter: discord.Interaction):
                            view = View()
                            view.add_item(ProviderSelect())
                            await back_inter.response.edit_message(embed=create_provider_embed(), view=view, content=None)

                        button.callback = back_callback
                        view = View()
                        view.add_item(button)
                        await model_inter.response.edit_message(embed=success_embed, view=view, content=None)
                        logger.info(lm.get('chat_model_log').format(user=model_inter.user, model=model))

                view = View()
                view.add_item(ModelSelect())
                await interaction.response.edit_message(embed=model_embed, view=view, content=None)

        view = View()
        view.add_item(ProviderSelect())
        await interaction.response.send_message(embed=create_provider_embed(), view=view, ephemeral=True)

    @discordClient.tree.command(name="instruction-set", description=lm.get('instruction_set_description'))
    @app_commands.describe(instruction=lm.get('instruction_set_describe'))
    async def instruction_set(interaction: discord.Interaction, instruction: str):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        await discordClient.set_user_instruction(user_id, instruction)
        await interaction.followup.send(lm.get('instruction_set_success'))
        logger.info(lm.get('instruction_set_log').format(user=interaction.user))

    @discordClient.tree.command(name="instruction-reset", description=lm.get('instruction_reset_description'))
    async def instruction_reset(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        await discordClient.reset_user_instruction(user_id)
        await interaction.followup.send(lm.get('instruction_reset_success'))
        logger.info(lm.get('instruction_reset_log').format(user=interaction.user))

    @discordClient.tree.command(name="reset", description=lm.get('reset_description'))
    async def reset(
        interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        await discordClient.reset_conversation_history(user_id)
        await discordClient.reset_user_instruction(user_id)
        await interaction.followup.send(lm.get('reset_success'))
        logger.warning(lm.get('reset_log').format(user=interaction.user))

    @discordClient.tree.command(name="help", description=lm.get('help_description'))
    async def help_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        
        embed = discord.Embed(
            title=lm.get('help_title'),
            description=lm.get('help_description'),
            color=discord.Color.blue()
        )
        
        categories = {
            lm.get('help_category_main'): [
                (lm.get('help_command_ask'), lm.get('help_command_ask_desc')),
                (lm.get('help_command_asklong'), lm.get('help_command_asklong_desc')),
                (lm.get('help_command_askpdf'), lm.get('help_command_askpdf_desc')),
                (lm.get('help_command_draw'), lm.get('help_command_draw_desc'))
            ],
            lm.get('help_category_ai'): [
                (lm.get('help_command_chat_model'), lm.get('help_command_chat_model_desc')),
                (lm.get('help_command_instruction_set'), lm.get('help_command_instruction_set_desc')),
                (lm.get('help_command_instruction_reset'), lm.get('help_command_instruction_reset_desc')),
                (lm.get('help_command_reset'), lm.get('help_command_reset_desc'))
            ],
            lm.get('help_category_reminders'): [
                (lm.get('help_command_remind_add'), lm.get('help_command_remind_add_desc')),
                (lm.get('help_command_remind_list'), lm.get('help_command_remind_list_desc')),
                (lm.get('help_command_remind_delete'), lm.get('help_command_remind_delete_desc'))
            ],
            lm.get('help_category_info'): [
                (lm.get('help_command_help'), lm.get('help_command_help_desc')),
                (lm.get('help_command_about'), lm.get('help_command_about_desc')),
                (lm.get('help_command_changelog'), lm.get('help_command_changelog_desc')),
                (lm.get('help_command_history'), lm.get('help_command_history_desc'))
            ]
        }
        
        for category, commands in categories.items():
            command_list = "\n".join([f"**{cmd}** - {desc}" for cmd, desc in commands])
            embed.add_field(
                name=f"**{category}**",
                value=command_list,
                inline=False
            )
        
        embed.set_footer(text=lm.get('help_footer').format(version=os.environ.get('VERSION_BOT')))
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(lm.get('log_user_help').format(username=username))

    @discordClient.tree.command(name="about", description=lm.get('about_description'))
    async def about_command(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        about_file_path = 'texts/about.txt'

        about_text = await read_file(about_file_path)
        if not about_text:
            await interaction.followup.send(lm.get('about_error').format(admin=os.environ.get('ADMIN_NAME')))
            logger.error(lm.get('about_error_log').format(path=about_file_path))
            return

        about_text = about_text.format(username=username)
        await interaction.followup.send(about_text)
        logger.info(lm.get('about_log').format(username=username))

    @discordClient.tree.command(name="changelog", description=lm.get('changelog_description'))
    async def changelog(interaction: discord.Interaction):
        changelog_dir = "texts/change_log"
        files = [f[:-4] for f in os.listdir(changelog_dir) if f.endswith('.txt')]

        def version_key(v):
            return [int(p) if p.isdigit() else p for p in v.split('.')]

        versions = sorted(files, key=version_key, reverse=True)
        groups = {}
        for v in versions:
            major = v.split('.')[0]
            groups.setdefault(major, []).append(v)

        def create_main_embed():
            embed = discord.Embed(
                title=lm.get('changelog_title'),
                description=lm.get('changelog_full_description'),
                color=discord.Color.green()
            )
            for major in sorted(groups.keys(), key=int, reverse=True):
                rows = sorted(groups[major], key=version_key, reverse=True)
                table = f"{lm.get('changelog_versions_list')}:\n```" + "\n".join(rows) + "```"
                embed.add_field(name=f"**{major}.x.x**", value=table, inline=False)
            return embed

        def create_main_view():
            options = [SelectOption(label=v, value=v) for v in versions[:25]]

            class VersionSelect(Select):
                def __init__(self):
                    super().__init__(placeholder=lm.get('changelog_description_select'), min_values=1, max_values=1, options=options)

                async def callback(self, interaction: discord.Interaction):
                    version = self.values[0]
                    text = await read_file(f"{changelog_dir}/{version}.txt")
                    detail_embed = discord.Embed(title=lm.get('changelog_version_title').format(version=version), description=text, color=discord.Color.blue())
                    button = Button(label=lm.get('changelog_back_button'), style=ButtonStyle.secondary)

                    async def back_callback(back_inter: discord.Interaction):
                        await back_inter.response.edit_message(embed=create_main_embed(), view=create_main_view())

                    button.callback = back_callback
                    view = View()
                    view.add_item(button)
                    await interaction.response.edit_message(embed=detail_embed, view=view)
                    logger.info(lm.get('changelog_log').format(username=interaction.user, version=version))

            view = View()
            view.add_item(VersionSelect())
            return view

        await interaction.response.send_message(embed=create_main_embed(), view=create_main_view(), ephemeral=True)

    @discordClient.tree.command(name="history", description=lm.get('history_description'))
    async def history(interaction: discord.Interaction):
        """
        Export the user's message history to a JSON file and send it to the user.
        
        Args:
            interaction: Discord interaction object
        """
        await interaction.response.defer(ephemeral=True)

        if interaction.user == discordClient.user:
            return

        is_dm = isinstance(interaction.channel, discord.DMChannel)
        user_id = interaction.user.id
        channel_id = None if is_dm else interaction.channel.id

        try:
            user_data = await discordClient.load_user_data(user_id, channel_id)
            history_list = user_data.get('history')
            if not history_list:
                await interaction.followup.send(lm.get('history_empty'), ephemeral=True)
                return

            temp_dir = 'temp'
            os.makedirs(temp_dir, exist_ok=True)
            filename = f"history_{channel_id or user_id}.json"
            temp_filepath = os.path.join(temp_dir, filename)

            await write_json(temp_filepath, history_list)

            try:
                with open(temp_filepath, 'rb') as file:
                    await interaction.followup.send(
                        lm.get('history_download_success'),
                        file=discord.File(file, filename=filename),
                        ephemeral=True
                    )
            except Exception as e:
                logger.error(lm.get('history_error_log').format(error=str(e)))
                await interaction.followup.send(
                    lm.get('history_download_error').format(error=str(e)),
                    ephemeral=True
                )
            finally:
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)

            if is_dm:
                logger.info(lm.get('log_user_history_dm').format(username=str(interaction.user)))
            else:
                logger.info(lm.get('log_user_history_channel').format(
                    username=str(interaction.user),
                    channel=interaction.channel.name
                ))

        except Exception as e:
            logger.error(lm.get('history_error_log').format(error=str(e)))
            await interaction.followup.send(
                lm.get('history_error').format(error=str(e)),
                ephemeral=True
            )

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
                    await interaction.followup.send(lm.get('draw_generate_empty'))
                    logger.error(lm.get('draw_generate_error_log'))
                    return

            if images_data:
                if count > 1:
                    files = [discord.File(image_path, filename=f"image_{i+1}.png") for i, image_path in enumerate(images_data)]
                    model_message = lm.get('draw_images_model_message').format(model=model_name)
                    await interaction.followup.send(model_message, files=files)
                else:
                    with open(images_data[0], 'rb') as f:
                        model_message = lm.get('draw_image_model_message').format(model=model_name)
                        await interaction.followup.send(model_message, file=discord.File(f, filename=images_data[0]))
                for image_path in images_data:
                    os.remove(image_path)
            else:
                await interaction.followup.send(lm.get('draw_generate_empty'))
                logger.error(lm.get('draw_generate_empty_log'))

        except Exception as e:
            logger.error(lm.get('draw_error_log').format(error=str(e)))
            await interaction.followup.send(lm.get('draw_error').format(error=str(e)))

    @discordClient.tree.command(name="draw", description=lm.get('draw_description'))
    @app_commands.describe(
        prompt=lm.get('draw_prompt_describe'),
        image_model=lm.get('draw_model_describe'),
        count=lm.get('draw_count_describe')
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
        logger.info(lm.get('log_user_draw').format(
            username=username,
            prompt=prompt,
            channel=channel,
            model=image_model.value,
            count=count
        ))

        await generate_and_send_image(
            interaction, 
            prompt, 
            image_model.value, 
            image_model.name,
            count=count
        )

    @discordClient.tree.command(name="remind-add", description=lm.get('remind_add_description'))
    @app_commands.describe(
        day=lm.get('remind_add_day_describe'),
        month=lm.get('remind_add_month_describe'),
        year=lm.get('remind_add_year_describe'),
        hour=lm.get('remind_add_hour_describe'),
        minute=lm.get('remind_add_minute_describe'),
        offset=lm.get('remind_add_offset_describe'),
        message=lm.get('remind_add_message_describe')
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

        if reminders_utils._scheduler is None:
            await interaction.followup.send(lm.get('remind_scheduler_error'))
            logger.error(lm.get('remind_scheduler_error_log').format(username=username))
            return

        try:
            reminder_time = datetime(year, month, day, hour, minute) + timedelta(hours=offset)

            if reminder_time < datetime.now():
                await interaction.followup.send(lm.get('remind_past_error'))
                return

            max_future_date = datetime.now() + timedelta(days=365)
            if reminder_time > max_future_date:
                await interaction.followup.send(lm.get('remind_future_error'))
                return

            reminder_id = await reminders_utils.reminder_manager.add_reminder(user_id, message, reminder_time)
            if reminder_id:
                await reminders_utils._scheduler.add_reminder(user_id, reminder_id, message, reminder_time)
                await interaction.followup.send(lm.get('remind_set_success').format(time=reminder_time.strftime('%Y-%m-%d %H:%M')))
                logger.info(lm.get('log_user_remind').format(username=username))
        except ValueError as ve:
            logger.exception(lm.get('log_remind_error').format(error=str(ve)))
            await interaction.followup.send(lm.get('remind_time_error'))
        except Exception as e:
            logger.exception(lm.get('remind_error_log').format(error=str(e)))
            await interaction.followup.send(lm.get('remind_error').format(error=str(e)))

    @discordClient.tree.command(name="remind-list", description=lm.get('remind_list_description'))
    async def show_reminders(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        username = str(interaction.user)
        user_id = interaction.user.id

        reminders = await reminders_utils.reminder_manager.load_reminders(user_id)
        if not reminders:
            await interaction.followup.send(lm.get('remind_list_empty'))
            return

        reminder_list = "\n".join(
            [f"{index + 1}. {datetime.fromisoformat(reminder['time']).strftime('%Y-%m-%d %H:%M')} - {reminder['message']}"
             for index, reminder in enumerate(reminders)]
        )
        await interaction.followup.send(lm.get('remind_list_success').format(list=reminder_list))
        logger.info(lm.get('remind_list_log').format(username=username))

    @discordClient.tree.command(name="remind-delete", description=lm.get('remind_delete_description'))
    @app_commands.describe(reminder_number=lm.get('remind_delete_number_describe'))
    async def delete_reminder(interaction: discord.Interaction, reminder_number: int):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        username = str(interaction.user)

        reminders = await reminders_utils.reminder_manager.load_reminders(user_id)
        if not reminders:
            await interaction.followup.send(lm.get('remind_delete_empty'))
            return

        if reminder_number < 1 or reminder_number > len(reminders):
            await interaction.followup.send(lm.get('remind_delete_invalid'))
            return

        reminder_id = reminders[reminder_number - 1]['id']
        success = await reminders_utils.reminder_manager.remove_reminder(user_id, reminder_id)
        if success:
            if reminders_utils._scheduler:
                await reminders_utils._scheduler.remove_reminder(user_id, reminder_id)
            await interaction.followup.send(lm.get('remind_delete_success').format(number=reminder_number))
            logger.info(lm.get('remind_delete_log').format(username=username, number=reminder_number))
        else:
            await interaction.followup.send(lm.get('remind_delete_error'))

    @discordClient.tree.command(name="ban", description=lm.get('ban_description'))
    @app_commands.describe(
        user_id=lm.get('ban_user_describe'),
        reason=lm.get('ban_reason_describe'),
        days=lm.get('ban_days_describe')
    )
    async def ban_user(
        interaction: discord.Interaction, 
        user_id: str,  # it should be int but discord bug?
        reason: Optional[str] = lm.get('ban_default_reason'),
        days: Optional[int] = None
    ):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != ban_manager.admin_id:
            await interaction.followup.send(lm.get('no_permission'))
            return

        logger.info(lm.get('ban_log_attempt').format(
            user_id=user_id,
            admin_id=interaction.user.id,
            reason=reason
        ))

        try:
            await ban_manager.ban_user(
                int(user_id),
                reason, 
                days=days
            )
            logger.info(lm.get('ban_log_success').format(user_id=user_id))
            await interaction.followup.send(lm.get('ban_success').format(user_id=user_id))
        except Exception as e:
            logger.error(lm.get('log_ban_error').format(user_id=user_id, error=e))
            await interaction.followup.send(lm.get('ban_error').format(error=str(e)))

    @discordClient.tree.command(name="unban", description=lm.get('unban_description'))
    @app_commands.describe(
        user_id=lm.get('unban_user_describe')
    )
    async def unban_user(
        interaction: discord.Interaction, 
        user_id: str  # it should be int but discord bug?
    ):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != ban_manager.admin_id:
            await interaction.followup.send(lm.get('no_permission'))
            return

        logger.info(lm.get('unban_log_attempt').format(
            user_id=user_id,
            admin_id=interaction.user.id
        ))

        try:
            result = await ban_manager.unban_user(int(user_id))
            if result:
                await interaction.followup.send(lm.get('unban_success').format(user_id=user_id))
            else:
                await interaction.followup.send(lm.get('unban_not_banned').format(user_id=user_id))
        except Exception as e:
            logger.error(lm.get('log_unban_error').format(user_id=user_id, error=e))
            await interaction.followup.send(lm.get('unban_error').format(error=str(e)))

    @discordClient.tree.command(name="ban-info", description=lm.get('ban_info_description'))
    @app_commands.describe(
        user_id=lm.get('ban_info_user_describe')
    )
    async def ban_info(
        interaction: discord.Interaction,
        user_id: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)

        target_user_id = int(user_id) if user_id else interaction.user.id
        is_self_check = (target_user_id == interaction.user.id)

        try:
            is_banned, ban_data = await ban_manager.is_user_banned(target_user_id, is_self_check)

            if is_banned:
                embed = discord.Embed(
                    title=ban_data["title"],
                    description=ban_data["description"],
                    color=ban_data["color"]
                )

                for field in ban_data["fields"]:
                    embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", False))

                await interaction.followup.send(embed=embed)
            else:
                if is_self_check:
                    await interaction.followup.send(lm.get('ban_info_not_banned_self'))
                else:
                    await interaction.followup.send(lm.get('ban_info_not_banned_other').format(user_id=target_user_id))
        except Exception as e:
            logger.error(lm.get('ban_info_error_log').format(user_id=target_user_id, error=e))
            await interaction.followup.send(
                lm.get('ban_info_error').format(error=str(e))
            )

    @discordClient.tree.command(name="ban-list", description=lm.get('ban_list_description'))
    async def list_banned_users(
        interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != ban_manager.admin_id:
            await interaction.followup.send(lm.get('no_permission'))
            return

        banned_users = await ban_manager.get_banned_users(interaction.user.id)

        if not banned_users:
            await interaction.followup.send(lm.get('ban_list_empty'))
            return

        banned_list = "\n".join([
            lm.get('ban_list_item').format(user_id=user['user_id'], reason=user['reason'])
            for user in banned_users
        ])

        logger.info(lm.get('ban_list_log').format(admin_id=interaction.user.id))
        await interaction.followup.send(lm.get('ban_list_success').format(list=banned_list))

    @discordClient.event
    async def on_message(message):
        if message.author == discordClient.user:
            return

        if discordClient.user in message.mentions:
            clean_message = message.content.replace(f'<@{discordClient.user.id}>', '').strip()

            if clean_message:
                discordClient.current_channel = message.channel

                logger.info(lm.get('log_bot_mention').format(
                    username=message.author,
                    message=clean_message,
                    channel=message.channel
                ))
                asyncio.create_task(discordClient.send_message(message, clean_message, None))

    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    await discordClient.start(TOKEN)
