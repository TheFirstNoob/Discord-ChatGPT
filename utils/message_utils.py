from discord import Message, Interaction
import re

async def send_split_message(self, response: str, message):
    char_limit = 1900

    async def send_chunks(chunk: str, lang: str, channel):
        if lang:
            await channel.send(f"```{lang}\n{chunk}```")
        else:
            await channel.send(chunk)

    if hasattr(message, 'followup'):
        channel = message.channel
        send_method = message.followup.send
    elif hasattr(message, 'channel'):
        channel = message.channel
        send_method = message.channel.send
    else:
        raise AttributeError("send_split_message: Неподдерживаемый тип объекта для отправки сообщения")

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

            for j, chunk in enumerate(chunks):
                if is_code_block:
                    if j == 0:
                        await send_chunks(chunk, lang, channel)
                    else:
                        await send_chunks(chunk, lang, channel)
                else:
                    await send_chunks(chunk, "", channel)

            is_code_block = False
            lang = ""
    else:
        await channel.send(response)

    return
