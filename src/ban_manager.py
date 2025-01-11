import os
import json
import asyncio
import aiofiles
from datetime import datetime, timedelta
from src.log import logger

class BanManager:
    def __init__(self, bans_dir='bans'):
        self.bans_dir = bans_dir
        os.makedirs(bans_dir, exist_ok=True)
        self.admin_id = int(os.getenv('ADMIN_ID', 0))

    async def ban_user(self, user_id, reason="Нарушение правил", duration=None):
        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')

        ban_data = {
            'user_id': user_id,
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'duration': duration
        }

        async with aiofiles.open(ban_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(ban_data, ensure_ascii=False, indent=4))

    async def unban_user(self, user_id):
        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')
        
        if os.path.exists(ban_file):
            os.remove(ban_file)
            return True
        
        return False

    async def is_user_banned(self, user_id):
        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')
        
        if not os.path.exists(ban_file):
            return False, None

        async with aiofiles.open(ban_file, 'r', encoding='utf-8') as f:
            ban_data = json.loads(await f.read())

        if ban_data['duration'] is None:
            return True, ban_data['reason']

        ban_time = datetime.fromisoformat(ban_data['timestamp'])
        duration = timedelta(**ban_data['duration']) if ban_data['duration'] else None

        if duration and datetime.now() > ban_time + duration:
            os.remove(ban_file)
            return False, None

        return True, ban_data['reason']

    async def get_banned_users(self, admin_id):
        if admin_id != self.admin_id:
            return []

        banned_users = []
        for filename in os.listdir(self.bans_dir):
            if filename.endswith('_ban.json'):
                user_id = int(filename.split('_')[0])
                is_banned, reason = await self.is_user_banned(user_id)
                if is_banned:
                    banned_users.append({
                        'user_id': user_id,
                        'reason': reason
                    })
        
        return banned_users

ban_manager = BanManager()