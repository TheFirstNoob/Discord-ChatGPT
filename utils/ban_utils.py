import os
import discord
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from utils.files_utils import read_json, write_json
from src.log import logger
from src.locale_manager import locale_manager as lm

@dataclass
class BanData:
    """Data class representing a user's ban information."""
    user_id: int
    reason: str
    timestamp: datetime
    duration: Optional[Dict[str, int]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BanData':
        """Create a BanData instance from a dictionary."""
        return cls(
            user_id=data['user_id'],
            reason=data['reason'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            duration=data.get('duration')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert BanData instance to a dictionary."""
        return {
            'user_id': self.user_id,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration
        }

    def is_expired(self) -> bool:
        """Check if the ban has expired."""
        if self.duration is None:
            return False
        return datetime.now() > self.timestamp + timedelta(**self.duration)

    def get_unban_date(self) -> Optional[datetime]:
        """Get the date when the ban will expire."""
        if self.duration is None:
            return None
        return self.timestamp + timedelta(**self.duration)

class BanManager:
    """Manages user bans and ban-related operations."""

    def __init__(self, bans_dir: str = 'bans'):
        self.bans_dir = bans_dir
        os.makedirs(bans_dir, exist_ok=True)
        self.admin_id = int(os.getenv('ADMIN_ID', 0))
        self._ban_cleanup_running = False

    async def get_ban_filepath(self, user_id: int) -> str:
        """Get the filepath for a user's ban data."""
        return os.path.join(self.bans_dir, f'{user_id}_ban.json')

    async def check_bans(self) -> None:
        """Check and cleanup expired bans."""
        if self._ban_cleanup_running:
            return

        self._ban_cleanup_running = True
        logger.info(lm.get('ban_manager_start'))

        try:
            await self.cleanup_expired_bans()
            logger.info(lm.get('ban_manager_complete'))
        except Exception as e:
            logger.error(lm.get('ban_manager_error').format(error=e))
        finally:
            self._ban_cleanup_running = False

    async def ban_user(self, user_id: int, reason: str = lm.get('ban_default_reason'), days: Optional[int] = None) -> None:
        """Ban a user with optional duration."""
        ban_file = await self.get_ban_filepath(user_id)
        ban_data = BanData(
            user_id=user_id,
            reason=reason,
            timestamp=datetime.now(),
            duration={'days': days} if days else None
        )

        try:
            await write_json(ban_file, ban_data.to_dict())
            logger.info(lm.get('ban_user_success').format(user_id=user_id, reason=reason))
        except Exception as e:
            logger.error(lm.get('ban_user_error').format(user_id=user_id, error=e))
            raise

    async def unban_user(self, user_id: int) -> bool:
        """Remove a user's ban."""
        ban_file = await self.get_ban_filepath(user_id)
        
        if os.path.exists(ban_file):
            try:
                os.remove(ban_file)
                logger.info(lm.get('unban_user_success').format(user_id=user_id))
                return True
            except Exception as e:
                logger.error(lm.get('unban_user_error').format(user_id=user_id, error=e))
                raise
        
        return False

    async def get_ban_message(self, ban_data: BanData, target_user_id: int, is_self_check: bool) -> Dict[str, Any]:
        """Generate ban message embed data."""
        ban_time = ban_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        unban_date = ban_data.get_unban_date()
        
        if unban_date is None:
            unban_text = lm.get('ban_embed_permanent')
        else:
            unban_text = lm.get('ban_embed_unban_date').format(date=unban_date.strftime('%Y-%m-%d %H:%M:%S'))

        title = (lm.get('ban_embed_title_self') if is_self_check 
                else lm.get('ban_embed_title_other').format(user_id=target_user_id))
        description = (lm.get('ban_embed_description_self') if is_self_check 
                      else lm.get('ban_embed_description_other').format(user_id=target_user_id))

        return {
            "title": title,
            "description": description,
            "fields": [
                {"name": lm.get('ban_embed_field_reason'), "value": ban_data.reason, "inline": False},
                {"name": lm.get('ban_embed_field_ban_date'), "value": ban_time, "inline": True},
                {"name": lm.get('ban_embed_field_ban_duration'), "value": unban_text, "inline": True}
            ],
            "color": 0xff0000
        }

    async def is_user_banned(self, user_id: int, is_self_check: bool = True) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if a user is banned and get ban information."""
        ban_file = await self.get_ban_filepath(user_id)
        
        if not os.path.exists(ban_file):
            return False, None

        try:
            data = await read_json(ban_file)
            ban_data = BanData.from_dict(data)
        except Exception as e:
            logger.error(lm.get('is_user_banned_error').format(user_id=user_id, error=e))
            return False, None

        if ban_data.is_expired():
            await self.unban_user(user_id)
            return False, None

        return True, await self.get_ban_message(ban_data, user_id, is_self_check)

    async def check_ban_and_respond(self, interaction: discord.Interaction) -> bool:
        """Check if a user is banned and respond with ban message if they are."""
        try:
            is_banned, ban_data = await self.is_user_banned(interaction.user.id, is_self_check=True)
            if is_banned:
                embed = discord.Embed(
                    title=ban_data["title"],
                    description=ban_data["description"],
                    color=ban_data["color"]
                )

                for field in ban_data["fields"]:
                    embed.add_field(
                        name=field["name"],
                        value=field["value"],
                        inline=field.get("inline", False)
                    )

                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                return True
            return False
        except Exception as e:
            logger.error(lm.get('log_ban_check_error').format(user_id=interaction.user.id, error=e))
            error_message = lm.get('ban_check_error')
            if interaction.response.is_done():
                await interaction.followup.send(error_message, ephemeral=True)
            else:
                await interaction.response.send_message(error_message, ephemeral=True)
            return True

    async def get_banned_users(self, admin_id: int) -> List[Dict[str, Any]]:
        """Get list of currently banned users (admin only)."""
        if admin_id != self.admin_id:
            return []

        banned_users = []
        for filename in os.listdir(self.bans_dir):
            if not filename.endswith('_ban.json'):
                continue

            try:
                user_id = int(filename.split('_')[0])
                ban_file = await self.get_ban_filepath(user_id)
                data = await read_json(ban_file)
                ban_data = BanData.from_dict(data)

                if ban_data.is_expired():
                    await self.unban_user(user_id)
                    continue

                banned_users.append({
                    'user_id': user_id,
                    'reason': ban_data.reason
                })
            except Exception as e:
                logger.error(lm.get('get_banned_users_error').format(user_id=user_id, error=e))
                continue
        
        return banned_users

    async def cleanup_expired_bans(self) -> None:
        """Clean up all expired bans."""
        for filename in os.listdir(self.bans_dir):
            if not filename.endswith('_ban.json'):
                continue

            try:
                user_id = int(filename.split('_')[0])
                await self.is_user_banned(user_id)
            except Exception as e:
                logger.error(lm.get('cleanup_expired_bans_error').format(user_id=user_id, error=e))
                continue

# Global instance
ban_manager = BanManager()