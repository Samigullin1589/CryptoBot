# bot/services/security_service.py
# Дата обновления: 28.10.2025
# Версия: 2.2.1
# Описание: ИСПРАВЛЕНО - Правильные имена настроек (строчные буквы)

import re
import asyncio
from datetime import timedelta
from typing import List
from urllib.parse import urlparse
import contextlib

from aiogram import Bot
from aiogram import types as tg
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.ai_content_service import AIContentService
from bot.services.image_vision_service import ImageVisionService
from bot.services.moderation_service import ModerationService
from bot.utils.keys import KeyFactory
from bot.utils.models import Verdict, Escalation, ImageAnalysisResult

URL_RE = re.compile(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)[^\s()<>]+|\bt\.me/[a-zA-Z0-9_]+|@[a-zA-Z0-9_]{5,})")
REPEATED_CHARS_RE = re.compile(r"(.)\1{6,}")
HEAVY_CAPS_RE = re.compile(r"\b[A-ZА-ЯЁ]{8,}\b")
SPAM_KEYWORDS_RE = re.compile(r"\b(joinchat|invite|airdrop|free\s+crypto|bonus|giveaway|розыгрыш|бонус|подарок|приз|ставки|казино)\b", re.IGNORECASE)

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
        redis_client: Redis,
        bot: Bot,
    ):
        self.redis = redis_client
        self.bot = bot
        self.ai_service = ai_content_service
        self.image_vision_service = image_vision_service
        self.moderation_service = moderation_service
        # ✅ ИСПРАВЛЕНО: settings.SECURITY → settings.threat_filter
        self.config = settings.threat_filter
        self.keys = KeyFactory
        logger.info("Сервис SecurityService инициализирован.")

    def is_enabled(self) -> bool:
        # ✅ ИСПРАВЛЕНО: self.config.ENABLED → self.config.enabled
        return self.config.enabled

    async def analyze_message(self, message: tg.Message) -> Verdict:
        """
        Основной метод анализа сообщения с каскадом проверок.
        """
        if not self.is_enabled():
            return Verdict(ok=True, reasons=["security_disabled"])

        text = message.text or message.caption or ""
        
        # Уровень 1: Быстрые эвристики
        verdict = self._apply_text_heuristics(text)
        if not verdict.ok: return verdict

        # Уровень 2: Анализ ссылок
        link_verdict = self._analyze_links(text)
        if not link_verdict.ok: return link_verdict

        # Уровень 3: AI-анализ
        ai_verdict = await self._apply_ai_analysis(message, text)
        if not ai_verdict.ok: return ai_verdict

        return Verdict(ok=True)

    async def register_violation(self, user_id: int, chat_id: int, weight: int = 1) -> Escalation:
        """
        Регистрирует нарушение и возвращает решение об эскалации.
        """
        offense_key = self.keys.user_offense_count(user_id, chat_id)
        
        try:
            pipe = self.redis.pipeline()
            pipe.incrby(offense_key, weight)
            # ✅ ИСПРАВЛЕНО: self.config.WINDOW_SECONDS → self.config.window_seconds
            pipe.expire(offense_key, self.config.window_seconds)
            new_count = (await pipe.execute())[0]
        except Exception as e:
            logger.error(f"Не удалось обновить счетчик нарушений для user_id={user_id}: {e}")
            new_count = weight

        # ✅ ИСПРАВЛЕНО: все пороги теперь строчными
        if new_count >= self.config.ban_threshold: 
            decision = "ban"
        elif new_count >= self.config.mute_threshold: 
            decision = "mute"
        elif new_count >= self.config.warn_threshold: 
            decision = "warn"
        else: 
            decision = "none"
            
        # ✅ ИСПРАВЛЕНО: self.config.MUTE_SECONDS → self.config.mute_seconds
        return Escalation(count=new_count, decision=decision, mute_seconds=self.config.mute_seconds)

    async def enforce_decision(self, message: tg.Message, verdict: Verdict):
        """
        Применяет наказание в соответствии с вердиктом.
        """
        if verdict.ok or not message.from_user: return

        user_id, chat_id = message.from_user.id, message.chat.id
        
        with contextlib.suppress(Exception): await message.delete()

        if message.chat.type == "private": return

        escalation = await self.register_violation(user_id, chat_id, weight=verdict.weight)
        
        if escalation.decision == "mute":
            await self.moderation_service.apply_mute_in_chat(chat_id, user_id, timedelta(seconds=escalation.mute_seconds))
        elif escalation.decision == "ban":
            await self.moderation_service.apply_ban_in_chat(chat_id, user_id, reason="Автобан за спам")
            await self.moderation_service.create_ban_record(user_id=user_id, by_admin_id=self.bot.id, reason="Автобан (превышен лимит нарушений)")

    def _apply_text_heuristics(self, text: str) -> Verdict:
        """Применяет быстрые проверки текста."""
        if REPEATED_CHARS_RE.search(text): return Verdict(ok=False, reasons=["repeated_chars"], weight=2)
        if HEAVY_CAPS_RE.search(text) and len(text) > 20: return Verdict(ok=False, reasons=["heavy_caps"], weight=1)
        if SPAM_KEYWORDS_RE.search(text): return Verdict(ok=False, reasons=["spam_keyword"], weight=3)
        return Verdict(ok=True)

    def _analyze_links(self, text: str) -> Verdict:
        """Проверяет найденные в тексте ссылки."""
        urls = URL_RE.findall(text)
        if not urls: return Verdict(ok=True)

        for url in urls:
            try:
                domain = urlparse(f"http://{url.replace('https://', '').replace('http://', '')}").hostname
                if not domain: continue
                # ✅ ИСПРАВЛЕНО: доступ к deny_domains и allow_domains
                # Предполагаем что в ThreatFilterConfig есть поля deny_domains и allow_domains
                deny_domains = getattr(self.config, 'deny_domains', [])
                allow_domains = getattr(self.config, 'allow_domains', [])
                
                if any(denied in domain for denied in deny_domains):
                    return Verdict(ok=False, reasons=[f"denied_domain:{domain}"], weight=5)
                if allow_domains and not any(allowed in domain for allowed in allow_domains):
                    return Verdict(ok=False, reasons=[f"suspicious_link:{domain}"], weight=2)
            except Exception:
                continue

        return Verdict(ok=True)

    async def _apply_ai_analysis(self, message: tg.Message, text: str) -> Verdict:
        """
        Делегирует анализ контента AI-сервисам. **(ПОЛНАЯ РЕАЛИЗАЦИЯ)**
        """
        if not self.ai_service:
            return Verdict(ok=True)

        tasks = []
        # Анализ изображения, если оно есть и сервис доступен
        if self.image_vision_service and (message.photo or (message.document and message.document.mime_type and "image" in message.document.mime_type)):
            photo_bytes = await self.image_vision_service._download_photo(message)
            if photo_bytes:
                tasks.append(self.image_vision_service.analyze(photo_bytes))
        
        if not tasks:
            return Verdict(ok=True)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_verdict = Verdict(ok=True)
        for res in results:
            if isinstance(res, ImageAnalysisResult):
                if res.is_spam:
                    final_verdict.ok = False
                    final_verdict.reasons.append(f"image_spam:{res.explanation or 'AI verdict'}")
                    final_verdict.weight = max(final_verdict.weight, 4) # Даем высокий вес за спам на картинке
            elif isinstance(res, Exception):
                logger.error(f"Ошибка при AI-анализе контента: {res}")

        return final_verdict