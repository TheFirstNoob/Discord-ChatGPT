from __future__ import annotations

import sys
import unittest
import json
import asyncio

from asgiref.sync import sync_to_async
from g4f.client import Client
from g4f.Provider import (
    Airforce, Blackbox, Bixin123, Binjie, ChatGot, Chatgpt4o, ChatgptFree,
    DDG, DeepInfraImage, FreeChatgpt, Free2GPT, HuggingChat, HuggingFace, Nexra, # Do not delete huggingFace
    ReplicateHome, Liaobots, LiteIcoding, PerplexityLabs, Pi, TeachAnything,
    Pizzagpt, RetryProvider
)


class AITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.INFO = '\x1b[34;1m'
        self.ERROR = '\x1b[31m'

        self.providers = {
            "gpt-3.5-turbo": RetryProvider([FreeChatgpt, Nexra], shuffle=False),
            "gpt-4": RetryProvider([Nexra, Binjie, Airforce, Liaobots], shuffle=False),
            "gpt-4-turbo": RetryProvider([Nexra, Airforce, Liaobots], shuffle=False),
            "gpt-4o-mini": RetryProvider([Pizzagpt, ChatgptFree, Airforce, DDG, Liaobots], shuffle=False),
            "gpt-4o": RetryProvider([Chatgpt4o, LiteIcoding, Airforce, Liaobots], shuffle=False),
            "claude-3-haiku": RetryProvider([DDG, Liaobots], shuffle=False),
            "blackbox": RetryProvider([Blackbox], shuffle=False),
            "gemini-flash": RetryProvider([Blackbox, Liaobots], shuffle=False),
            "gemini-pro": RetryProvider([ChatGot, Liaobots], shuffle=False),
            "gemma-2b": RetryProvider([ReplicateHome], shuffle=False),
            "command-r-plus": RetryProvider([HuggingChat], shuffle=False),
            "llama-3.1-70b": RetryProvider([HuggingChat, Blackbox, TeachAnything, Free2GPT, DDG], shuffle=False),
            "llama-3.1-405b": RetryProvider([Blackbox], shuffle=False),
            "llama-3.1-sonar-large-128k-online": RetryProvider([PerplexityLabs], shuffle=False),
            "llama-3.1-sonar-large-128k-chat": RetryProvider([PerplexityLabs], shuffle=False),
            "pi": RetryProvider([Pi], shuffle=False),
            "qwen-turbo": RetryProvider([Bixin123], shuffle=False),
            "qwen-2-72b": RetryProvider([Airforce], shuffle=False),
            "mixtral-8x7b": RetryProvider([HuggingChat, ReplicateHome, DDG], shuffle=False),
            "mixtral-8x7b-dpo": RetryProvider([HuggingChat], shuffle=False),
            "mistral-7b": RetryProvider([HuggingChat], shuffle=False),
            "yi-1.5-9b": RetryProvider([FreeChatgpt], shuffle=False),
            "SparkDesk-v1.1": RetryProvider([FreeChatgpt], shuffle=False),
        }
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
            async_create = sync_to_async(Client().chat.completions.create)
            response = await async_create(
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