import unittest
from g4f.client import Client
from g4f.Provider import (
    AiChatOnline, AiChats, Blackbox, Airforce, Bixin123, Binjie, CodeNews, ChatGot, Chatgpt4o, ChatgptFree,
    Chatgpt4Online,
    DDG, DeepInfra, DeepInfraImage, FreeChatgpt, FreeGpt, Free2GPT, FreeNetfly, Koala, HuggingChat, HuggingFace, Nexra,
    ReplicateHome, Liaobots, LiteIcoding, MagickPen, Prodia, PerplexityLabs, Pi, TeachAnything, TwitterBio, Snova, You,
    Pizzagpt, RetryProvider
)


class AITests(unittest.TestCase):
    def test_provider_availability(self):
        providers = {
            "gpt-3.5-turbo": RetryProvider([FreeChatgpt, FreeNetfly, Bixin123, Nexra, TwitterBio, Airforce],
                                           shuffle=False),
            "gpt-4": RetryProvider([Chatgpt4Online, Nexra, Binjie, FreeNetfly, AiChats, Airforce, You, Liaobots],
                                   shuffle=False),
            "gpt-4-turbo": RetryProvider([Nexra, Bixin123, Airforce, You, Liaobots], shuffle=False),
            "gpt-4o-mini": RetryProvider(
                [Pizzagpt, AiChatOnline, ChatgptFree, CodeNews, You, FreeNetfly, Koala, MagickPen, Airforce, DDG,
                 Liaobots], shuffle=False),
            "gpt-4o": RetryProvider([Chatgpt4o, LiteIcoding, AiChatOnline, Airforce, You, Liaobots], shuffle=False),
            "claude-3-haiku": RetryProvider([DDG, Liaobots], shuffle=False),
            "blackbox": RetryProvider([Blackbox], shuffle=False),
            "gemini-flash": RetryProvider([Blackbox, Liaobots], shuffle=False),
            "gemini-pro": RetryProvider([ChatGot, Liaobots], shuffle=False),
            "gemma-2b": RetryProvider([ReplicateHome], shuffle=False),
            "command-r-plus": RetryProvider([HuggingChat, HuggingFace], shuffle=False),
            "llama-3.1-70b": RetryProvider(
                [HuggingChat, HuggingFace, Blackbox, DeepInfra, FreeGpt, TeachAnything, Free2GPT, Snova, DDG],
                shuffle=False),
            "llama-3.1-405b": RetryProvider([Blackbox, Snova], shuffle=False),
            "llama-3.1-sonar-large-128k-online": RetryProvider([PerplexityLabs], shuffle=False),
            "llama-3.1-sonar-large-128k-chat": RetryProvider([PerplexityLabs], shuffle=False),
            "pi": RetryProvider([Pi], shuffle=False),
            "qwen-turbo": RetryProvider([Bixin123], shuffle=False),
            "qwen-2-72b": RetryProvider([Airforce], shuffle=False),
            "mixtral-8x7b": RetryProvider([HuggingChat, HuggingFace, ReplicateHome, TwitterBio, DeepInfra, DDG],
                                          shuffle=False),
            "mixtral-8x7b-dpo": RetryProvider([HuggingChat, HuggingFace], shuffle=False),
            "mistral-7b": RetryProvider([HuggingChat, HuggingFace, DeepInfra], shuffle=False),
            "yi-1.5-9b": RetryProvider([FreeChatgpt], shuffle=False),
            "SparkDesk-v1.1": RetryProvider([FreeChatgpt], shuffle=False),
        }

        for model in providers:
            # Replace all broken names
            model = model.replace("3_5", "3.5")
            model = model.replace("3_1", "3.1")
            model = model.replace("1_5", "1.5")
            model = model.replace("1_1", "1.1")

            with self.subTest(model=str(model)):
                for provider in providers[model].providers:
                    provider_name = provider.__name__
                    with self.subTest(provider=provider_name):
                        print(f"[+] Отправляю запрос провайдеру {provider_name} используя модель {model}")
                        try:
                            client = Client()
                            response = client.chat.completions.create(
                                model=model,
                                messages=[{"role": "user", "content": "Hello"}],
                                provider=provider
                            )
                            res = response.choices[0].message.content

                            # Check if response is empty
                            var = res[0]

                            print(f"    - Ответ от модели {model} провайдера {provider_name}: {res}")
                        except Exception as e:
                            if str(e) == "string index out of range":
                                self.fail(f"Ответ от модели {model} провайдера {provider_name} пуст! ({res})")
                            else:
                                self.fail(
                                    f"Ошибка при отправке запроса к модели {model} провайдера {provider_name}: {e}")


if __name__ == '__main__':
    unittest.main()
