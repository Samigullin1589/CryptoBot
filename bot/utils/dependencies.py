# bot/utils/dependencies.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional

from redis.asyncio import Redis

from bot.config.settings import Settings
from bot.utils.keys import KeyFactory


@dataclass
class Deps:
    """
    Легковесный контейнер зависимостей для хэндлеров.
    Все сервисы передаются как опциональные, чтобы избежать жесткой связанности.
    """
    settings: Settings
    redis: Redis
    keys: type[KeyFactory]
    admin_service: Optional[Any] = None
    user_service: Optional[Any] = None
    price_service: Optional[Any] = None
    asic_service: Optional[Any] = None
    news_service: Optional[Any] = None
    market_data_service: Optional[Any] = None
    crypto_center_service: Optional[Any] = None
    mining_game_service: Optional[Any] = None
    verification_service: Optional[Any] = None
    mining_service: Optional[Any] = None
    security_service: Optional[Any] = None
    moderation_service: Optional[Any] = None
    coin_list_service: Optional[Any] = None
    achievement_service: Optional[Any] = None
    quiz_service: Optional[Any] = None
    ai_content_service: Optional[Any] = None
    event_service: Optional[Any] = None
    market_service: Optional[Any] = None
    parser_service: Optional[Any] = None
    coin_alias_service: Optional[Any] = None
    anti_spam_service: Optional[Any] = None
    stop_word_service: Optional[Any] = None
    image_guard_service: Optional[Any] = None
    image_vision_service: Optional[Any] = None
    advanced_security_service: Optional[Any] = None
    antispam_learning_service: Optional[Any] = None