from __future__ import annotations

import asyncio
import sys
import unittest
import json

from g4f.client import AsyncClient
from g4f.Provider import RetryProvider

from src.aclient import _initialize_providers


class AITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.INFO = '\x1b[34;1m'
        self.ERROR = '\x1b[31m'

        self.providers = {}
        models = _initialize_providers()
        for model in models:
            self.providers[model] = RetryProvider(models[model])

        self.results = []

    async def test_provider_availability(self):
        sys.tracebacklimit = 0

        tasks = []
        for model in self.providers:
            for provider in self.providers[model].providers:
                tasks.append(self.check_provider(model, provider))

        await asyncio.gather(*tasks, return_exceptions=True)

        # Save results to a JSON file
        with open('results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=4)

    async def check_provider(self, model, provider):
        provider_name = provider.__name__
        print(f"[?] Отправляю запрос провайдеру {provider_name} используя модель {model}")
        try:
            response = await AsyncClient().chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                provider=provider
            )
            res = response.choices[0].message.content

            # Check if response is empty
            var = res[0]

            print(f"{self.INFO}[+] Ответ от модели {model} провайдера {provider_name}: {res}")
            self.results.append({
                "model": model,
                "provider": provider_name,
                "response": res
            })
        except Exception as e:
            err = str(e)
            msg = f"{self.ERROR}[-] Ошибка при отправке запроса к модели {model} провайдера {provider_name}: {err}"
            if err == "string index out of range":
                msg = f"{self.ERROR}[-] Ответ от модели {model} провайдера {provider_name} пуст! ({res})"

            self.results.append({
                "model": model,
                "provider": provider_name,
                "error": err
            })

            print(msg)


if __name__ == '__main__':
    unittest.main()