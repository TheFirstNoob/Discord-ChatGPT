import aiofiles
import json
import os
from typing import Optional, Any, Union
from pathlib import Path
from src.log import logger
from src.locale_manager import locale_manager as lm

async def read_file(filepath: Union[str, Path], encoding: str = 'utf-8') -> Optional[str]:
    """
    Read content from a file asynchronously.
    
    Args:
        filepath: Path to the file to read
        encoding: File encoding (default: utf-8)
    
    Returns:
        File content as string or None if file doesn't exist or error occurs
    """
    try:
        if os.path.exists(filepath):
            async with aiofiles.open(filepath, 'r', encoding=encoding) as file:
                return await file.read()
        return None
    except Exception as e:
        logger.error(lm.get('file_read_error').format(filepath=filepath, error=e))
        return None

async def write_file(filepath: Union[str, Path], content: str, encoding: str = 'utf-8') -> bool:
    """
    Write content to a file asynchronously.
    
    Args:
        filepath: Path to the file to write
        content: Content to write
        encoding: File encoding (default: utf-8)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if content is None:
            logger.error(lm.get('file_write_error').format(filepath=filepath, error="Content is None"))
            return False

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        async with aiofiles.open(filepath, 'w', encoding=encoding) as file:
            await file.write(content)
        return True
    except Exception as e:
        logger.error(lm.get('file_write_error').format(filepath=filepath, error=e))
        return False

async def read_json(filepath: Union[str, Path]) -> Optional[Any]:
    """
    Read and parse JSON from a file asynchronously.
    
    Args:
        filepath: Path to the JSON file
    
    Returns:
        Parsed JSON data or None if file doesn't exist or error occurs
    """
    content = await read_file(filepath)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(lm.get('file_json_read_error').format(filepath=filepath, error=e))
    return None

async def write_json(filepath: Union[str, Path], data: Any, indent: int = 4) -> bool:
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

async def append_file(filepath: Union[str, Path], content: str, encoding: str = 'utf-8') -> bool:
    """
    Append content to a file asynchronously.
    
    Args:
        filepath: Path to the file
        content: Content to append
        encoding: File encoding (default: utf-8)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        async with aiofiles.open(filepath, 'a', encoding=encoding) as file:
            await file.write(content)
        return True
    except Exception as e:
        logger.error(lm.get('file_append_error').format(filepath=filepath, error=e))
        return False

async def delete_file(filepath: Union[str, Path]) -> bool:
    """
    Delete a file asynchronously.
    
    Args:
        filepath: Path to the file to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except Exception as e:
        logger.error(lm.get('file_delete_error').format(filepath=filepath, error=e))
        return False

async def ensure_directory(directory: Union[str, Path]) -> bool:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Path to the directory
    
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(lm.get('directory_create_error').format(directory=directory, error=e))
        return False