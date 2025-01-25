import os
import json
import base64
from cryptography.fernet import Fernet
from src.log import logger
from utils.files_utils import read_json, write_json

class UserDataEncryptor:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.key_file = f'keys/{user_id}_key.json'
        self.cipher_suite = None

    async def initialize(self):
        if not os.path.exists('keys'):
            os.makedirs('keys')
        
        self.cipher_suite = await self._load_or_generate_key()
        return self

    async def _load_or_generate_key(self):
        try:
            if os.path.exists(self.key_file):
                key_data = await read_json(self.key_file)
                key = base64.urlsafe_b64decode(key_data['key'])
                return Fernet(key)
            else:
                key = Fernet.generate_key()
                await write_json(self.key_file, {
                    'key': base64.urlsafe_b64encode(key).decode()
                })
                return Fernet(key)
        except Exception as e:
            logger.error(f"_load_or_generate_key: Ошибка при работе с ключом: {e}")
            return None

    async def encrypt(self, data):
        if not self.cipher_suite:
            await self.initialize()
        
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            encrypted_data = self.cipher_suite.encrypt(json_data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            logger.error(f"encrypt: Ошибка шифрования: {e}")
            return None

    async def decrypt(self, encrypted_data):
        if not self.cipher_suite:
            await self.initialize()
        
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self.cipher_suite.decrypt(decoded_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception as e:
            logger.error(f"decrypt: Ошибка дешифрования: {e}")
            return None