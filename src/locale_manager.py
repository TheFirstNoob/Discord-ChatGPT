import os
import json
from typing import Dict, Any

class LocaleManager:
    def __init__(self, locale_dir: str = 'locale'):
        self.locale_dir = locale_dir
        self.current_locale = os.getenv('LOCALE', 'ru_RU')
        self.locale_data = self._load_locale()

    def _load_locale(self) -> Dict[str, Any]:
        locale_file = os.path.join(self.locale_dir, f'{self.current_locale}.json')
        
        try:
            with open(locale_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"RU: Локализация {self.current_locale} не найдена. Используется ru_RU по умолчанию.")
            print(f"EN: Localize {self.current_locale} not found. Used ru_RU to default.")
            default_file = os.path.join(self.locale_dir, 'ru_RU.json')
            with open(default_file, 'r', encoding='utf-8') as f:
                return json.load(f)

    def get(self, key: str, default: str = '', **kwargs) -> str:
        keys = key.split('.')
        value = self.locale_data
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        
        if isinstance(value, str):
            try:
                return value.format(**kwargs)
            except KeyError:
                return value
        return default

locale_manager = LocaleManager()