import os
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from utils.files_utils import read_json, write_json
from src.log import logger

class ReminderManager:
    def __init__(self, reminders_dir='reminders'):
        self.reminders_dir = reminders_dir
        os.makedirs(reminders_dir, exist_ok=True)
        self._reminders_running = False

    async def get_reminders_filepath(self, user_id: int) -> str:
        return os.path.join(self.reminders_dir, f'{user_id}_reminders.json')

    async def load_reminders(self, user_id: int) -> List[Dict]:
        filepath = await self.get_reminders_filepath(user_id)
        try:
            return await read_json(filepath) or []
        except Exception as e:
            logger.error(f"load_reminders: Ошибка при чтении файла напоминаний для пользователя {user_id}: {e}")
            return []

    async def save_reminders(self, user_id: int, reminders: List[Dict]):
        filepath = await self.get_reminders_filepath(user_id)
        try:
            await write_json(filepath, reminders)
        except Exception as e:
            logger.error(f"save_reminders: Ошибка при записи файла напоминаний для пользователя {user_id}: {e}")

    async def add_reminder(self, user_id: int, message: str, reminder_time: datetime) -> Optional[str]:
        reminders = await self.load_reminders(user_id)

        reminder_id = str(datetime.now().timestamp())
        reminder = {
            'id': reminder_id,
            'message': message,
            'time': reminder_time.isoformat()
        }
        reminders.append(reminder)
        await self.save_reminders(user_id, reminders)
        return reminder_id

    async def remove_reminder(self, user_id: int, reminder_id: str) -> bool:
        reminders = await self.load_reminders(user_id)
        initial_count = len(reminders)

        reminders = [r for r in reminders if r['id'] != reminder_id]
        
        if len(reminders) < initial_count:
            await self.save_reminders(user_id, reminders)
            return True
        return False

    async def check_reminders(self, client):
        if self._reminders_running:
            return

        self._reminders_running = True
        logger.info("check_reminders: Запуск периодической проверки напоминаний...")

        try:
            while True:
                try:
                    await asyncio.sleep(10)
                    current_time = datetime.now()

                    try:
                        user_files = os.listdir(self.reminders_dir)
                    except Exception as e:
                        logger.error(f"check_reminders: Ошибка при чтении директории напоминаний: {e}")
                        continue

                    for user_file in user_files:
                        if not user_file.endswith('_reminders.json'):
                            continue

                        user_id = int(user_file.split('_')[0])
                        reminders = await self.load_reminders(user_id)

                        for reminder in reminders[:]:
                            reminder_time = datetime.fromisoformat(reminder['time'])

                            if reminder_time <= current_time:
                                try:
                                    user = await client.fetch_user(user_id)
                                    if user:
                                        await user.send(f"> :alarm_clock: **Привет! :wave: Вы просили меня напомнить вам о:** \n {reminder['message']}")
                                        logger.info(f"check_reminders: Отправлено напоминание пользователю {user_id}: {reminder['message']}")
                                        reminders.remove(reminder)
                                except Exception as e:
                                    logger.error(f"check_reminders: Ошибка при отправке напоминания пользователю {user_id}: {e}")
                                    reminders.remove(reminder)  # Удаляем напоминание, даже если не удалось отправить

                        await self.save_reminders(user_id, reminders)
                except Exception as e:
                    logger.error(f"check_reminders: Ошибка в цикле проверки напоминаний: {e}")
                    await asyncio.sleep(30)
        finally:
            self._reminders_running = False

reminder_manager = ReminderManager()