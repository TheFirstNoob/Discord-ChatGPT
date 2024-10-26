from __future__ import annotations

import asyncio
import sys
import unittest
import json
import logging
import time

from g4f.client import Client
from g4f.Provider import RetryProvider
from src.aclient import _initialize_providers

client = Client()

class ColoredFormatter(logging.Formatter):
    INFO_COLOR = '\x1b[34;1m'  # Синий
    ERROR_COLOR = '\x1b[31m'   # Красный
    RESET_COLOR = '\x1b[0m'    # Сброс цвета

    def format(self, record):
        if record.levelno == logging.INFO:
            record.msg = f"{self.INFO_COLOR}{record.msg}{self.RESET_COLOR}"
        elif record.levelno == logging.ERROR:
            record.msg = f"{self.ERROR_COLOR}{record.msg}{self.RESET_COLOR}"
        return super().format(record)

# Настройка логирования
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(message)s'))
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
logger.addHandler(handler)

# Конфиг
CONFIG = {
    "timeout": 30,  # Тайм-аут в секундах
}

class AITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Инициализация провайдеров перед каждым тестом."""
        self.providers = {}
        models = _initialize_providers()
        for model in models:
            self.providers[model] = RetryProvider(models[model])

        self.results = []

    async def test_provider_availability(self):
        """Тест доступности всех провайдеров."""
        sys.tracebacklimit = 0

        for model in self.providers:
            for provider in self.providers[model].providers:
                await self.check_provider(model, provider)

        # Сохранение результатов в JSON файл
        with open('results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=4)

    async def check_provider(self, model, provider):
        """Проверка конкретного провайдера с тайм-аутом."""
        provider_name = provider.__name__
        logger.info(f"[?] Отправляю запрос провайдеру {provider_name} используя модель {model}")

        try:
            start_time = time.time()
            response = await asyncio.wait_for(
                client.chat.completions.async_create(
                    model=model,
                    messages=[{"role": "user", "content": "Hello"}],
                    provider=provider
                ),
                timeout=CONFIG["timeout"]
            )
            elapsed_time = time.time() - start_time
            res = response.choices[0].message.content

            if not res:
                raise ValueError("Ответ пустой.")

            logger.info(f"[+] Ответ от модели {model} провайдера {provider_name} за {elapsed_time:.2f} сек: {res}")
            self.results.append({
                "model": model,
                "provider": provider_name,
                "response": res,
                "response_time": elapsed_time
            })

        except asyncio.TimeoutError:
            logger.error(f"[-] Тайм-аут при запросе к модели {model} провайдера {provider_name}.")
            self.results.append({
                "model": model,
                "provider": provider_name,
                "error": "Тайм-аут! Провайдер не ответил за отведенное время."
            })

        except Exception as e:
            err = str(e)
            logger.error(f"[-] Ошибка при отправке запроса к модели {model} провайдера {provider_name}: {err}")
            self.results.append({
                "model": model,
                "provider": provider_name,
                "error": err
            })

if __name__ == '__main__':
    unittest.main()