from __future__ import annotations

import asyncio
import sys
import unittest
import json
import logging

from g4f.client import Client
from g4f.Provider import RetryProvider

from src.aclient import _initialize_providers

client = Client()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Цветовые коды
INFO_COLOR = '\x1b[34;1m'
ERROR_COLOR = '\x1b[31m'
RESET_COLOR = '\x1b[0m'


class AITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.providers = {}
        models = _initialize_providers()
        for model in models:
            self.providers[model] = RetryProvider(models[model])

        self.results = []

    async def test_provider_availability(self):
        sys.tracebacklimit = 0

        for model in self.providers:
            for provider in self.providers[model].providers:
                await self.check_provider(model, provider)

        # Сохранение результатов в JSON файл
        with open('results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=4)

    async def check_provider(self, model, provider):
        provider_name = provider.__name__
        logger.info(f"[?] Отправляю запрос провайдеру {provider_name} используя модель {model}")
        try:
            response = await client.chat.completions.async_create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                provider=provider
            )
            res = response.choices[0].message.content

            # Проверка, что ответ не пустой
            var = res[0]

            logger.info(f"{INFO_COLOR}[+] Ответ от модели {model} провайдера {provider_name}: {res}{RESET_COLOR}")
            print(f"{INFO_COLOR}[+] Ответ от модели {model} провайдера {provider_name}: {res}{RESET_COLOR}")
            self.results.append({
                "model": model,
                "provider": provider_name,
                "response": res
            })
        except Exception as e:
            err = str(e)
            msg = f"{ERROR_COLOR}[-] Ошибка при отправке запроса к модели {model} провайдера {provider_name}: {err}{RESET_COLOR}"
            if err == "string index out of range":
                msg = f"{ERROR_COLOR}[-] Ответ от модели {model} провайдера {provider_name} пуст! ({res}){RESET_COLOR}"

            self.results.append({
                "model": model,
                "provider": provider_name,
                "error": err
            })

            logger.error(msg)
            print(f"{ERROR_COLOR}[-] Ошибка при отправке запроса к модели {model} провайдера {provider_name}: {err}{RESET_COLOR}")


if __name__ == '__main__':
    unittest.main()