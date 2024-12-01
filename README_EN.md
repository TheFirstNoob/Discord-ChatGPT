# [Русский](README.md) | English

# Discord ChatGPT Bot (Uses gpt4free library providers)

## All providers work and are tested in the RU region. Your experience may vary!
## Works and tested correctly on Python version 3.11.5

* **This is a heavily modified version of the bot:** [Zero6992/chatGPT-discord-bot](https://github.com/Zero6992/chatGPT-discord-bot)
* **Special thanks to Zero6992 for the open-source project <3**

---

## 📋 Table of Contents

1. [⭐️ Features](#%EF%B8%8F-features)
2. [🆕 Differences from the original version](#-differences-from-the-original-version)
3. [🛠️ Installation](#%EF%B8%8F-installation)
4. [🔨 Create your own Discord bot](#-create-your-own-discord-bot)
5. [🚀 Running the bot on Windows](#-running-the-bot-on-windows)
6. [📝 Commands](#-commands)

---

## ⭐️ Features

* 🧠 **AI Usage:** Most of the modified code is written with the help of ChatGPT and other AIs for experimentation.
* 💬 **Multifunctionality:** The bot can communicate both in a Discord channel and in private messages.
* 🌐 **Internet Support:** The bot can perform search queries, find images, and videos using the **[duckduckgo-search](https://github.com/deedy5/duckduckgo_search)** library.
* 📝 **Working with PDF:** The bot can analyze your PDF file for text content and interact with it using the **[pdfminer.six](https://github.com/pdfminer/pdfminer.six)** library. (Does not support images!)

---

## 🆕 Differences from the original version

### 🔹 Main difference: Support for individual conversation history for each user

* 🧠 **Extended AI models:** Support for more chat models and image generation models using the **[gpt4free](https://github.com/xtekky/gpt4free)** library.
* 💾 **Individual memory:** Each user has their own "memory," resettable with the `/reset` command separately.
* 📊 **Settings retention:** The AI model used is saved individually for each user.
* 📥 **Conversation history:** Ability to download the user's conversation history with the AI.

---

## 🛠️ Installation

* **Python 3.9 or later**
* **Rename the `.env.example` file to `.env`**
* In the Windows terminal, run `pip3 install -r requirements.txt` or `pip install -r requirements.txt` to install all required libraries

---

## 🔨 Create your own Discord bot

**Download the bot:** [TheFirstNoob/Discord-ChatGPT](https://github.com/TheFirstNoob/Discord-ChatGPT/archive/refs/heads/main.zip)

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. Go to the **Bot** section, get the Token, and insert it into `.env` in the line: `DISCORD_BOT_TOKEN`.
3. Enable `Server Members Intent` and `Message Content Intent`.
4. Go to the **OAuth2** section and in the **OAuth2 URL Generator** check the **Bot** option.
5. In **Bot Permissions**, check the following options:
   - View Channels
   - Send Message
   - Send Message in Thread (if needed - optional)
   - Manage Message
   - Manage Thread (if needed - optional)
   - Read Message History
   - Attach Files
   - Embed Links
   - Use Slash Commands
6. Copy the generated link and follow it.
7. Invite the bot to your Discord server.
8. Create a system chat channel and right-click to copy the channel ID.
9. Insert the channel ID into `.env` in the line: `DISCORD_CHANNEL_ID`.
10. Customize the initial prompt to your liking in the `system_prompt.txt` file.
11. Adjust other parameters in `.env` if needed.

---

## 🚀 Running the bot on Windows

* If the IDE is correctly installed, simply double-click `main.py`.
* **OR**
* Open the terminal in the bot's folder and run: `py main.py` / `python3 main.py` / `python main.py`.

**The bot is running :)**

---

## 📝 Commands

### Main
| Command        | Description                                  |
|----------------|----------------------------------------------|
| `/ask`         | Chat with AI (separate memory in DM)         |
| `/asklong`     | Chat with AI with a larger context request   |
| `/askpdf`      | Chat with AI with a PDF file (Text only)     |
| `/draw`        | Create an image using AI                     |

### Information
| Command        | Description                                  |
|----------------|----------------------------------------------|
| `/help`        | Display the list of commands                 | 
| `/about `      | Information about the project                |
| `/changelog`   | Information about changes                    |

### Management
| Command        			| Description                                  	|
|---------------------------|-----------------------------------------------|
| `/reset`       			| Reset conversation history                 	|
| `/chat-model` 			| Switch chat model                          	|
| `/history`     			| Download conversation history              	| 
