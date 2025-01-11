import os
import asyncio
from datetime import datetime
from typing import List, Dict
from utils.files_utils import read_json, write_json
from src.log import logger

REMINDERS_DIR = 'reminders'

async def get_reminders_filepath(user_id: int) -> str:
    return os.path.join(REMINDERS_DIR, f'{user_id}_reminders.json')

async def load_reminders(user_id: int) -> List[Dict]:
    filepath = await get_reminders_filepath(user_id)
    return await read_json(filepath) or []

async def save_reminders(user_id: int, reminders: List[Dict]):
    filepath = await get_reminders_filepath(user_id)
    await write_json(filepath, reminders)

async def check_reminders(client):
    if hasattr(client, '_reminders_running') and client._reminders_running:
        return
    
    client._reminders_running = True
    logger.info("Запуск проверки напоминаний...")
    
    try:
        while True:
            try:
                await asyncio.sleep(10)
                current_time = datetime.now()
                user_ids = os.listdir(REMINDERS_DIR)

                for user_file in user_ids:
                    user_id = int(user_file.split('_')[0])
                    reminders = await load_reminders(user_id)

                    for reminder in reminders[:]:
                        reminder_time = datetime.fromisoformat(reminder['time'])

                        if (reminder_time.year == current_time.year and
                            reminder_time.month == current_time.month and
                            reminder_time.day == current_time.day and
                            reminder_time.hour == current_time.hour and
                            reminder_time.minute == current_time.minute):
                            
                            try:
                                user = await client.fetch_user(user_id)
                                if user:
                                    await user.send(f"> :alarm_clock: **Привет! :wave: Вы просили меня напомнить вас о:** \n {reminder['message']}")
                                    logger.info(f"check_reminders: Отправлено напоминание пользователю {user_id}: {reminder['message']}")
                                    reminders.remove(reminder)
                            except Exception as e:
                                logger.error(f"check_reminders: Ошибка при обработке напоминания: {e}")

                        elif reminder_time < current_time:
                            try:
                                user = await client.fetch_user(user_id)
                                if user:
                                    await user.send(f"> :warning: **Извините :persevere: , из-за технических проблем с нашей стороны мы не смогли вовремя напомнить вам о:** \n> {reminder['message']}")
                                    logger.info(f"check_reminders: Просроченное напоминание для пользователя {user_id}: {reminder['message']}")
                                    reminders.remove(reminder)
                            except Exception as e:
                                logger.error(f"check_reminders: Ошибка при обработке просроченного напоминания: {e}")
                    
                    await save_reminders(user_id, reminders)
            except Exception as e:
                logger.error(f"check_reminders: Ошибка в цикле проверки напоминаний: {e}")
                await asyncio.sleep(30)
    finally:
        client._reminders_running = False