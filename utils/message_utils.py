import re

async def send_split_message(self, response: str, message):
    char_limit = 1900

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

    async def smart_send(content):
        blocks = re.split(r'(```(?:[a-zA-Z]+)?\n.*?```)', content, flags=re.DOTALL)
        
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