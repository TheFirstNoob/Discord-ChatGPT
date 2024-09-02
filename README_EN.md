# English | [Русский](README.md)

# Discord ChatGPT Bot (Used gpt4free provider libs)
## All providers are operational and tested in the RU region. Your experience may vary!
## Works correctly on Python version 3.11.5

* **This is a heavily modified version of the bot: https://github.com/Zero6992/chatGPT-discord-bot/**
* **Special thanks to Zero6992 for the open-source project <3**

# Features
* **Most of the modified code was written using ChatGPT and other AI models for Experiment**
* **The bot can communicate both in Discord channels and in direct messages**

# Differences from the original version
## The main difference is the support for conversation history for each user separately

* A larger number of chat models using the **gpt4free** library: https://github.com/xtekky/gpt4free
* Support for SDXL and FLUX models for image generation
* Support for "memory" for each user that does not reset upon bot restart
* Memory `/reset` works individually for users, not globally (none)
* Saving the used AI model for each user individually

-----

# Installation
* **Python 3.9 or later**
* **Rename the file `.env.example` to `.env`**
* In the Windows Terminal, run `pip3 install -r requirements.txt` | `pip install -r requirements.txt` to install all required libraries
-----
## Create your Discord bot
Download build bot: https://github.com/TheFirstNoob/Discord-ChatGPT/archive/refs/heads/main.zip

1. Go to https://discord.com/developers/applications and create an application
2. Navigate to the **Bot** section, obtain the Token, and insert it into `.env` in the line: `DISCORD_BOT_TOKEN`
3. Enable `Server Members Intent` and `Message Content Intent`
4. Go to the **OAuth2** section and in the **OAuth2 URL Generator**, check the box for ***Bot***
5. In **Bot Permissions**, check the following options:
   - View Channels
   - Send Messages
   - Send Messages in Threads (if needed - optional)
   - Manage Messages
   - Manage Threads (if needed - optional)
   - Read Message History
   - Attach Files (for future updates)
   - Embed Links
   - Use Slash Commands
6. Copy the generated link and navigate to it
7. Invite the bot to your Discord server
8. Create a system chat channel and right-click to copy the channel ID
9. Insert the Channel ID into `.env` in the line: `DISCORD_CHANNEL_ID`
10. Go to https://deepinfra.com/dash/api_keys and create your API key
11. Insert the DeepInfra API key into `.env` in the line `DEEPINFRA_API_KEY`
12. Customize the starting prompt to your liking in the `system_prompt.txt` file
-----
## Running the bot on Windows
* If your IDE is correctly set up, simply double-click `main.py` to run it
* **OR**
* Open a terminal in the bot's folder and type: `py main.py` / `python3 main.py` / `python main.py`

**The bot is running :)**
-----
## Commands

**MAIN:**
1. `/ask {prompt} {Additional query}`: Chat with AI (a separate memory of your queries is created in DMs)
2. `/draw {prompt} {Service}`: Create an image using the SDXL or FLUX model

**INFORMATION:**
1. `/help`: Display information on how to use Hitagi ChatGPT (shows a list of commands)
2. `/modelinfo`: Display information about a specific model (includes my examples)
3. `/info`: Display information about the Hitagi ChatGPT project (includes my example)
4. `/changelog`: Display information about changes in a specific version (includes my examples)

**MANAGEMENT:**
1. `/reset`: Reset your conversation history
2. `/chat-model {AI model}`: Change the chat model
