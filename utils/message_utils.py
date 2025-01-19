from discord import Message
import re

async def send_split_message(self, response: str, message):
    char_limit = 1900

    if hasattr(message, 'followup'):
        send_method = message.followup.send
    elif hasattr(message, 'channel'):
        send_method = message.channel.send
    else:
        raise AttributeError("send_split_message: Неподдерживаемый тип объекта для отправки сообщения")

    async def send_chunks(chunk: str, lang: str):
        if lang:
            formatted_chunk = f"```{lang}\n{chunk}```"
        else:
            formatted_chunk = chunk
        await send_method(formatted_chunk)

    if len(response) > char_limit:
        parts = re.split(r"(```(?:[a-zA-Z]+)?\n?)", response)
        lang = ""
        is_code_block = False
        for i, part in enumerate(parts):
            if i % 2 == 1:
                match = re.match(r"```([a-zA-Z]+)?\n?", part)
                if match:
                    lang = match.group(1) or ""
                    is_code_block = True
                continue

            chunks = [part[i:i + char_limit] for i in range(0, len(part), char_limit)]
            for chunk in chunks:
                await send_chunks(chunk, lang)
            is_code_block = False
            lang = ""
    else:
        await send_method(response)
    return
