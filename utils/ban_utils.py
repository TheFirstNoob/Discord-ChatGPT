import os
import asyncio
from datetime import datetime, timedelta
from utils.files_utils import read_json, write_json
from src.log import logger

class BanManager:
    def __init__(self, bans_dir='bans'):
        self.bans_dir = bans_dir
        os.makedirs(bans_dir, exist_ok=True)
        self.admin_id = int(os.getenv('ADMIN_ID', 0))
        self.cleanup_task = None

    async def check_bans(self):
        if hasattr(self, '_ban_cleanup_running') and self._ban_cleanup_running:
            return

        self._ban_cleanup_running = True
        logger.info("BanManager: Запуск периодической проверки банов...")

        try:
            while True:
                try:
                    await self.cleanup_expired_bans()
                    logger.info("BanManager: Проверка истекших банов завершена.")
                except Exception as e:
                    logger.error(f"BanManager: Ошибка при проверке истекших банов: {e}")
                await asyncio.sleep(3600)  # 1 час
        finally:
            self._ban_cleanup_running = False

    async def ban_user(self, user_id, reason="Нарушение правил", days=None):
        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')

        ban_data = {
            'user_id': user_id,
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'duration': {'days': days} if days else None
        }

        try:
            await write_json(ban_file, ban_data)
            logger.info(f"ban_user: Пользователь {user_id} забанен. Причина: {reason}")
        except Exception as e:
            logger.error(f"ban_user: Ошибка при записи файла бана для пользователя {user_id}: {e}")
            raise

    async def unban_user(self, user_id):
        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')
        
        if os.path.exists(ban_file):
            try:
                os.remove(ban_file)
                logger.info(f"unban_user: Пользователь {user_id} разбанен.")
                return True
            except Exception as e:
                logger.error(f"unban_user: Ошибка при удалении файла бана для пользователя {user_id}: {e}")
                raise
        
        return False

    async def is_ban_expired(self, ban_data):
        if ban_data['duration'] is None:
            return False

        ban_time = datetime.fromisoformat(ban_data['timestamp'])
        duration = timedelta(**ban_data['duration'])
        return datetime.now() > ban_time + duration

    async def get_ban_message(self, ban_data):
        reason = ban_data['reason']
        if ban_data['duration'] is None:
            unban_text = "Перманентный бан"
        else:
            ban_time = datetime.fromisoformat(ban_data['timestamp'])
            duration = timedelta(**ban_data['duration'])
            unban_date = (ban_time + duration).strftime('%Y-%m-%d %H:%M:%S')
            unban_text = f"Дата разблокировки: {unban_date}"

        return f":x: Вам заблокирован доступ к использованию этим ботом!\n**Причина**: {reason}\n{unban_text}"

    async def is_user_banned(self, user_id):
        ban_file = os.path.join(self.bans_dir, f'{user_id}_ban.json')
        
        if not os.path.exists(ban_file):
            return False, None

        try:
            ban_data = await read_json(ban_file)
        except Exception as e:
            logger.error(f"is_user_banned: Ошибка при чтении файла бана для пользователя {user_id}: {e}")
            return False, None

        if await self.is_ban_expired(ban_data):
            os.remove(ban_file)
            return False, None

        ban_message = await self.get_ban_message(ban_data)
        return True, ban_message

    async def check_ban_and_respond(self, interaction):
        try:
            is_banned, ban_message = await self.is_user_banned(interaction.user.id)
            if is_banned:
                await interaction.response.send_message(ban_message, ephemeral=True)
                return True
            return False
        except Exception as e:
            logger.error(f"check_ban_and_respond: Ошибка при проверке бана пользователя {interaction.user.id}: {e}")
            await interaction.response.send_message("> :x: **ОШИБКА:** Не удалось проверить ваш статус бана. Пожалуйста, попробуйте позже.", ephemeral=True)
            return True

    async def get_banned_users(self, admin_id):
        if admin_id != self.admin_id:
            return []

        banned_users = []
        for filename in os.listdir(self.bans_dir):
            if filename.endswith('_ban.json'):
                user_id = int(filename.split('_')[0])
                ban_file = os.path.join(self.bans_dir, filename)

                try:
                    ban_data = await read_json(ban_file)
                except Exception as e:
                    logger.error(f"get_banned_users: Ошибка при чтении файла бана для пользователя {user_id}: {e}")
                    continue

                if await self.is_ban_expired(ban_data):
                    os.remove(ban_file)
                    continue

                banned_users.append({
                    'user_id': user_id,
                    'reason': ban_data['reason']
                })
        
        return banned_users

    async def cleanup_expired_bans(self):
        for filename in os.listdir(self.bans_dir):
            if filename.endswith('_ban.json'):
                user_id = int(filename.split('_')[0])
                await self.is_user_banned(user_id)

ban_manager = BanManager()