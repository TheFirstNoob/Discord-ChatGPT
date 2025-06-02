import os
import asyncio
import heapq
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from utils.files_utils import read_json, write_json
from src.log import logger
from src.locale_manager import locale_manager as lm

# Constants
OVERDUE_THRESHOLD = 180  # 3 minutes critical time when we consider a reminder overdue
RETRY_DELAY = 30         # delay before retry in seconds
MAX_FUTURE_DAYS = 365    # maximum days in the future for reminders

@dataclass
class Reminder:
    id: str
    message: str
    time: datetime
    utc_offset_minutes: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reminder':
        return cls(
            id=data['id'],
            message=data['message'],
            time=datetime.fromisoformat(data['time']),
            utc_offset_minutes=data.get('utc_offset_minutes')
        )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'id': self.id,
            'message': self.message,
            'time': self.time.isoformat()
        }
        if self.utc_offset_minutes is not None:
            data['utc_offset_minutes'] = self.utc_offset_minutes
        return data

class ReminderManager:
    """Manages reminder storage, retrieval, and per-user default timezone offset."""
    
    def __init__(self, reminders_dir: str = 'reminders'):
        self.reminders_dir = reminders_dir
        os.makedirs(reminders_dir, exist_ok=True)

    async def _get_user_filepath(self, user_id: int) -> str:
        return os.path.join(self.reminders_dir, f'{user_id}_reminders.json')

    async def _load_user_file(self, user_id: int) -> Dict[str, Any]:
        path = await self._get_user_filepath(user_id)
        data = await read_json(path) or {}
        return {
            'last_offset': data.get('last_offset'),
            'reminders': data.get('reminders', [])
        }

    async def _save_user_file(self, user_id: int, data: Dict[str, Any]) -> bool:
        path = await self._get_user_filepath(user_id)
        try:
            await write_json(path, data)
            return True
        except Exception as e:
            logger.error(lm.get('reminder_save_error').format(user_id=user_id, error=e))
            return False

    async def load_reminders(self, user_id: int) -> List[Reminder]:
        user_data = await self._load_user_file(user_id)
        return [Reminder.from_dict(item) for item in user_data['reminders']]

    async def save_reminders(self, user_id: int, reminders: List[Reminder]) -> bool:
        user_data = await self._load_user_file(user_id)
        user_data['reminders'] = [r.to_dict() for r in reminders]
        return await self._save_user_file(user_id, user_data)

    async def add_reminder(self, user_id: int, message: str, reminder_time: datetime, utc_offset_minutes: Optional[int] = None) -> Optional[str]:
        reminders = await self.load_reminders(user_id)
        reminder_id = str(datetime.now().timestamp())
        reminders.append(Reminder(id=reminder_id, message=message, time=reminder_time, utc_offset_minutes=utc_offset_minutes))
        return reminder_id if await self.save_reminders(user_id, reminders) else None

    async def remove_reminder(self, user_id: int, reminder_id: str) -> bool:
        reminders = await self.load_reminders(user_id)
        filtered = [r for r in reminders if r.id != reminder_id]
        return await self.save_reminders(user_id, filtered) if len(filtered) < len(reminders) else False

    async def update_reminder_time(self, user_id: int, reminder_id: str, new_time: datetime) -> bool:
        reminders = await self.load_reminders(user_id)
        for r in reminders:
            if r.id == reminder_id:
                r.time = new_time
                return await self.save_reminders(user_id, reminders)
        return False

    async def get_last_offset(self, user_id: int) -> Optional[int]:
        data = await self._load_user_file(user_id)
        return data.get('last_offset')

    async def set_last_offset(self, user_id: int, offset_minutes: int) -> bool:
        data = await self._load_user_file(user_id)
        data['last_offset'] = offset_minutes
        return await self._save_user_file(user_id, data)

class ReminderScheduler:
    """Schedules and manages reminder execution."""
    
    def __init__(self, client: Any, reminder_manager: ReminderManager):
        self.client = client
        self.reminder_manager = reminder_manager
        self.reminder_heap: List[Tuple[datetime, int, str, str]] = []
        self._new_reminder_event = asyncio.Event()
        self._heap_lock = asyncio.Lock()
        self._is_running = True

    async def load_all_reminders(self) -> None:
        try:
            user_files = os.listdir(self.reminder_manager.reminders_dir)
        except Exception as e:
            logger.error(lm.get('reminder_load_dir_error').format(error=e))
            return

        logger.info(lm.get('log_reminder_load_start'))
        for user_file in (f for f in user_files if f.endswith('_reminders.json')):
            user_id = int(user_file.split('_')[0])
            reminders = await self.reminder_manager.load_reminders(user_id)
            async with self._heap_lock:
                for reminder in reminders:
                    heapq.heappush(self.reminder_heap, (reminder.time, user_id, reminder.id, reminder.message))
        logger.info(lm.get('reminder_load_success'))

    async def add_reminder(self, user_id: int, reminder_id: str, message: str, scheduled_time: datetime) -> None:
        async with self._heap_lock:
            heapq.heappush(self.reminder_heap, (scheduled_time, user_id, reminder_id, message))
            self._new_reminder_event.set()

    async def remove_reminder(self, user_id: int, reminder_id: str) -> None:
        async with self._heap_lock:
            self.reminder_heap = [item for item in self.reminder_heap if not (item[1] == user_id and item[2] == reminder_id)]
            heapq.heapify(self.reminder_heap)

    async def scheduler_loop(self) -> None:
        while self._is_running:
            try:
                await self._process_reminders()
            except Exception as e:
                logger.error(lm.get('reminder_scheduler_error').format(error=e))
                await asyncio.sleep(1)

    async def _process_reminders(self) -> None:
        async with self._heap_lock:
            wait_time = None if not self.reminder_heap else max(0, (self.reminder_heap[0][0] - datetime.now()).total_seconds())

        await self._new_reminder_event.wait() if wait_time is None else asyncio.wait_for(self._new_reminder_event.wait(), timeout=wait_time)
        self._new_reminder_event.clear()

        now = datetime.now()
        due = []
        async with self._heap_lock:
            while self.reminder_heap and self.reminder_heap[0][0] <= now:
                due.append(heapq.heappop(self.reminder_heap))

        for scheduled_time, user_id, reminder_id, message in due:
            await self._process_single_reminder(scheduled_time, user_id, reminder_id, message)

    async def _process_single_reminder(self, scheduled_time: datetime, user_id: int, reminder_id: str, message: str) -> None:
        delay_seconds = (datetime.now() - scheduled_time).total_seconds()
        reminders = await self.reminder_manager.load_reminders(user_id)
        reminder = next((r for r in reminders if r.id == reminder_id), None)

        local_time = scheduled_time + timedelta(minutes=reminder.utc_offset_minutes) if reminder and reminder.utc_offset_minutes is not None else scheduled_time
        text = (lm.get('reminder_message_overdue') if delay_seconds > OVERDUE_THRESHOLD else lm.get('reminder_message')).format(message=message)

        if reminder and reminder.utc_offset_minutes is not None:
            text += f"\n(Local time: {local_time.strftime('%d.%m.%Y %H:%M')})"

        try:
            user = await self.client.fetch_user(user_id)
            if user:
                await user.send(text)
                logger.info(lm.get('reminder_send_success').format(reminder_id=reminder_id, user_id=user_id))
            await self.reminder_manager.remove_reminder(user_id, reminder_id)
        except Exception as e:
            logger.error(lm.get('reminder_send_error').format(reminder_id=reminder_id, user_id=user_id, error=e))
            await self._handle_reminder_retry(user_id, reminder_id, message)

    async def _handle_reminder_retry(self, user_id: int, reminder_id: str, message: str) -> None:
        retry_time = datetime.now() + timedelta(seconds=RETRY_DELAY)
        if await self.reminder_manager.update_reminder_time(user_id, reminder_id, retry_time):
            logger.info(lm.get('reminder_retry_success').format(reminder_id=reminder_id, user_id=user_id, retry_time=retry_time))
            await self.add_reminder(user_id, reminder_id, message, retry_time)
        else:
            logger.error(lm.get('reminder_retry_error').format(reminder_id=reminder_id, user_id=user_id))

    def stop(self) -> None:
        self._is_running = False

# Global instances
reminder_manager = ReminderManager()
_scheduler: Optional[ReminderScheduler] = None

async def init_reminder_scheduler(client: Any) -> None:
    global _scheduler
    if _scheduler is None:
        _scheduler = ReminderScheduler(client, reminder_manager)
        await _scheduler.load_all_reminders()
        logger.info(lm.get('reminder_scheduler_ready'))

async def run_reminder_scheduler() -> None:
    if _scheduler is None:
        raise Exception(lm.get('reminder_scheduler_not_init'))
    await _scheduler.scheduler_loop()