from discord import Message

async def send_split_message(self, response: str, message: Message):
    char_limit = 1900

    async def send_chunks(chunk: str, is_code: bool):
        if is_code:
            await message.followup.send(f"```{chunk}```")
        else:
            await message.followup.send(chunk)

    if len(response) > char_limit:
        parts = response.split("```")
        is_code_block = False

        for part in parts:
            chunks = [part[i:i + char_limit] for i in range(0, len(part), char_limit)]
            for chunk in chunks:
                await send_chunks(chunk, is_code_block)
            is_code_block = not is_code_block
    else:
        await message.followup.send(response)

    return