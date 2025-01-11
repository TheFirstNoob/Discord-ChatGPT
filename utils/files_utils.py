import aiofiles
import json
import os

async def read_file(filepath):
    if os.path.exists(filepath):
        async with aiofiles.open(filepath, 'r', encoding='utf-8') as file:
            return await file.read()
    return None

async def write_file(filepath, content):
    async with aiofiles.open(filepath, 'w', encoding='utf-8') as file:
        await file.write(content)

async def read_json(filepath):
    content = await read_file(filepath)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"read_json: Ошибка при чтении JSON из файла {filepath}")
    return None

async def write_json(filepath, data):
    content = json.dumps(data, ensure_ascii=False, indent=4)
    await write_file(filepath, content)