import os
import asyncio
import json
import logging
import time
import g4f.debug

from g4f.cookies import set_cookies_dir, read_cookie_files
from g4f.client import AsyncClient
from g4f.Provider import RetryProvider
from src.aclient import _initialize_providers

client = AsyncClient()

g4f.debug.logging = True
g4f.debug.version_check = True

cookies_dir = os.path.join(os.path.dirname(__file__), "har_and_cookies")
set_cookies_dir(cookies_dir)
read_cookie_files(cookies_dir)

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
timeout = 60  # Время ожидания ответа провайдера (В секундах)
parallel_execution = False  # Установите: True для параллельной работы (быстрее, но Нестабильно!), False для последовательной (Рекомендуемо!)

class ProviderChecker:
    def __init__(self):
        self.providers = {}
        self.results = []

    async def initialize_providers(self):
        models = _initialize_providers()
        for model in models:
            self.providers[model] = RetryProvider(models[model])

    async def iterate_providers(self):
        for model in self.providers:
            for provider in self.providers[model].providers:
                yield model, provider

    async def check_provider_availability(self):
        if parallel_execution:
            await self.check_provider_availability_parallel()
        else:
            await self.check_provider_availability_sequential()
        
        self.save_results_to_file("results.json")

    async def check_provider_availability_parallel(self):
        tasks = []
        async for model, provider in self.iterate_providers():
            task = asyncio.create_task(self.check_provider(model, provider))
            tasks.append(task)
            await asyncio.sleep(1)

        await asyncio.gather(*tasks)

    async def check_provider_availability_sequential(self):
        async for model, provider in self.iterate_providers():
            await self.check_provider(model, provider)

    async def check_provider(self, model, provider):
        provider_name = provider.__name__
        logger.info(f"[?] Отправляем запрос к модели: {model} Провайдер: {provider_name}")

        try:
            start_time = time.time()
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hello!"}],
                    provider=provider
                ),
                timeout=timeout
            )
            elapsed_time = time.time() - start_time
            res = response.choices[0].message.content

            if not res:
                logger.error(f"[-] Пустой ответ от модели: {model} Провайдер: {provider_name}.")
                self.results.append(self.create_error_result(model, provider_name, "Пустой ответ."))
                return

            logger.info(f"[+] Успешный ответ от модели: {model} Провайдер: {provider_name} за {elapsed_time:.2f} сек: {res}")
            self.results.append(self.create_success_result(model, provider_name, res, elapsed_time))

        except asyncio.TimeoutError:
            logger.error(f"[-] Тайм-аут модели: {model} Провайдер: {provider_name}.")
            self.results.append(self.create_error_result(model, provider_name, "Тайм-Аут! Провайдер не ответил за требуемое время."))

        except Exception as e:
            logger.error(f"[-] Ошибка при отправке запроса к модели: {model} Провайдер: {provider_name}: {str(e)}")
            self.results.append(self.create_error_result(model, provider_name, str(e)))

    def create_success_result(self, model, provider_name, response, elapsed_time):
        return {
            "model": model,
            "provider": provider_name,
            "response": response,
            "response_time": elapsed_time
        }

    def create_error_result(self, model, provider_name, error):
        return {
            "model": model,
            "provider": provider_name,
            "error": error
        }

    def save_results_to_file(self, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=4)
            logger.info(f"[+] Результат сохранен в файл: {filename}")
        except IOError as e:
            logger.error(f"[-] Ошибка сохранения результата: {filename}: {str(e)}")

async def main():
    checker = ProviderChecker()
    await checker.initialize_providers()
    await checker.check_provider_availability()

if __name__ == '__main__':
    asyncio.run(main())