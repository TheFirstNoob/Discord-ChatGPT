from discord import Message, Interaction

async def send_split_message(self, response: str, message):
    char_limit = 1900

    async def send_chunks(chunk: str, is_code: bool, channel):
        if is_code:
            await channel.send(f"```{chunk}```")
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
        parts = response.split("```")
        is_code_block = False

        for part in parts:
            chunks = [part[i:i + char_limit] for i in range(0, len(part), char_limit)]
            for chunk in chunks:
                await send_chunks(chunk, is_code_block, channel)
            is_code_block = not is_code_block
    else:
        await channel.send(response)

    return