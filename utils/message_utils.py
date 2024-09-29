from discord import Message

async def send_split_message(self, response: str, message: Message):
    char_limit = 1900
    if len(response) > char_limit:
        parts = response.split("```")
        is_code_block = False

        for i in range(len(parts)):
            part = parts[i]
            if is_code_block:
                code_block_chunks = [part[j:j+char_limit] for j in range(0, len(part), char_limit)]
                for chunk in code_block_chunks:
                    await message.followup.send(f"```{chunk}```")
            else:
                non_code_chunks = [part[j:j+char_limit] for j in range(0, len(part), char_limit)]
                for chunk in non_code_chunks:
                    await message.followup.send(chunk)
            is_code_block = not is_code_block
    else:
        await message.followup.send(response)

    return
