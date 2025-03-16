import os
import asyncio
import heapq
from datetime import datetime, timedelta
from typing import List, Dict
from utils.files_utils import read_json, write_json
from src.log import logger

OVERDUE_THRESHOLD = 180  # 3 минуты критическое время когда считаем что напоминание просрочено
RETRY_DELAY = 30  # задержка перед повторной попыткой в секундах

class ReminderManager:
    def __init__(self, reminders_dir='reminders'):
        self.reminders_dir = reminders_dir
        os.makedirs(reminders_dir, exist_ok=True)

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

    async def add_reminder(self, user_id: int, message: str, reminder_time: datetime) -> str:
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

    async def update_reminder_time(self, user_id: int, reminder_id: str, new_time: datetime) -> bool:
        reminders = await self.load_reminders(user_id)
        updated = False
        for r in reminders:
            if r['id'] == reminder_id:
                r['time'] = new_time.isoformat()
                updated = True
                break
        if updated:
            await self.save_reminders(user_id, reminders)
            return True
        return False

class ReminderScheduler:
    def __init__(self, client, run_reminder_scheduler: ReminderManager):
        self.client = client
        self.run_reminder_scheduler = run_reminder_scheduler
        self.reminder_heap = []  # (scheduled_time, user_id, reminder_id, message)
        self._new_reminder_event = asyncio.Event()
        self._heap_lock = asyncio.Lock()

    async def load_all_reminders(self):
        try:
            user_files = os.listdir(self.run_reminder_scheduler.reminders_dir)
        except Exception as e:
            logger.error(f"load_all_reminders: Ошибка при чтении директории: {e}")
            return

        for user_file in user_files:
            if not user_file.endswith('_reminders.json'):
                continue
            try:
                user_id = int(user_file.split('_')[0])
            except ValueError:
                continue
            reminders = await self.run_reminder_scheduler.load_reminders(user_id)
            async with self._heap_lock:
                for reminder in reminders:
                    scheduled_time = datetime.fromisoformat(reminder['time'])
                    heapq.heappush(self.reminder_heap, (scheduled_time, user_id, reminder['id'], reminder['message']))
        logger.info("load_all_reminders: Все напоминания загружены в очередь.")

    async def add_reminder(self, user_id: int, reminder_id: str, message: str, scheduled_time: datetime):
        async with self._heap_lock:
            heapq.heappush(self.reminder_heap, (scheduled_time, user_id, reminder_id, message))
            self._new_reminder_event.set()

    async def scheduler_loop(self):
        while True:
            async with self._heap_lock:
                if not self.reminder_heap:
                    wait_time = None
                else:
                    next_time, _, _, _ = self.reminder_heap[0]
                    now = datetime.now()
                    delay = (next_time - now).total_seconds()
                    wait_time = delay if delay > 0 else 0

            try:
                if wait_time is None:
                    await self._new_reminder_event.wait()
                else:
                    try:
                        await asyncio.wait_for(self._new_reminder_event.wait(), timeout=wait_time)
                    except asyncio.TimeoutError:
                        pass
            finally:
                self._new_reminder_event.clear()

            now = datetime.now()
            due_reminders = []
            async with self._heap_lock:
                while self.reminder_heap and self.reminder_heap[0][0] <= now:
                    due_reminders.append(heapq.heappop(self.reminder_heap))

            for scheduled_time, user_id, reminder_id, message in due_reminders:
                delay_seconds = (now - scheduled_time).total_seconds()
                if delay_seconds > OVERDUE_THRESHOLD:
                    text = f" :persevere: **Извините! К сожалению из-за технических проблем, я не смогла вам напомнить во время о:** \n{message}"
                else:
                    text = f"> :alarm_clock: **Привет! Вы просили меня напомнить вам о:** \n{message}"
                try:
                    user = await self.client.fetch_user(user_id)
                    if user:
                        await user.send(text)
                        logger.info(f"scheduler_loop: Напоминание {reminder_id} отправлено пользователю {user_id}")
                    await self.run_reminder_scheduler.remove_reminder(user_id, reminder_id)
                except Exception as e:
                    logger.error(f"scheduler_loop: Ошибка отправки напоминания {reminder_id} для пользователя {user_id}: {e}")
                    retry_time = datetime.now() + timedelta(seconds=RETRY_DELAY)
                    updated = await self.run_reminder_scheduler.update_reminder_time(user_id, reminder_id, retry_time)
                    if updated:
                        logger.info(f"scheduler_loop: Напоминание {reminder_id} для пользователя {user_id} переназначено на {retry_time}")
                        await self.add_reminder(user_id, reminder_id, message, retry_time)
                    else:
                        logger.error(f"scheduler_loop: Не удалось обновить время напоминания {reminder_id} для пользователя {user_id}")

reminder_manager = ReminderManager()
_scheduler = None

async def init_reminder_scheduler(client):
    global _scheduler
    if _scheduler is None:
        logger.info("Инициализация планировщика...")
        _scheduler = ReminderScheduler(client, reminder_manager)
        await _scheduler.load_all_reminders()
        logger.info("Планировщик напоминаний инициализирован.")

async def run_reminder_scheduler():
    if _scheduler is None:
        raise Exception("Scheduler не инициализирован. Перед запуском вызовите init_reminder_scheduler(client).")
    await _scheduler.scheduler_loop()