import os
import asyncio
import json
import logging
import time
import g4f.debug
from typing import Dict, List, Any

from g4f.cookies import set_cookies_dir, read_cookie_files
from g4f.client import AsyncClient
from g4f.Provider import RetryProvider
from src.aclient import _initialize_providers
from src.locale_manager import locale_manager as lm
from src.log import logger

client = AsyncClient()

g4f.debug.logging = True
g4f.debug.version_check = True

class ColoredFormatter(logging.Formatter):
    INFO_COLOR = '\x1b[34;1m'  # Синий
    ERROR_COLOR = '\x1b[31m'   # Красный
    RESET_COLOR = '\x1b[0m'    # Цвет сброса

    def format(self, record):
        if record.levelno == logging.INFO:
            record.msg = f"{self.INFO_COLOR}{record.msg}{self.RESET_COLOR}"
        elif record.levelno == logging.ERROR:
            record.msg = f"{self.ERROR_COLOR}{record.msg}{self.RESET_COLOR}"
        return super().format(record)

handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(message)s'))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Настройки
timeout = 60  # Время ожидания ответа провайдера (в секундах)
parallel_execution = False  # True — параллельно, False — последовательно

class ProviderChecker:
    def __init__(self):
        self.providers: Dict[str, RetryProvider] = {}
        self.results: List[Dict[str, Any]] = []

    async def initialize_providers(self):
        # Настройка и чтение кук выполняется один раз здесь
        cookies_dir = os.path.join(os.path.dirname(__file__), "har_and_cookies")
        set_cookies_dir(cookies_dir)
        read_cookie_files(cookies_dir)

        # Инициализация провайдеров из вашего модуля
        models = _initialize_providers()
        for model_name, provider_factory in models.items():
            self.providers[model_name] = RetryProvider(provider_factory)

    def iterate_providers(self):
        for model, retry in self.providers.items():
            for provider in retry.providers:
                yield model, provider

    async def check_provider_availability(self):
        if parallel_execution:
            await self._check_parallel()
        else:
            await self._check_sequential()
        self.save_results_to_file("results.json")

    async def _check_parallel(self):
        tasks = []
        for model, provider in self.iterate_providers():
            tasks.append(asyncio.create_task(self.check_provider(model, provider)))
            await asyncio.sleep(1)  # небольшой дилей между задачами
        await asyncio.gather(*tasks)

    async def _check_sequential(self):
        for model, provider in self.iterate_providers():
            await self.check_provider(model, provider)

    async def check_provider(self, model: str, provider):
        provider_name = provider.__name__
        logger.info(lm.get('test_send_request').format(model=model, provider=provider_name))

        try:
            start = time.time()
            res = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Привет! Как дела?"}],
                    provider=provider
                ),
                timeout=timeout
            )
            elapsed = time.time() - start
            logger.info(lm.get('test_success_response').format(
                model=model,
                provider=provider_name,
                time=elapsed,
                response=res
            ))

            if not res:
                raise ValueError(lm.get('error_empty_ai_response'))

            # Сериализуем только простые поля
            choices_data = []
            for c in res.choices:
                choices_data.append({
                    "index": c.index,
                    "message": {
                        "role": c.message.role,
                        "content": c.message.content
                    },
                    "finish_reason": c.finish_reason
                })

            usage = res.usage
            usage_data = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            }

            response_data = {
                "id": res.id,
                "model": res.model,
                "choices": choices_data,
                "usage": usage_data
            }

            self.results.append({
                "model": model,
                "provider": provider_name,
                "response": response_data,
                "response_time": elapsed
            })

        except asyncio.TimeoutError:
            err = lm.get('error_all_providers_failed')
            logger.error(err)
            self.results.append(self._error_result(model, provider_name, err))

        except Exception as e:
            err = str(e)
            logger.error(lm.get('log_provider_failed').format(provider=provider_name, error=err))
            self.results.append(self._error_result(model, provider_name, err))

    def _error_result(self, model, provider, error_msg):
        return {"model": model, "provider": provider, "error": error_msg}

    def save_results_to_file(self, filename: str):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=4)
            logger.info(lm.get('test_save_result').format(filename=filename))
        except IOError as e:
            logger.error(lm.get('file_write_error').format(filepath=filename, error=str(e)))

async def main():
    checker = ProviderChecker()
    await checker.initialize_providers()
    await checker.check_provider_availability()

if __name__ == '__main__':
    asyncio.run(main())
