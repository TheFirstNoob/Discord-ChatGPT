import os
import json
import asyncio
from datetime import datetime, timedelta
from src.log import logger

class BanManager:
    def __init__(self, bans_dir='bans'):
        self.bans_dir = bans_dir
        os.makedirs(bans_dir, exist_ok=True)
        self.admin_id = int(os.getenv('ADMIN_ID', 0))

    async def ban_user(self, admin_id, user_id, reason="Нарушение правил", duration=None):
        """
        Забанить пользователя
        
        :param admin_id: ID администратора
        :param user_id: ID пользователя для бана
        :param reason: Причина бана
        :param duration: Длительность бана (None - перманентный)
        :return: Результат операции
        """
        # Проверка прав администратора
        if admin_id != self.admin_id:
            return False, "У вас нет прав для бана"

        # Путь к файлу бана
        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')

        # Подготовка данных о бане
        ban_data = {
            'user_id': user_id,
            'banned_by': admin_id,
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'duration': duration  # None означает перманентный бан
        }

        # Сохраняем информацию о бане
        async with aiofiles.open(ban_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(ban_data, ensure_ascii=False, indent=4))

        logger.warning(f"Пользователь {user_id} забанен администратором {admin_id}. Причина: {reason}")
        return True, "Пользователь успешно забанен"

    async def unban_user(self, admin_id, user_id):
        """
        Разбанить пользователя
        """
        if admin_id != self.admin_id:
            return False, "У вас нет прав для разбана"

        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')
        
        if os.path.exists(ban_file):
            os.remove(ban_file)
            logger.info(f"Пользователь {user_id} разбанен администратором {admin_id}")
            return True, "Пользователь успешно разбанен"
        
        return False, "Пользователь не был забанен"

    async def is_user_banned(self, user_id):
        """
        Проверка бана пользователя
        
        :return: Формат (забанен, причина_бана)
        """
        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')
        
        if not os.path.exists(ban_file):
            return False, None

        async with aiofiles.open(ban_file, 'r', encoding='utf-8') as f:
            ban_data = json.loads(await f.read())

        # Проверка на перманентный бан
        if ban_data['duration'] is None:
            return True, ban_data['reason']

        # Проверка временного бана
        ban_time = datetime.fromisoformat(ban_data['timestamp'])
        duration = timedelta(**ban_data['duration']) if ban_data['duration'] else None

        if duration and datetime.now() > ban_time + duration:
            # Бан истек, удаляем файл
            os.remove(ban_file)
            return False, None

        return True, ban_data['reason']

    async def get_banned_users(self, admin_id):
        """
        Получить список забаненных пользователей
        """
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