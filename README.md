# Русский | [English](README_EN.md)

# Discord ChatGPT Bot (Использует провайдеров gpt4free библиотеки)

## Все провайдеры работают и протестированы в Ру регионе. У вас все может работать иначе!
## Работает и протестировано корректно на версии Python 3.11.5

* **Это сильно модифицированная версия бота:** [Zero6992/chatGPT-discord-bot](https://github.com/Zero6992/chatGPT-discord-bot)
* **Отдельно спасибо Zero6992 за открытый код проекта <3**

---

## 📋 Содержание

1. [⭐️ Особенности](#%EF%B8%8F-особенности)
2. [🆕 Отличия от начальной версии](#-отличия-от-начальной-версии)
4. [🚧 ПЛАНЫ на 2025](#-планы-на-2025)
5. [🛠️ Установка](#%EF%B8%8F-установка)
6. [🔨 Создайте своего Discord бота](#-создайте-своего-discord-бота)
7. [🚀 Запуск бота на Windows](#-запуск-бота-на-windows)
8. [📝 Команды](#-команды)

---

## ⭐️ Особенности

* 🧠 **Использование ИИ:** Большая часть модифицированного кода написана с помощью ChatGPT и других ИИ для эксперимента.
* 💬 **Многофункциональность:** Бот может общаться как в канале Discord, так и в личных сообщениях. Можно использовать как слеш-команды, так и упоминание через @.
* 🌐 **Интернет-доступ:** Бот может выполнять поисковые запросы, находить изображения и видео через библиотеку **[duckduckgo-search](https://github.com/deedy5/duckduckgo_search)**.
* 📝 **Работа с PDF:** Бот может изучить ваш PDF файл на содержимое текста и работать с ним через библиотеку **[pdfminer.six](https://github.com/pdfminer/pdfminer.six)**. (Не поддерживает картинки!)
* 🔔 **Напоминания:** Бот может напомнить вам о важном событии такие как Экзамены, сессия, ДедЛайны и так далее. Поддерживаются как актуальные напоминания так и уведомления о просроченных.
* 🔨 **Администрирование:** Администратор может управлять доступом к боту для каждого пользователя.
* 🔑 **Поддержка шифрования:** Продвинутая защита данных с помощью шифрования Fernet, гарантирующая конфиденциальность пользовательских взаимодействий и персональной информации.

---

## 🆕 Отличия от начальной версии

### 🔹 Главное отличие: Поддержка истории диалога с каждым пользователем отдельно

* 🧠 **Расширенные ИИ модели:** Поддержка большего количества чат-моделей и моделей генерации изображений с использованием библиотеки **[gpt4free](https://github.com/xtekky/gpt4free)**.
* 💾 **Индивидуальная память:** У каждого пользователя своя "память", сбрасываемая командой `/reset` отдельно.
* 📊 **Выбор модели и Инструкции:** Используемая модель ИИ и набор инструкций сохраняются индивидуально для каждого пользователя.
* 📥 **История диалогов:** Возможность скачивания истории диалога пользователя с ИИ.

---

## 🚧 ПЛАНЫ на 2025

<details>
   <summary>
   
   ### Новый планируемый функционал

   </summary>
   
- **Поддержка потоковых сообщений**: Реализовать функцию потоковых сообщений в Discord через функцию редактирования, при этом правильно разделять на части для чанков.
	> - Например добавить `/settings`, чтобы пользователи могли настраивать свои параметры.
	> - Установить минимальную задержку в 1 секунду между сообщениями, чтобы предотвратить спам и потенциальные проблемы.
- **Интеграция моделей зрения**: Внедрить поддержку моделей зрения для улучшения функциональности.
- **Поддержка агентов**: Добавить возможности для агентов, аналогичных агентам Blackbox.
- **Локализация**: Локализовать весь код для улучшения доступности для пользователей из разных регионов.
- **Интеграция Google Search**: Добавить поиск по интернету через Google для улучшенного поиска информации.
- **Интеграция WolframAlpha**: Добавить WolframAlpha для предоставления вычислительных знаний.
- **Интеграция DeepL**: Добавить DeepL для расширенных возможностей перевода.
- **Discord UI**: Улучшить визуальную составляющую бота с помощью UI. Например: Ember-сообщения и/или интерактивные кнопки (например, "Сгенерировать заново").
- **Интеграция базы данных**: Использовать MySQL/NoSQL или другую базу данных для хранения сообщений пользователей в зависимости от настроек конфигурации по мимо текущего json.
- **Постоянная память**: Реализовать постоянную память для каждого пользователя для сохранения пользовательских инструкций и предпочтений.
- **Новое новое новое, ищем новое**: Изучить возможность интеграции дополнительных услуг и продуктов для расширения функциональности.
  
</details>

<details>
   <summary>
   
   ### Улучшения бота

   </summary>
   	
- **Оптимизация потоковых сообщений**: Дальнейшая оптимизация функции `utils/message_split` для улучшения производительности после добавления потоковых сообщениях.
- **Улучшенный веб-поиск**: Улучшить возможности веб-поиска для изображений и видео. Преобразовать сообщения пользователей для повышения точности поиска и реализовать определение языка для оптимальных результатов.
		
    > **Пример запроса пользователя**: "Я хочу научиться основам C++" (с request_type = videos)
	> 	
    > - **Текущая реализация**:
	> 		- Отправляет видео с YouTube с текстом: "Я хочу научиться основам C++"
	> 		- Предоставляет неправильные ссылки.
	> 	
    > - **Желаемая реализация**:
	> 		- Преобразовать сообщение пользователя для точного поиска.
	> 		- Отправить видео с YouTube после преобразования: "C++ для начинающих" (или "Основы C++").
	> 		- Предоставить пользователю правильные ссылки.

- **Оптимизация кода**: Переделать структуру и оптимизировать код для повышения производительности и удобства дальнейшего улучшения.
- **Усиление безопасности и стабильности**: Укрепить меры безопасности всех параметров, а так же данных пользователей и улучшить общую стабильность.
- **Улучшение README**: Повысить ясность и полноту документации README.
- **Документация для кода**: Добавить подробную документацию для всех компонентов кода, чтобы каждый мог понять что и как.
- **Улучшение логирования**: Улучшить логирование для лучшего отслеживания проблем и отладки этих проблем.

</details>

---

## 🛠️ Установка

* **Python 3.10 или позднее**
* **Переименуйте файл `.env.example` в `.env`**
* В терминале Windows выполните `pip3 install -r requirements.txt` или `pip install -r requirements.txt` чтобы установить все требуемые библиотеки

---

## 🔨 Создайте своего Discord бота

**Скачайте бота:** [Latest Release](https://github.com/TheFirstNoob/Discord-ChatGPT/releases)  
> [!WARNING]
> **Пожалуйста используйте ТОЛЬКО релиз версии!**  
> Прямое скачивание Main-версий может привести к нестабильной работе по разным причинам.  

1. Перейдите на [Discord Developer Portal](https://discord.com/developers/applications) и создайте приложение.
2. Перейдите в раздел **Bot**, получите Token и вставьте его в `.env` в строку: `DISCORD_BOT_TOKEN`.
3. Установите `Server Members Intent` и `Message Content Intent` на **Включено**.
4. Перейдите в раздел **OAuth2** и в **OAuth2 URL Generator** поставьте галочку на **Bot**.
5. В **Bot Permissions** поставьте галочки на следующие пункты:
   - View Channels
   - Send Message
   - Send Message in Thread (если нужно - не обязательно)
   - Manage Message
   - Manage Thread (если нужно - не обязательно)
   - Read Message History
   - Attach Files
   - Embed Links
   - Use Slash Commands
6. Скопируйте полученную ссылку и перейдите по ней.
7. Пригласите бота в свой Discord сервер.
8. Создайте системный канал чата и через ПКМ скопируйте ID канала.
9. Вставьте ID канала в `.env` в строку: `DISCORD_CHANNEL_ID`.
10. Настройте стартовый промпт на ваш вкус в файле `system_prompt.txt`.
11. Настройте остальные параметры в `.env`, если нужно.

---

## 🚀 Запуск бота на Windows

* Если корректно установлен IDE, просто двойным кликом запустите `main.py`.
* **ИЛИ**
* Откройте терминал в папке с ботом и выполните: `py main.py` / `python3 main.py` / `python main.py`.

**Бот запущен :)**

---

## 📝 Команды

### Основные
| Команда           | Описание                                  |
|-------------------|-------------------------------------------|
| `/ask`            | Чат с ИИ (в ЛС отдельная память)			|
| `/asklong`        | Чат с ИИ с большим контекстным запросом   |
| `/asklong`        | Чат с ИИ с PDF файлами (Только текст)     |
| `/draw`           | Создать изображение с помощью ИИ          |

### Информация
| Команда        | Описание                                 |
|----------------|------------------------------------------|
| `/help`        | Вывести список команд                    |
| `/about`       | Информация о проекте                     |
| `/changelog`   | Информация об изменениях                 |

### Напоминания
| Команда           | Описание                            |
|-------------------|-------------------------------------|
| `/remind-add`     | Создать напоминание                 |
| `/remind-list`    | Показать список ваших напоминаний   |
| `/remind-delete`  | Удалить напоминание (Через Индекс)  |

### Инструкции
| Команда               | Описание                    |
|-----------------------|-----------------------------|
| `/instruction-set`    | Установить инстукцию для ИИ |
| `/instruction-reset ` | Сбросить инстукцию для ИИ   |

### Администрирование
| Команда         | Описание                    |
|-----------------|-----------------------------|
| `/ban`     	  | Заблокировать пользователя  |
| `/unban`    	  | Разблокировать пользователя |
| `/banned-list ` | Список забаненных  			|

### Управление
| Команда        			| Описание                      |
|---------------------------|-------------------------------|
| `/reset`       			| Сбросить историю диалога      |
| `/chat-model` 			| Сменить чат модель            |
| `/history`     			| Скачать историю диалога       |
