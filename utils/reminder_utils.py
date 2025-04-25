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
RETRY_DELAY = 30  # delay before retry in seconds
MAX_FUTURE_DAYS = 365  # maximum days in the future for reminders

@dataclass
class Reminder:
    """Data class representing a reminder."""
    id: str
    message: str
    time: datetime

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reminder':
        """Create a Reminder instance from a dictionary."""
        return cls(
            id=data['id'],
            message=data['message'],
            time=datetime.fromisoformat(data['time'])
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Reminder instance to a dictionary."""
        return {
            'id': self.id,
            'message': self.message,
            'time': self.time.isoformat()
        }

class ReminderManager:
    """Manages reminder storage and retrieval."""
    
    def __init__(self, reminders_dir: str = 'reminders'):
        self.reminders_dir = reminders_dir
        os.makedirs(reminders_dir, exist_ok=True)

    async def get_reminders_filepath(self, user_id: int) -> str:
        """Get the filepath for a user's reminders."""
        return os.path.join(self.reminders_dir, f'{user_id}_reminders.json')

    async def load_reminders(self, user_id: int) -> List[Reminder]:
        """Load all reminders for a user."""
        filepath = await self.get_reminders_filepath(user_id)
        try:
            data = await read_json(filepath) or []
            return [Reminder.from_dict(item) for item in data]
        except Exception as e:
            logger.error(lm.get('reminder_load_error').format(user_id=user_id, error=e))
            return []

    async def save_reminders(self, user_id: int, reminders: List[Reminder]) -> bool:
        """Save reminders for a user."""
        filepath = await self.get_reminders_filepath(user_id)
        try:
            await write_json(filepath, [r.to_dict() for r in reminders])
            return True
        except Exception as e:
            logger.error(lm.get('reminder_save_error').format(user_id=user_id, error=e))
            return False

    async def add_reminder(self, user_id: int, message: str, reminder_time: datetime) -> Optional[str]:
        """Add a new reminder."""
        reminders = await self.load_reminders(user_id)
        reminder_id = str(datetime.now().timestamp())
        reminder = Reminder(id=reminder_id, message=message, time=reminder_time)
        reminders.append(reminder)
        
        if await self.save_reminders(user_id, reminders):
            return reminder_id
        return None

    async def remove_reminder(self, user_id: int, reminder_id: str) -> bool:
        """Remove a reminder by ID."""
        reminders = await self.load_reminders(user_id)
        initial_count = len(reminders)
        reminders = [r for r in reminders if r.id != reminder_id]
        
        if len(reminders) < initial_count:
            return await self.save_reminders(user_id, reminders)
        return False

    async def update_reminder_time(self, user_id: int, reminder_id: str, new_time: datetime) -> bool:
        """Update a reminder's time."""
        reminders = await self.load_reminders(user_id)
        for r in reminders:
            if r.id == reminder_id:
                r.time = new_time
                return await self.save_reminders(user_id, reminders)
        return False

class ReminderScheduler:
    """Schedules and manages reminder execution."""
    
    def __init__(self, client: Any, reminder_manager: ReminderManager):
        self.client = client
        self.reminder_manager = reminder_manager
        self.reminder_heap: List[Tuple[datetime, int, str, str]] = []
        self._new_reminder_event = asyncio.Event()
        self._heap_lock = asyncio.Lock()
        self._is_running = False

    async def load_all_reminders(self) -> None:
        """Load all reminders from storage into the scheduler."""
        try:
            user_files = os.listdir(self.reminder_manager.reminders_dir)
        except Exception as e:
            logger.error(lm.get('reminder_load_dir_error').format(error=e))
            return

        logger.info(lm.get('log_reminder_load_start'))

        for user_file in user_files:
            if not user_file.endswith('_reminders.json'):
                continue
            try:
                user_id = int(user_file.split('_')[0])
            except ValueError:
                continue
                
            reminders = await self.reminder_manager.load_reminders(user_id)
            async with self._heap_lock:
                for reminder in reminders:
                    heapq.heappush(
                        self.reminder_heap,
                        (reminder.time, user_id, reminder.id, reminder.message)
                    )
        logger.info(lm.get('reminder_load_success'))

    async def add_reminder(self, user_id: int, reminder_id: str, message: str, scheduled_time: datetime) -> None:
        """Add a new reminder to the scheduler."""
        async with self._heap_lock:
            heapq.heappush(self.reminder_heap, (scheduled_time, user_id, reminder_id, message))
            self._new_reminder_event.set()

    async def remove_reminder(self, user_id: int, reminder_id: str) -> None:
        """Remove a reminder from the scheduler."""
        async with self._heap_lock:
            self.reminder_heap = [
                item for item in self.reminder_heap
                if not (item[1] == user_id and item[2] == reminder_id)
            ]
            heapq.heapify(self.reminder_heap)

    async def scheduler_loop(self) -> None:
        """Main scheduler loop that processes reminders."""
        self._is_running = True
        while self._is_running:
            try:
                await self._process_reminders()
            except Exception as e:
                logger.error(lm.get('reminder_scheduler_error').format(error=e))
                await asyncio.sleep(1)

    async def _process_reminders(self) -> None:
        """Process due reminders and handle retries."""
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
            await self._process_single_reminder(scheduled_time, user_id, reminder_id, message)

    async def _process_single_reminder(self, scheduled_time: datetime, user_id: int, reminder_id: str, message: str) -> None:
        """Process a single reminder."""
        delay_seconds = (datetime.now() - scheduled_time).total_seconds()
        text = (lm.get('reminder_message_overdue') if delay_seconds > OVERDUE_THRESHOLD 
                else lm.get('reminder_message')).format(message=message)
        
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
        """Handle retry logic for failed reminders."""
        retry_time = datetime.now() + timedelta(seconds=RETRY_DELAY)
        updated = await self.reminder_manager.update_reminder_time(user_id, reminder_id, retry_time)
        
        if updated:
            logger.info(lm.get('reminder_retry_success').format(
                reminder_id=reminder_id, user_id=user_id, retry_time=retry_time
            ))
            await self.add_reminder(user_id, reminder_id, message, retry_time)
        else:
            logger.error(lm.get('reminder_retry_error').format(reminder_id=reminder_id, user_id=user_id))

    def stop(self) -> None:
        """Stop the scheduler."""
        self._is_running = False

# Global instances
reminder_manager = ReminderManager()
_scheduler: Optional[ReminderScheduler] = None

async def init_reminder_scheduler(client: Any) -> None:
    """Initialize the reminder scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ReminderScheduler(client, reminder_manager)
        await _scheduler.load_all_reminders()
        logger.info(lm.get('reminder_scheduler_ready'))

async def run_reminder_scheduler() -> None:
    """Run the reminder scheduler."""
    if _scheduler is None:
        raise Exception(lm.get('reminder_scheduler_not_init'))
    await _scheduler.scheduler_loop()