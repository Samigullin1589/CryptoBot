# bot/services/security_service.py
# Дата обновления: 21.08.2025
# Версия: 2.0.0
# Описание: Комплексный сервис безопасности для обнаружения и предотвращения
# спама, токсичного поведения и других угроз с использованием эвристик и AI.

import asyncio
import html
import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from aiogram import Bot
from aiogram import types as tg
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.ai_content_service import AIContentService
from bot.services.image_vision_service import ImageVisionService
from bot.services.moderation_service import ModerationService
from bot.utils.dependencies import get_bot_instance, get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import Escalation, Verdict

# --- Скомпилированные регулярные выражения для эвристического анализа ---

# Обнаруживает URL-адреса, ссылки на Telegram и упоминания пользователей
URL_RE = re.compile(
    r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)[^\s()<>]+|\bt\.me/[a-zA-Z0-9_]+|@[a-zA-Z0-9_]{5,})"
)
# Обнаруживает длинные последовательности одинаковых символов (флуд)
REPEATED_CHARS_RE = re.compile(r"(.)\1{6,}")
# Обнаруживает слова, написанные преимущественно заглавными буквами (КАПС)
HEAVY_CAPS_RE = re.compile(r"\b[A-ZА-ЯЁ]{8,}\b")
# Обнаруживает ключевые слова, часто встречающиеся в спаме и скаме
SPAM_KEYWORDS_RE = re.compile(
    r"\b(joinchat|invite|airdrop|free\s+crypto|bonus|giveaway|розыгрыш|бонус|подарок|приз|ставки|казино)\b",
    re.IGNORECASE
)

class SecurityService:
    """
    Оркестрирует анализ сообщений на предмет угроз, управляет эскалацией
    нарушений и применяет меры модерации.
    """

    def __init__(
        self,
        ai_content_service: AIContentService,
        image_vision_service: ImageVisionService,
        moderation_service: ModerationService,
    ):
        self.redis: Redis = get_redis_client()
        self.bot: Bot = get_bot_instance()
        self.ai_service = ai_content_service
        self.image_vision_service = image_vision_service
        self.moderation_service = moderation_service
        self.config = settings.SECURITY
        self.keys = KeyFactory
        logger.info("Сервис SecurityService инициализирован.")

    def is_enabled(self) -> bool:
        """Проверяет, включен ли сервис в конфигурации."""
        return self.config.ENABLED

    async def is_globally_banned(self, user_id: int) -> bool:
        """Проверяет, забанен ли пользователь глобально через ModerationService."""
        return await self.moderation_service.get_ban_record(user_id) is not None

    async def analyze_message(self, message: tg.Message) -> Verdict:
        """
        Основной метод анализа сообщения. Прогоняет контент через каскад проверок:
        1. Быстрые эвристики по тексту.
        2. Проверка ссылок по белым/черным спискам.
        3. Глубокий анализ текста и изображений через AI (если необходимо).
        """
        if not self.is_enabled():
            return Verdict(ok=True, reasons=["security_disabled"])

        text = message.text or message.caption or ""
        
        # --- Уровень 1: Быстрые эвристики ---
        verdict = self._apply_text_heuristics(text)
        if not verdict.ok:
            return verdict # Немедленно блокируем, если эвристика сработала

        # --- Уровень 2: Анализ ссылок ---
        link_verdict = self._analyze_links(text)
        if not link_verdict.ok:
            return link_verdict

        # --- Уровень 3: AI-анализ (текст и/или изображение) ---
        ai_verdict = await self._apply_ai_analysis(message, text)
        if not ai_verdict.ok:
            return ai_verdict

        return Verdict(ok=True) # Если все проверки пройдены

    async def register_violation(self, user_id: int, chat_id: int, weight: int = 1) -> Escalation:
        """
        Регистрирует нарушение для пользователя в чате, увеличивает счетчик
        и возвращает решение об эскалации (предупреждение, мут, бан).
        """
        offense_key = self.keys.user_offense_count(user_id, chat_id)
        
        try:
            # Атомарно увеличиваем счетчик и устанавливаем время жизни
            pipe = self.redis.pipeline()
            pipe.incrby(offense_key, weight)
            pipe.expire(offense_key, self.config.WINDOW_SECONDS)
            new_count = (await pipe.execute())[0]
        except Exception as e:
            logger.error(f"Не удалось обновить счетчик нарушений для user_id={user_id}: {e}")
            new_count = weight

        # Принимаем решение об эскалации на основе порогов из конфига
        if new_count >= self.config.BAN_THRESHOLD:
            decision = "ban"
        elif new_count >= self.config.MUTE_THRESHOLD:
            decision = "mute"
        elif new_count >= self.config.WARN_THRESHOLD:
            decision = "warn"
        else:
            decision = "none"
            
        return Escalation(count=new_count, decision=decision, mute_seconds=self.config.MUTE_SECONDS)

    async def enforce_decision(self, message: tg.Message, verdict: Verdict):
        """Применяет наказание в соответствии с вердиктом и системой эскалации."""
        if verdict.ok or not message.from_user:
            return

        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Всегда удаляем подозрительное сообщение
        with contextlib.suppress(Exception):
            await message.delete()

        # Если чат не групповой, дальнейшие действия не применяются
        if message.chat.type == "private":
            return

        escalation = await self.register_violation(user_id, chat_id, weight=verdict.weight)
        
        if escalation.decision == "mute":
            await self.moderation_service.apply_mute_in_chat(
                chat_id, user_id, timedelta(seconds=escalation.mute_seconds)
            )
        elif escalation.decision == "ban":
            await self.moderation_service.apply_ban_in_chat(chat_id, user_id, reason="Автобан за спам")
            # Создаем глобальную запись о бане
            await self.moderation_service.create_ban_record(
                user_id=user_id, by_admin_id=self.bot.id, reason="Автобан за спам (превышен лимит нарушений)"
            )

    def _apply_text_heuristics(self, text: str) -> Verdict:
        """Применяет быстрые проверки текста на основе регулярных выражений."""
        if REPEATED_CHARS_RE.search(text):
            return Verdict(ok=False, reasons=["repeated_chars"], weight=2)
        if HEAVY_CAPS_RE.search(text) and len(text) > 20:
            return Verdict(ok=False, reasons=["heavy_caps"], weight=1)
        if SPAM_KEYWORDS_RE.search(text):
            return Verdict(ok=False, reasons=["spam_keyword"], weight=3)
        return Verdict(ok=True)

    def _analyze_links(self, text: str) -> Verdict:
        """Проверяет все найденные в тексте ссылки."""
        urls = URL_RE.findall(text)
        if not urls:
            return Verdict(ok=True)

        for url in urls:
            try:
                domain = urlparse(f"http://{url.replace('https://', '').replace('http://', '')}").hostname
                if not domain:
                    continue
                
                # Проверка по черному списку
                if any(denied in domain for denied in self.config.DENY_DOMAINS):
                    return Verdict(ok=False, reasons=[f"denied_domain:{domain}"], weight=5)
                
                # Проверка по белому списку
                if not any(allowed in domain for allowed in self.config.ALLOW_DOMAINS):
                    return Verdict(ok=False, reasons=[f"suspicious_link:{domain}"], weight=2)
            except Exception:
                continue # Игнорируем ошибки парсинга невалидных URL

        return Verdict(ok=True)

    async def _apply_ai_analysis(self, message: tg.Message, text: str) -> Verdict:
        """Делегирует анализ контента AI-сервисам, если они доступны."""
        if not self.ai_service:
            return Verdict(ok=True)

        tasks = []
        # Анализ текста, если он есть
        if text:
            tasks.append(self.ai_service.analyze_text(text))
        # Анализ изображения, если оно есть
        if message.photo or (message.document and message.document.mime_type and "image" in message.document.mime_type):
            photo_bytes = await self.image_vision_service._download_photo(message)
            if photo_bytes:
                tasks.append(self.image_vision_service.analyze(photo_bytes))
        
        if not tasks:
            return Verdict(ok=True)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_verdict = Verdict(ok=True)
        for res in results:
            if isinstance(res, Verdict) and not res.ok:
                final_verdict.ok = False
                final_verdict.reasons.extend(res.reasons)
                final_verdict.weight = max(final_verdict.weight, res.weight)
            elif isinstance(res, Exception):
                logger.error(f"Ошибка при AI-анализе контента: {res}")

        return final_verdict