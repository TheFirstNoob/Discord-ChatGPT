import os
import json
import base64
from typing import Optional, Any
from dataclasses import dataclass
from cryptography.fernet import Fernet, InvalidToken
from src.log import logger
from utils.files_utils import read_json, write_json
from src.locale_manager import locale_manager as lm

@dataclass
class EncryptionKey:
    """Data class representing an encryption key."""
    key: bytes
    encoded_key: str

    @classmethod
    def generate(cls) -> 'EncryptionKey':
        """Generate a new encryption key."""
        key = Fernet.generate_key()
        return cls(
            key=key,
            encoded_key=base64.urlsafe_b64encode(key).decode()
        )

    @classmethod
    def from_encoded(cls, encoded_key: str) -> 'EncryptionKey':
        """Create an EncryptionKey instance from an encoded key string."""
        key = base64.urlsafe_b64decode(encoded_key)
        return cls(key=key, encoded_key=encoded_key)

class UserDataEncryptor:
    """Handles encryption and decryption of user data."""

    def __init__(self, user_id: Optional[int] = None, channel_id: Optional[int] = None):
        self.user_id = user_id
        self.channel_id = channel_id
        self.key_file = f'keys/user_{user_id}_key.json' if user_id else None
        self.cipher_suite: Optional[Fernet] = None
        self._initialized = False

    async def initialize(self) -> 'UserDataEncryptor':
        """Initialize the encryptor with a key."""
        if not self._initialized:
            # Skip encryption for channels
            if self.channel_id is not None:
                self._initialized = True
                return self

            if not os.path.exists('keys'):
                os.makedirs('keys')
            
            self.cipher_suite = await self._load_or_generate_key()
            self._initialized = True
        return self

    async def _load_or_generate_key(self) -> Optional[Fernet]:
        """Load existing key or generate a new one."""
        if not self.key_file:
            logger.error(lm.get('encryption_no_user_id'))
            return None

        try:
            if os.path.exists(self.key_file):
                key_data = await read_json(self.key_file)
                if not key_data or 'key' not in key_data:
                    logger.error(lm.get('encryption_invalid_key_file'))
                    return None
                key = EncryptionKey.from_encoded(key_data['key'])
            else:
                key = EncryptionKey.generate()
                await write_json(self.key_file, {'key': key.encoded_key})
            
            return Fernet(key.key)
        except Exception as e:
            logger.error(lm.get('encryption_key_error').format(error=e))
            return None

    async def encrypt(self, data: Any) -> Optional[str]:
        """Encrypt data and return as base64 encoded string."""
        # Skip encryption for channels
        if self.channel_id is not None:
            return json.dumps(data, ensure_ascii=False)

        if not self.cipher_suite:
            await self.initialize()
            if not self.cipher_suite:
                return None
        
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            encrypted_data = self.cipher_suite.encrypt(json_data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            logger.error(lm.get('encryption_encrypt_error').format(error=e))
            return None

    async def decrypt(self, encrypted_data: str) -> Optional[Any]:
        """Decrypt base64 encoded string back to original data."""
        # Skip decryption for channels
        if self.channel_id is not None:
            try:
                return json.loads(encrypted_data)
            except json.JSONDecodeError as e:
                logger.error(lm.get('encryption_invalid_json').format(error=e))
                return None

        if not self.cipher_suite:
            await self.initialize()
            if not self.cipher_suite:
                return None
        
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self.cipher_suite.decrypt(decoded_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except InvalidToken:
            logger.error(lm.get('encryption_invalid_token'))
            return None
        except json.JSONDecodeError:
            logger.error(lm.get('encryption_invalid_json'))
            return None
        except Exception as e:
            logger.error(lm.get('encryption_decrypt_error').format(error=e))
            return None

    async def rotate_key(self) -> bool:
        """Rotate the encryption key and re-encrypt data if needed."""
        if not self.cipher_suite:
            await self.initialize()
            if not self.cipher_suite:
                return False

        try:
            new_key = EncryptionKey.generate()
            new_cipher = Fernet(new_key.key)
            
            await write_json(self.key_file, {'key': new_key.encoded_key})
            
            self.cipher_suite = new_cipher
            return True
        except Exception as e:
            logger.error(lm.get('encryption_rotate_error').format(error=e))
            return False

    def is_initialized(self) -> bool:
        """Check if the encryptor is properly initialized."""
        return self._initialized and self.cipher_suite is not None