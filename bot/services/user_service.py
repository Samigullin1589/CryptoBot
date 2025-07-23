# ===============================================================
# Файл: bot/services/user_service.py (БЕЗ ИЗМЕНЕНИЙ)
# Описание: Этот файл уже написан правильно.
# ===============================================================
import time
import json
import logging
from dataclasses import dataclass, asdict, fields
from typing import Optional, List, Dict

import redis.asyncio as redis
from aiogram import Bot
from aiogram.enums import ChatMemberStatus

logger = logging.getLogger(__name__)

@dataclass
class UserProfile:
    user_id: int
    chat_id: int
    join_timestamp: float
    trust_score: int = 100
    is_banned: bool = False
    mute_until_timestamp: float = 0
    violations_count: int = 0
    electricity_cost: Optional[float] = None
    last_activity_timestamp: float = 0.0
    message_count: int = 0
    conversation_history_json: str = "[]"
    is_admin: bool = False
    has_immunity: bool = False

class UserService:
    ACTIVITY_REWARD_THRESHOLD: int = 50
    ACTIVITY_REWARD_POINTS: int = 5

    def __init__(self, redis_client: redis.Redis, bot: Bot, admin_user_ids: list[int]):
        self.redis = redis_client
        self.bot = bot
        self.global_admins = set(admin_user_ids)

    def _get_user_profile_key(self, user_id: int, chat_id: int) -> str:
        return f"user_profile:{chat_id}:{user_id}"

    async def get_or_create_user(self, user_id: int, chat_id: int) -> UserProfile:
        profile_key = self._get_user_profile_key(user_id, chat_id)
        saved_profile_data = await self.redis.hgetall(profile_key)

        profile_dict = {
            "user_id": user_id,
            "chat_id": chat_id,
            "join_timestamp": time.time()
        }

        if saved_profile_data:
            decoded_data = {k.decode('utf-8'): v.decode('utf-8') for k, v in saved_profile_data.items()}
            
            for field in fields(UserProfile):
                if field.name in decoded_data:
                    raw_value = decoded_data[field.name]
                    try:
                        if field.type is bool:
                            profile_dict[field.name] = raw_value.lower() == 'true'
                        elif raw_value != 'None':
                            profile_dict[field.name] = field.type(raw_value)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert field '{field.name}' with value '{raw_value}' to type {field.type}")
        
        user_profile = UserProfile(**profile_dict)
        
        if not saved_profile_data:
            await self._save_user_profile(user_profile)

        try:
            chat_member = await self.bot.get_chat_member(chat_id, user_id)
            if chat_member.status in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR]:
                user_profile.is_admin = True
        except Exception:
            user_profile.is_admin = False

        if user_id in self.global_admins:
            user_profile.has_immunity = True
            user_profile.is_admin = True

        return user_profile

    async def _save_user_profile(self, profile: UserProfile):
        profile_key = self._get_user_profile_key(profile.user_id, profile.chat_id)
        profile_dict = {k: str(v) for k, v in asdict(profile).items() if k not in ['is_admin', 'has_immunity']}
        await self.redis.hset(profile_key, mapping=profile_dict)

    async def log_violation(self, user_id: int, chat_id: int, reason: str, penalty: int = 10, details: Optional[dict] = None):
        user_profile = await self.get_or_create_user(user_id, chat_id)
        user_profile.trust_score = max(0, user_profile.trust_score - penalty)
        user_profile.violations_count += 1
        await self._save_user_profile(user_profile)
        logger.warning(f"VIOLATION: User {user_id} in chat {chat_id}. Reason: {reason}. New score: {user_profile.trust_score}. Details: {details}")

    async def update_user_status(self, user_id: int, chat_id: int, is_banned: bool):
        user_profile = await self.get_or_create_user(user_id, chat_id)
        user_profile.is_banned = is_banned
        if is_banned:
            user_profile.trust_score = 0
        await self._save_user_profile(user_profile)

    async def update_user_mute(self, user_id: int, chat_id: int, mute_until: float):
        user_profile = await self.get_or_create_user(user_id, chat_id)
        user_profile.mute_until_timestamp = mute_until
        await self._save_user_profile(user_profile)

    async def update_user_activity(self, user_id: int, chat_id: int):
        profile = await self.get_or_create_user(user_id, chat_id)
        profile.last_activity_timestamp = time.time()
        profile.message_count += 1
        if profile.message_count >= self.ACTIVITY_REWARD_THRESHOLD:
            profile.trust_score += self.ACTIVITY_REWARD_POINTS
            profile.message_count = 0
            logger.info(f"Пользователь {user_id} награжден за активность в чате {chat_id}. Новый рейтинг: {profile.trust_score}")
        await self._save_user_profile(profile)

    async def get_conversation_history(self, user_id: int, chat_id: int) -> List[Dict[str, str]]:
        profile = await self.get_or_create_user(user_id, chat_id)
        try:
            return json.loads(profile.conversation_history_json)
        except json.JSONDecodeError:
            logger.error(f"Не удалось декодировать историю диалога для пользователя {user_id}")
            return []

    async def add_to_conversation_history(self, user_id: int, chat_id: int, user_text: str, model_text: str, max_history_len: int = 10):
        history = await self.get_conversation_history(user_id, chat_id)
        
        history.append({"role": "user", "parts": [{"text": user_text}]})
        history.append({"role": "model", "parts": [{"text": model_text}]})
        
        if len(history) > max_history_len * 2:
            history = history[-max_history_len * 2:]
            
        profile = await self.get_or_create_user(user_id, chat_id)
        profile.conversation_history_json = json.dumps(history, ensure_ascii=False)
        await self._save_user_profile(profile)

    async def get_user_electricity_cost(self, user_id: int, chat_id: int, default_cost: float) -> float:
        user_profile = await self.get_or_create_user(user_id, chat_id)
        return user_profile.electricity_cost if user_profile.electricity_cost is not None else default_cost

    async def set_user_electricity_cost(self, user_id: int, chat_id: int, cost: float):
        user_profile = await self.get_or_create_user(user_id, chat_id)
        user_profile.electricity_cost = cost
        await self._save_user_profile(user_profile)
