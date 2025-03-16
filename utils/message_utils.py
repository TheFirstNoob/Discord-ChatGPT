import re
import os
from discord import Embed

async def send_split_message(self, response: str, message):
    char_limit = 1900  # Лимит для обычных сообщений
    embed_char_limit = 4096  # Лимит для поля Embed
    total_embed_limit = 6000  # Общий лимит для Embed

    if hasattr(message, 'followup'):
        send_method = message.followup.send
    elif hasattr(message, 'channel'):
        send_method = message.channel.send
    else:
        raise AttributeError("send_split_message: Неподдерживаемый тип объекта для отправки сообщения")

    def split_code_block(lang, code_content):
        code_lines = code_content.split('\n')
        code_chunks = []
        current_chunk = ""

        for line in code_lines:
            if len(current_chunk) + len(line) + len(lang) + 10 > char_limit:
                code_chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        
        if current_chunk:
            code_chunks.append(current_chunk)
        
        return [f"```{lang}\n{chunk}```" for chunk in code_chunks]

    def extract_thinking(response):
        think_pattern = re.compile(r'<think>(.*?)</think>', re.DOTALL)
        reasoning_pattern = re.compile(r'Started reasoning...(.*?)Done in \d+s\.', re.DOTALL)

        think_match = think_pattern.search(response)
        reasoning_match = reasoning_pattern.search(response)

        if think_match:
            thinking_text = think_match.group(1).strip()
            response = think_pattern.sub('', response).strip()
            return thinking_text, response
        elif reasoning_match:
            thinking_text = reasoning_match.group(1).strip()
            response = reasoning_pattern.sub('', response).strip()
            return thinking_text, response
        else:
            return None, response

    async def send_embed_message(thinking_text):
        thinking_chunks = [thinking_text[i:i + embed_char_limit] for i in range(0, len(thinking_text), embed_char_limit)]

        for chunk in thinking_chunks:
            embed = Embed(
                title=":brain: Размышления ИИ...",
                description=chunk,
                color=0x3498db  # Синий цвет для размышлений
            )
            await send_method(embed=embed)

    async def smart_send(content):
        thinking_text, response = extract_thinking(content)

        if thinking_text:
            await send_embed_message(thinking_text)

        blocks = re.split(r'(```(?:[a-zA-Z]+)?\n.*?```)', response, flags=re.DOTALL)
        
        current_chunk = ""
        messages_to_send = []

        for block in blocks:
            code_match = re.match(r'```([a-zA-Z]*)\n(.*?)```', block, re.DOTALL)
            if code_match:
                lang = code_match.group(1)
                code_content = code_match.group(2)
                
                code_chunks = split_code_block(lang, code_content)
                
                for code_chunk in code_chunks:
                    if len(current_chunk + '\n' + code_chunk) > char_limit:
                        messages_to_send.append(current_chunk)
                        current_chunk = code_chunk
                    else:
                        current_chunk += '\n' + code_chunk if current_chunk else code_chunk
            else:
                lines = block.split('\n')
                for line in lines:
                    if len(current_chunk + '\n' + line) > char_limit:
                        messages_to_send.append(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += ('\n' + line) if current_chunk else line
        
        if current_chunk:
            messages_to_send.append(current_chunk)
        
        for msg in messages_to_send:
            await send_method(msg)

    await smart_send(response)