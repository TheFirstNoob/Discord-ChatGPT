import asyncio
import aiofiles
import json
import os
import re
from typing import Any, Optional, Union
from src.log import logger
from src.locale_manager import locale_manager as lm

# Fix potential overload for import os functions... maybe its not perfect but more stable
async def run_blocking(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)

async def ensure_directory(dirpath: Union[str]) -> bool:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory: Path to the directory

    Returns:
        True if successful, False otherwise
    """
    try:
        await run_blocking(os.makedirs, dirpath, exist_ok=True)
        return True
    except Exception as e:
        logger.error(lm.get('directory_create_error').format(directory=dirpath, error=e))
        return False

async def read_file(filepath: Union[str], encoding: str = 'utf-8') -> Optional[str]:
    """
    Read content from a file asynchronously.

    Args:
        filepath: Path to the file to read
        encoding: File encoding (default: utf-8)

    Returns:
        File content as string or None if file doesn't exist or error occurs
    """
    exists = await run_blocking(os.path.exists, filepath)
    if not exists:
        return None

    try:
        async with aiofiles.open(filepath, 'r', encoding=encoding) as f:
            return await f.read()
    except Exception as e:
        logger.error(lm.get('file_read_error').format(filepath=filepath, error=e))
        return None

async def write_file(
    filepath: Union[str],
    content: Union[str, bytes],
    encoding: str = 'utf-8',
    mode: str = 'w'
) -> bool:
    """
    Write or append content to a file asynchronously.

    This function automatically handles both text and binary files:
    - For text files (mode 'w', 'a'), the encoding argument is used (default: utf-8).
    - For binary files (mode contains 'b', e.g. 'wb', 'ab'), encoding is NOT passed to aiofiles.open,
      as it is not allowed in binary mode. This is required for correct saving of binary files such as PDF, images, etc.

    Args:
        filepath: Path to the file to write
        content: Content to write (str for text, bytes for binary)
        encoding: File encoding (default: utf-8, used only for text modes)
        mode: File mode, e.g. 'w' for write, 'a' for append, 'wb' for binary write, 'ab' for binary append

    Returns:
        True if successful, False otherwise
    """
    dirpath = os.path.dirname(filepath)
    if dirpath and not await ensure_directory(dirpath):
        return False

    try:
        if 'b' in mode:
            async with aiofiles.open(filepath, mode) as f:
                await f.write(content)
        else:
            async with aiofiles.open(filepath, mode, encoding=encoding) as f:
                await f.write(content)
        return True
    except Exception as e:
        key = 'file_write_error' if mode == 'w' else 'file_append_error'
        logger.error(lm.get(key).format(filepath=filepath, error=e))
        return False

async def append_file(
    filepath: Union[str],
    content: str,
    encoding: str = 'utf-8'
) -> bool:
    """
    Append content to a file asynchronously.

    Args:
        filepath: Path to the file
        content: Content to append
        encoding: File encoding

    Returns:
        True if successful, False otherwise
    """
    return await write_file(filepath, content, encoding, mode='a')

async def delete_file(filepath: Union[str]) -> bool:
    """
    Delete a file asynchronously.

    Args:
        filepath: Path to the file to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        exists = await run_blocking(os.path.exists, filepath)
        if not exists:
            return False
        await run_blocking(os.remove, filepath)
        return True
    except Exception as e:
        logger.error(lm.get('file_delete_error').format(filepath=filepath, error=e))
        return False

async def read_json(filepath: Union[str]) -> Optional[Any]:
    """
    Read and parse JSON from a file asynchronously.

    Args:
        filepath: Path to the JSON file

    Returns:
        Parsed JSON data or None if file doesn't exist or error occurs
    """
    text = await read_file(filepath)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(lm.get('file_json_read_error').format(filepath=filepath, error=e))
        return None

async def write_json(
    filepath: Union[str],
    data: Any,
    indent: int = 4
) -> bool:
    """
    Write data as JSON to a file asynchronously.

    Args:
        filepath: Path to the JSON file
        data: Data to write as JSON
        indent: JSON indentation level (default: 4)

    Returns:
        True if successful, False otherwise
    """
    try:
        content = json.dumps(data, ensure_ascii=False, indent=indent)
        return await write_file(filepath, content)
    except Exception as e:
        logger.error(lm.get('file_json_write_error').format(filepath=filepath, error=e))
        return False

def sanitize_filename(filename: str) -> str:
    """
    Removes dangerous characters from a filename.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', os.path.basename(filename))

async def save_attachment_to_file(
    attachment,  # discord.Attachment object
    dirpath: Union[str, None],
    user_id: Union[str, int]
) -> str:
    """
    Saves a discord.Attachment to a file asynchronously.

    Args:
        attachment: discord.Attachment object
        dirpath: Directory to save to (or None for current directory)
        user_id: User ID to make the filename unique

    Returns:
        Path to the saved file
    """
    safe_filename = sanitize_filename(attachment.filename)
    if dirpath:
        await ensure_directory(dirpath)
        temp_path = os.path.join(dirpath, f"temp_doc_{user_id}_{safe_filename}")
    else:
        temp_path = f"temp_doc_{user_id}_{safe_filename}"

    content = await attachment.read()
    write_success = await write_file(temp_path, content, mode='wb')
    if not write_success:
        logger.error(lm.get('file_write_error').format(filepath=temp_path, error="Failed to save attachment"))
        raise IOError(f"Failed to save attachment to {temp_path}")
    return temp_path
