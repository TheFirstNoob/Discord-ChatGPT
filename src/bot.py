import os
import base64
import asyncio
import requests
from docling.document_converter import DocumentConverter
import logging

import discord
from discord import app_commands, Attachment, SelectOption, ButtonStyle, Embed
from discord.ui import View, Select, Button, Modal, TextInput

from datetime import datetime, timedelta
from typing import Optional, List

# local
import utils.reminder_utils as reminders_utils
from utils.reminder_utils import Reminder
from src.locale_manager import locale_manager as lm
from src.log import logger
from src.aclient import discordClient
from src.agents_presets import AGENTS
from utils.files_utils import read_file, write_json, save_attachment_to_file
from utils.ban_utils import ban_manager

# g4f
from g4f.client import AsyncClient

client = AsyncClient()

# --- models list with vision support flag ---
MODELS = [
    ("GPT 3.5 Turbo", "gpt-3.5-turbo", "OpenAI", False),
    ("GPT 4o-Mini", "gpt-4o-mini", "OpenAI", False),
    ("GPT 4o", "gpt-4o", "OpenAI", False),
    ("GPT 4.1", "gpt-4.1", "OpenAI", False),
    ("GPT 4.1-Nano", "gpt-4.1-nano", "OpenAI", False),
    ("GPT 4.1-Mini", "gpt-4.1-mini", "OpenAI", False),
    ("GPT 4.1-XLarge", "gpt-4.1-xlarge", "OpenAI", False),
    ("GPT 4.5", "gpt-4.5", "OpenAI", False),
    ("o3-Mini", "o3-mini", "OpenAI", False),
    ("o3-Mini-High", "o3-mini-high", "OpenAI", False),
    ("o4-Mini", "o4-mini", "OpenAI", False),
    ("Claude 3.5 Sonnet", "claude-3.5-sonnet", "Anthropic", True),
    ("Claude 3.7 Sonnet", "claude-3.7-sonnet", "Anthropic", True),
    ("Gemini 1.5 Pro", "gemini-1.5-pro", "Google", True),
    ("Gemini 1.5 Flash", "gemini-1.5-flash", "Google", True),
    ("Gemini 2.0 Flash", "gemini-2.0-flash", "Google", True),
    ("Gemini 2.0 Flash Extended", "gemini-2.0-flash-thinking", "Google", True),
    ("Gemma 3 27B", "google/gemma-3-27b-it", "Google", True),
    ("Command A", "command-a", "Cohere", False),
    ("Command R+", "command-r-plus", "Cohere", False),
    ("Command R+ 08-2024", "CohereLabs/c4ai-command-r-plus-08-2024", "Cohere", False),
    ("Command R7B+", "command-r7b-12-2024", "Cohere", False),
    ("LLaMa v3.2 11B", "llama-3.2-11b", "MetaAI", True),
    ("LLaMa v3.3 70B", "llama-3.3-70b", "MetaAI", False),
    ("LLaMa v4 Scout", "llama-4-scout", "MetaAI", False),
    ("QwQ 32B", "qwq-32b", "Qwen Team", False),
    ("QvQ 72B", "qwen-qvq-72b-preview", "Qwen Team", True),
    ("Qwen 2.5 72B", "Qwen/Qwen2.5-72B-Instruct", "Qwen Team", False),
    ("Qwen 2.5 VL 32B", "Qwen/Qwen2.5-VL-32B-Instruct", "Qwen Team", False),
    ("Qwen 2.5 1M-Demo", "qwen-2.5-1m-demo", "Qwen Team", False),
    ("Qwen 2.5 Coder 32B", "qwen-2.5-coder-32b", "Qwen Team", False),
    ("Qwen 2.5 Coder", "qwen-2.5-coder", "Qwen Team", False),
    ("Qwen 3 32B", "qwen3-32b", "Qwen Team", False),
    ("Qwen 3 235B A22B","qwen3-235b-a22b", "Qwen Team", False),
    ("DeepSeek LLM 67B", "deepseek-chat", "DeepSeek AI", False),
    ("DeepSeek v3", "deepseek-v3", "DeepSeek AI", False),
    ("DeepSeek R1", "deepseek-r1", "DeepSeek AI", False),
    ("DeepSeek R1 Qwen 32B", "deepseek-r1-qwen-32b", "DeepSeek AI", False),
    ("DeepSeek R1 LLaMa 70B", "deepseek-r1-distill-llama-70b", "DeepSeek AI", False),
    ("GLM-4 230B", "glm-4", "GLM Team", False),
    ("Phi 4", "phi-4", "Microsoft", False),
    ("Blackbox", "Blackboxai", "Blackbox AI", False)
]

def is_vision_model(model_name: str) -> bool:
    """Check if the model supports vision."""
    return any(m[1] == model_name and m[3] for m in MODELS)

def get_vision_models() -> list:
    """Get a list of all vision model names."""
    return [m[1] for m in MODELS if m[3]]

async def run_discord_bot():
    @discordClient.event
    async def on_ready():
        print("On ready loading...")
        try:
            # We need add this check for catch sync tree error (for check missing locales in placeholders)
            await discordClient.tree.sync()
            print("Tree sync awaited...")
        except Exception as e:
            print(f"Tree sync failed: {e}")
            logger.error(f"Tree sync failed: {e}")
        await discordClient.send_start_prompt()
        print("Send start prompt awaited...")
        logger.info(lm.get('bot_start_log').format(user=discordClient.user))

    @discordClient.tree.command(name="ask", description=lm.get('asklong_description'))
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
        file: Optional[Attachment] = None,
        request_type: Optional[str] = None
    ):
        """Обрабатывает текст и/или файл через Docling и отправляет запрос ИИ."""
        await interaction.response.defer(ephemeral=False)

        # Проверка бана и от пользователя бота
        if await ban_manager.check_ban_and_respond(interaction):
            return
        if interaction.user == discordClient.user:
            return

        combined_message = message

        # Если прикреплён файл, обрабатываем его
        if file:
            # Проверка: если это изображение
            if file.content_type and file.content_type.startswith('image/'):
                # Получаем модель пользователя
                user_data = await discordClient.load_user_data(interaction.user.id)
                model = user_data.get('model', 'gpt-4o')
                vision_support = user_data.get('vision_support', False)

                # Проверяем поддержку vision
                if not vision_support and not is_vision_model(model):
                    # Собираем список vision-моделей для вывода
                    vision_models_str = "\n".join(
                        f"- `{m}`" for m in get_vision_models()
                    )
                    await interaction.followup.send(
                        f":x: {lm.get('vision_not_supported').format(model=model)}\n"
                        f"{lm.get('vision_supported_models')}:\n{vision_models_str}"
                    )
                    logger.info(lm.get('log_vision_attempt').format(user=interaction.user.id, model=model))
                    return

                # Получить изображение напрямую с CDN
                try:
                    response = requests.get(file.url, stream=True, timeout=10)
                    response.raise_for_status()
                    
                    ai_response = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": message}],
                        image=response.raw
                    )
                    result = ai_response.choices[0].message.content
                    await interaction.followup.send(result)
                    
                    logger.info(lm.get('log_user_asklong').format(
                        username=str(interaction.user),
                        message=message,
                        filename=file.filename if file else lm.get('filename_none'),
                        channel=interaction.channel
                    ))
                    return
                except Exception as e:
                    logger.error(lm.get('log_image_processing_failed').format(error=str(e)))
                    await interaction.followup.send(
                        lm.get('image_processing_failed').format(error=str(e))
                    )
                return  # Не продолжаем дальше, если это было изображение

            # Если это не изображение — стандартная обработка файла через Docling
            try:
                temp_path = await save_attachment_to_file(
                    file,
                    dirpath="temp",
                    user_id=interaction.user.id
                )
                from src.docling_utils import extract_docling_content
                try:
                    text, tables, structured = extract_docling_content(temp_path)
                    if text.strip():
                        combined_message = f"{message}\n\n{text}"
                    elif tables:
                        from utils.message_utils import send_split_message
                        sent_any = False
                        for table_chunk in tables:
                            if table_chunk.strip():
                                await send_split_message(discordClient, table_chunk, interaction)
                                sent_any = True
                        if not sent_any:
                            await interaction.followup.send(":x: Не удалось извлечь текст или таблицы из документа.")
                        return
                    else:
                        await interaction.followup.send(":x: Не удалось извлечь текст из документа. Возможно, файл пуст или содержит только таблицы/формулы без текста.")
                        return
                except Exception as e:
                    logger.exception(lm.get('log_file_processing_error').format(filename=file.filename, error=e))
                    await interaction.followup.send(lm.get('asklong_read_error').format(error=str(e)))
                    return
            finally:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)

        logger.info(lm.get('log_user_asklong').format(
            username=str(interaction.user),
            message=combined_message,
            filename=file.filename if file else lm.get('filename_none'),
            request_type=request_type or lm.get('request_type_none'),
            channel=interaction.channel
        ))

        asyncio.create_task(discordClient.send_message(interaction, combined_message, request_type))

    @discordClient.tree.command(name="chat-model", description=lm.get('chat_model_description'))
    async def chat_model(interaction: discord.Interaction):
        provider_map = {}
        for name, value, provider, vision in MODELS:
            provider_map.setdefault(provider, []).append((name, value, vision))

        def create_provider_embed():
            embed = discord.Embed(
                title=lm.get('chat_model_title'),
                description=lm.get('chat_model_full_description'),
                color=discord.Color.blue()
            )
            for prov, items in provider_map.items():
                lines = "\n".join(f"\u2022 {n} {':eye:' if v else ''}" for n, _, v in items)
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
                model_lines = "\n".join(f"\u2022 {n} {':eye:' if v else ''}" for n, _, v in models_for)

                model_embed = discord.Embed(
                    title=f"{lm.get('chat_model_choose_model')} {selected}",
                    description=model_lines,
                    color=discord.Color.purple()
                )

                class ModelSelect(Select):
                    def __init__(self):
                        opts = [
                            SelectOption(
                                label=f"{n} {':eye:' if vision else ''}",
                                value=v
                            )
                            for n, v, vision in models_for
                        ]
                        super().__init__(placeholder=lm.get('select_model_placeholder'), min_values=1, max_values=1, options=opts)

                    async def callback(self, model_inter: discord.Interaction):
                        model = self.values[0]
                        # Find vision support for selected model
                        vision_support = next((v for n, val, v in models_for if val == model), False)
                        await discordClient.set_user_model(model_inter.user.id, model, vision_support)
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

    @discordClient.tree.command(name="instruction", description=lm.get('instruction_manage_description'))
    async def instruction_manage(interaction: discord.Interaction):
        user_id = interaction.user.id

        async def get_current_instruction():
            user_data = await discordClient.load_user_data(user_id)
            return user_data.get('instruction', '')

        async def send_instruction_embed(inter, ephemeral=True):
            instruction = await get_current_instruction()
            embed = Embed(
                title=lm.get('instruction_manage_title'),
                description=lm.get('instruction_manage_desc'),
                color=discord.Color.blue()
            )
            embed.add_field(
                name=lm.get('instruction_current'),
                value=instruction or lm.get('instruction_not_set'),
                inline=False
            )
            view = InstructionManageView()
            # отвечаем сразу, а не followup
            await inter.response.send_message(embed=embed, view=view, ephemeral=ephemeral)

        class InstructionModal(Modal):
            def __init__(self):
                super().__init__(title=lm.get('instruction_modal_title'))
                self.instruction_input = TextInput(
                    label=lm.get('instruction_modal_label'),
                    placeholder=lm.get('instruction_modal_placeholder'),
                    style=discord.TextStyle.long,
                    required=True,
                    max_length=2000
                )
                self.add_item(self.instruction_input)

            async def on_submit(self, modal_interaction: discord.Interaction):
                await discordClient.set_user_instruction(user_id, self.instruction_input.value)
                await modal_interaction.response.send_message(
                    lm.get('instruction_set_success'),
                    ephemeral=True
                )
                # а здесь можно уже вызывать followup, потому что response был от модалки
                await send_instruction_embed(modal_interaction, ephemeral=True)
                logger.info(lm.get('instruction_set_log').format(user=interaction.user))

        class InstructionManageView(View):
            def __init__(self):
                super().__init__(timeout=180)

            @discord.ui.button(label=lm.get('instruction_set_button'), style=ButtonStyle.green, custom_id="set_instruction")
            async def set_instruction(self, button: Button, btn_inter: discord.Interaction):
                await btn_inter.response.send_modal(InstructionModal())

            @discord.ui.button(label=lm.get('instruction_delete_button'), style=ButtonStyle.red, custom_id="delete_instruction")
            async def delete_instruction(self, button: Button, btn_inter: discord.Interaction):
                await discordClient.reset_user_instruction(user_id)
                await btn_inter.response.send_message(
                    lm.get('instruction_reset_success'),
                    ephemeral=True
                )
                await send_instruction_embed(btn_inter, ephemeral=True)
                logger.info(lm.get('instruction_reset_log').format(user=interaction.user))

        # вот тут сразу ответ нам и нужен
        await send_instruction_embed(interaction, ephemeral=True)

    @discordClient.tree.command(name="agent", description=lm.get('agent_command_description'))
    async def agent_command(interaction: discord.Interaction):
        user_id = interaction.user.id

        agents_by_id = {agent["id"]: agent for agent in AGENTS}

        class AgentSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(
                        label=agent["name"],
                        value=agent["id"],
                        description=agent["preview"][:100]
                    )
                    for agent in AGENTS
                ]
                super().__init__(
                    placeholder=lm.get('agent_select_placeholder'),
                    min_values=1, max_values=1,
                    options=options
                )

            async def callback(self, select_interaction: discord.Interaction):
                agent_id = self.values[0]
                agent = agents_by_id[agent_id]
                embed = discord.Embed(
                    title=lm.get('agent_preview_title').format(name=agent['name']),
                    description=lm.get('agent_preview_desc').format(
                        preview=agent['preview'],
                        instruction=agent['instruction'] or lm.get('agent_no_instruction')
                    ),
                    color=discord.Color.purple()
                )
                view = AgentActionView(agent_id)
                await select_interaction.response.edit_message(embed=embed, view=view)

        class AgentActionView(discord.ui.View):
            def __init__(self, agent_id=None):
                super().__init__(timeout=180)
                self.add_item(AgentSelect())
                if agent_id:
                    self.add_item(UseAgentButton(agent_id))

        class UseAgentButton(discord.ui.Button):
            def __init__(self, agent_id):
                agent = agents_by_id[agent_id]
                super().__init__(
                    label=lm.get('agent_use_button').format(name=agent['name']),
                    style=discord.ButtonStyle.green,
                    custom_id=f"use_agent_{agent_id}"
                )
                self.agent_id = agent_id

            async def callback(self, button_interaction: discord.Interaction):
                agent = agents_by_id[self.agent_id]
                await discordClient.set_user_instruction(button_interaction.user.id, agent["instruction"])
                await button_interaction.response.send_message(
                    lm.get('agent_use_success').format(name=agent['name']),
                    ephemeral=True
                )

        embed = discord.Embed(
            title=lm.get('agent_embed_title'),
            description=lm.get('agent_embed_desc'),
            color=discord.Color.blue()
        )
        view = AgentActionView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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

        def create_major_embed():
            embed = discord.Embed(
                title=lm.get('changelog_title'),
                description=lm.get('changelog_full_description'),
                color=discord.Color.green()
            )
            for major in sorted(groups.keys(), key=int, reverse=True):
                count = len(groups[major])
                embed.add_field(
                    name=f"**{major}.x.x**",
                    value=f"{lm.get('changelog_versions_count')}: {count}",
                    inline=False
                )
            return embed

        def create_major_view():
            options = [
                SelectOption(label=f"{major}.x.x", value=major, description=f"{lm.get('changelog_versions_count')}: {len(groups[major])}")
                for major in sorted(groups.keys(), key=int, reverse=True)
            ][:25]  # Limit to 25 options

            class MajorSelect(Select):
                def __init__(self):
                    super().__init__(
                        placeholder=lm.get('changelog_select_major_placeholder'),
                        min_values=1, max_values=1, options=options
                    )

                async def callback(self, interaction: discord.Interaction):
                    selected_major = self.values[0]
                    minor_versions = sorted(groups[selected_major], key=version_key, reverse=True)
                    
                    minor_options = [
                        SelectOption(label=v, value=v)
                        for v in minor_versions[:25]
                    ]

                    class MinorSelect(Select):
                        def __init__(self):
                            super().__init__(
                                placeholder=lm.get('changelog_select_minor_placeholder'),
                                min_values=1, max_values=1, options=minor_options
                            )

                        async def callback(self, minor_inter: discord.Interaction):
                            version = self.values[0]
                            text = await read_file(f"{changelog_dir}/{version}.txt")
                            detail_embed = discord.Embed(
                                title=lm.get('changelog_version_title').format(version=version),
                                description=text,
                                color=discord.Color.blue()
                            )
                            
                            back_button = Button(label=lm.get('changelog_back_button'), style=ButtonStyle.secondary)

                            async def back_callback(back_inter: discord.Interaction):
                                await back_inter.response.edit_message(embed=create_major_embed(), view=create_major_view())

                            back_button.callback = back_callback
                            view = View()
                            view.add_item(back_button)
                            await minor_inter.response.edit_message(embed=detail_embed, view=view)
                            logger.info(lm.get('changelog_log').format(username=minor_inter.user, version=version))

                    back_to_major_button = Button(label=lm.get('changelog_back_button'), style=ButtonStyle.secondary)
                    
                    async def back_to_major_callback(back_inter: discord.Interaction):
                        await back_inter.response.edit_message(embed=create_major_embed(), view=create_major_view())
                    
                    back_to_major_button.callback = back_to_major_callback
                    
                    view = View()
                    view.add_item(MinorSelect())
                    view.add_item(back_to_major_button)
                    
                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            title=lm.get('changelog_select_minor_title').format(major=selected_major),
                            description=lm.get('changelog_select_minor_desc'),
                            color=discord.Color.purple()
                        ),
                        view=view
                    )

            view = View()
            view.add_item(MajorSelect())
            return view

        await interaction.response.send_message(embed=create_major_embed(), view=create_major_view(), ephemeral=True)

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

    @discordClient.tree.command(name="remind", description=lm.get('remind_description'))
    async def remind(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        embed = Embed(
            title=lm.get('remind_menu_title'),
            description=lm.get('remind_menu_description'),
            color=discord.Color.blue()
        )
        view = View()

        add_btn = Button(label=lm.get('remind_add_button'), style=ButtonStyle.green, custom_id="add_reminder")
        list_btn = Button(label=lm.get('remind_list_button'), style=ButtonStyle.blurple, custom_id="list_reminders")
        delete_btn = Button(label=lm.get('remind_delete_button'), style=ButtonStyle.red, custom_id="delete_reminder")
        change_tz_btn = Button(label=lm.get('remind_change_tz_button'), style=ButtonStyle.gray, custom_id="change_timezone")

        async def add_callback(btn_inter: discord.Interaction):
            offset = await reminders_utils.reminder_manager.get_last_offset(user_id)
            if offset is None:
                await _show_timezone_selector(btn_inter, post_action="add")
            else:
                await btn_inter.response.send_modal(ReminderModal(offset))

        async def list_callback(btn_inter: discord.Interaction):
            try:
                await btn_inter.response.defer(ephemeral=True)
                await show_reminders(btn_inter)
            except Exception as e:
                logging.error(lm.get('log_remind_show_error').format(error=e))
                await btn_inter.followup.send(lm.get('remind_error_loading'), ephemeral=True)

        async def delete_callback(btn_inter: discord.Interaction):
            try:
                await btn_inter.response.defer(ephemeral=True)
                await delete_reminder_ui(btn_inter)
            except Exception as e:
                logging.error(lm.get('log_remind_delete_error').format(error=e))
                await btn_inter.followup.send(lm.get('remind_error_loading_deletion'), ephemeral=True)

        async def change_tz_callback(btn_inter: discord.Interaction):
            await _show_timezone_selector(btn_inter, post_action="change")

        add_btn.callback = add_callback
        list_btn.callback = list_callback
        delete_btn.callback = delete_callback
        change_tz_btn.callback = change_tz_callback

        for b in (add_btn, list_btn, delete_btn, change_tz_btn):
            view.add_item(b)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def show_reminders(interaction: discord.Interaction):
        try:
            reminders = await reminders_utils.reminder_manager.load_reminders(interaction.user.id)
            if not reminders:
                embed = discord.Embed(
                    title=lm.get('remind_no_active_title'),
                    description=lm.get('remind_no_active_description'),
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title=lm.get('remind_your_reminders_title'),
                color=discord.Color.blue()
            )
            for index, reminder in enumerate(reminders, start=1):
                embed.add_field(
                    name=f"{lm.get('remind_reminder')} {index}",
                    value=f"{lm.get('remind_message')}: {reminder.message}\n{lm.get('remind_time')}: {reminder.time}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logging.error(lm.get('log_remind_show_error').format(error=e))
            await interaction.followup.send(lm.get('remind_error_loading'), ephemeral=True)

    async def delete_reminder_ui(interaction: discord.Interaction):
        try:
            reminders = await reminders_utils.reminder_manager.load_reminders(interaction.user.id)
            if not reminders:
                embed = discord.Embed(
                    title=lm.get('remind_no_delete_title'),
                    description=lm.get('remind_no_delete_description'),
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            await show_reminders_for_deletion(interaction, reminders)
        except Exception as e:
            logging.error(lm.get('log_remind_delete_error').format(error=e))
            await interaction.followup.send(lm.get('remind_error_loading_deletion'), ephemeral=True)

    async def show_reminders_for_deletion(interaction: discord.Interaction, reminders: List[Reminder]):
        embed = discord.Embed(
            title=lm.get('remind_select_delete_title'),
            color=discord.Color.blue()
        )
        for index, reminder in enumerate(reminders, start=1):
            embed.add_field(
                name=f"{lm.get('remind_reminder')} {index}",
                value=f"{lm.get('remind_message')}: {reminder.message}\n{lm.get('remind_time')}: {reminder.time}",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _show_timezone_selector(inter: discord.Interaction, post_action: str):
        """
        Shows a selector for UTC−12 to UTC+11.
        post_action: "add" — open the new ReminderModal after selection,
                     "change" — just confirm the change and return the user to the menu.
        """
        view = View(timeout=120)
        options = []
        last = await reminders_utils.reminder_manager.get_last_offset(inter.user.id)
        for tz in range(-12, 12):
            offset = (tz - 3) * 60
            label = f"UTC{tz:+d}"
            desc = lm.get('remind_moscow_time') if tz == 3 else lm.get('remind_hours_from_utc').format(tz=tz)
            options.append(SelectOption(label=label, value=str(offset), description=desc, default=(last == offset)))

        select = Select(placeholder=lm.get('remind_select_timezone_placeholder'), options=options, min_values=1, max_values=1)

        async def select_cb(sel_inter: discord.Interaction):
            chosen = int(select.values[0])
            await reminders_utils.reminder_manager.set_last_offset(sel_inter.user.id, chosen)

            if post_action == "add":
                await sel_inter.response.send_modal(ReminderModal(chosen))
            else:
                await sel_inter.response.send_message(
                    lm.get('remind_timezone_saved').format(offset=chosen//60),
                    ephemeral=True
                )

        select.callback = select_cb
        view.add_item(select)
        await inter.response.send_message(lm.get('remind_select_timezone_message'), view=view, ephemeral=True)

    class ReminderModal(Modal):
        def __init__(self, utc_offset_minutes: int):
            title = f"{lm.get('remind_modal_title')} (UTC{utc_offset_minutes//60:+d})"
            super().__init__(title=title)
            self.utc_offset = utc_offset_minutes

            self.date_msk = TextInput(
                label=lm.get('remind_date_label'),
                placeholder=lm.get('remind_date_placeholder'),
                style=discord.TextStyle.short,
                required=True
            )
            self.time_msk = TextInput(
                label=lm.get('remind_time_label'),
                placeholder=lm.get('remind_time_placeholder'),
                style=discord.TextStyle.short,
                required=True
            )
            self.message = TextInput(
                label=lm.get('remind_message_label'),
                placeholder=lm.get('remind_message_placeholder'),
                style=discord.TextStyle.long,
                required=True
            )
            self.add_item(self.date_msk)
            self.add_item(self.time_msk)
            self.add_item(self.message)

        async def on_submit(self, interaction: discord.Interaction):
            logger.info(lm.get('remind_user_submitted').format(user_id=interaction.user.id, utc_offset=self.utc_offset // 60))

            try:
                msk_time = datetime.strptime(
                    f"{self.date_msk.value} {self.time_msk.value}",
                    "%d.%m.%Y %H:%M"
                )
            except ValueError:
                await interaction.response.send_message(
                    lm.get('remind_time_error'),
                    ephemeral=True
                )
                return

            reminder_time = msk_time + timedelta(minutes=-self.utc_offset)
            now = datetime.now()
            if reminder_time < now:
                await interaction.response.send_message(lm.get('remind_past_error'), ephemeral=True)
                return
            if reminder_time > now + timedelta(days=reminders_utils.MAX_FUTURE_DAYS):
                await interaction.response.send_message(lm.get('remind_future_error'), ephemeral=True)
                return

            user_id = interaction.user.id
            reminder_id = await reminders_utils.reminder_manager.add_reminder(
                user_id, self.message.value, reminder_time, self.utc_offset
            )
            if reminder_id and reminders_utils._scheduler:
                await reminders_utils._scheduler.add_reminder(
                    user_id, reminder_id, self.message.value, reminder_time
                )
            local_time = msk_time + timedelta(minutes=-self.utc_offset)

            success = Embed(
                title=lm.get('remind_set_success_title'),
                description=(
                    lm.get('remind_set_success')
                    .format(time=reminder_time.strftime('%Y-%m-%d %H:%M UTC'), message=self.message.value)
                    + lm.get('remind_set_success_local').format(local_time=local_time.strftime('%d.%m.%Y %H:%M'))
                ),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=success, ephemeral=True)
            logger.info(lm.get('remind_set_log').format(reminder_id=reminder_id, user_id=user_id))

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
