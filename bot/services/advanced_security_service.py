# bot/services/advanced_security_service.py
# Дата обновления: 19.08.2025
# Версия: 2.0.0
# Описание: Модульный сервис для проактивной защиты от спама и нежелательного контента.

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from aiogram.types import Message
from loguru import logger
from redis.asyncio import Redis

from bot.config.settings import settings
from bot.services.antispam_learning import AntiSpamLearning
from bot.services.image_vision_service import ImageVisionService
from bot.utils.dependencies import get_bot_instance, get_redis_client
from bot.utils.keys import KeyFactory
from bot.utils.models import SecurityVerdict

# Скомпилированные регулярные выражения для производительности
URL_RE = re.compile(r"https?://[^\s/$.?#].[^\s]*", re.IGNORECASE)
INVITE_RE = re.compile(r"(t\.me/joinchat/|t\.me/\+|discord\.gg/|wa\.me/)", re.IGNORECASE)


class AdvancedSecurityService:
    """
    Эвристический и самообучающийся движок для борьбы со спамом.
    Анализирует сообщения по нескольким критериям, выставляет оценку угрозы
    и выносит вердикт о необходимом действии.
    """

    def __init__(self, learning_service: AntiSpamLearning, vision_service: Optional[ImageVisionService] = None):
        """
        Инициализирует сервис безопасности.

        :param learning_service: Сервис для работы с базой знаний о спаме.
        :param vision_service: Опциональный сервис для анализа изображений.
        """
        self.redis: Redis = get_redis_client()
        self.learning = learning_service
        self.vision = vision_service
        self.keys = KeyFactory
        self.config = settings.THREAT_FILTER
        logger.info("Сервис AdvancedSecurityService инициализирован.")

    async def _extract_domains(self, text: str) -> List[str]:
        """Извлекает все доменные имена из текста сообщения."""
        if not text:
            return []
        
        hosts: set[str] = set()
        for match in URL_RE.finditer(text):
            try:
                host = urlparse(match.group(0)).hostname
                if host and host.lower() not in self.config.SAFE_DOMAINS:
                    hosts.add(host.lower())
            except Exception:
                # Игнорируем некорректные URL
                continue
        return list(hosts)

    def _inspect_text_heuristics(self, text: str) -> Tuple[int, List[str]]:
        """Проверяет текст на основе эвристик: стоп-слова, инвайт-ссылки, длина."""
        score = 0
        reasons = []
        text_lower = (text or "").lower()

        if any(word in text_lower for word in self.config.SUSPICIOUS_WORDS):
            score += self.config.HEURISTIC_WORD_SCORE
            reasons.append("suspicious_words")
        
        if INVITE_RE.search(text_lower):
            score += self.config.HEURISTIC_INVITE_SCORE
            reasons.append("invite_link")
            
        if len(text) > self.config.MAX_TEXT_LENGTH:
            score += self.config.HEURISTIC_LENGTH_SCORE
            reasons.append("long_text")
            
        return score, reasons

    async def _inspect_domains(self, domains: List[str]) -> Tuple[int, List[str]]:
        """Проверяет домены по черному списку и подозрительным TLD."""
        score = 0
        reasons = []
        for host in domains:
            if await self.learning.is_bad_domain(host):
                score += self.config.BAD_DOMAIN_SCORE
                reasons.append(f"bad_domain:{host}")
                break  # Одного плохого домена достаточно
        
        if not reasons and any(host.endswith(tuple(self.config.SUSPICIOUS_TLDS)) for host in domains):
            score += self.config.SUSPICIOUS_TLD_SCORE
            reasons.append("suspicious_tld")
            
        return score, reasons

    async def _inspect_learned_phrases(self, text: str) -> Tuple[int, List[str]]:
        """Проверяет текст по базе знаний спам-фраз."""
        best_ratio, best_phrase = await self.learning.score_text(text, min_ratio=85)
        if best_ratio and best_phrase:
            score = min(40, best_ratio // 3)
            return score, [f"learned_phrase:'{best_phrase.phrase}'"]
        return 0, []

    async def _inspect_image(self, message: Message) -> Tuple[int, List[str]]:
        """Анализирует изображение в сообщении, если доступен сервис Vision."""
        if not self.vision or not message.photo:
            return 0, []
        
        try:
            largest_photo = max(message.photo, key=lambda p: (p.width or 0) * (p.height or 0))
            bot = get_bot_instance()
            file_info = await bot.get_file(largest_photo.file_id)
            
            if file_info.file_path:
                image_bytes = await bot.download_file(file_info.file_path)
                if image_bytes:
                    is_spam, details = await self.vision.analyze(image_bytes.read())
                    if is_spam:
                        reason = details.get("explanation", "Image marked as advertising/spam")
                        return self.config.IMAGE_SPAM_SCORE, [f"image_spam:{reason}"]
        except Exception as e:
            logger.error(f"Ошибка при анализе изображения: {e}")
        
        return 0, []

    async def _calculate_final_verdict(self, score: int, chat_id: int, user_id: int) -> Tuple[Optional[str], str]:
        """Определяет финальное действие на основе очков и количества страйков."""
        action: Optional[str] = None
        reason = ""

        if score >= self.config.SCORE_BAN:
            action, reason = "ban", "Очень высокий уровень угрозы"
        elif score >= self.config.SCORE_MUTE:
            action, reason = "mute", "Высокий уровень угрозы"
        elif score >= self.config.SCORE_WARN:
            action, reason = "warn", "Средний уровень угрозы"
        elif score >= self.config.SCORE_DELETE:
            action, reason = "delete", "Низкий уровень угрозы"

        if action in ("delete", "warn", "mute"):
            key = self.keys.user_strikes(chat_id, user_id)
            try:
                strikes = await self.redis.incr(key)
                await self.redis.expire(key, self.config.REPEAT_WINDOW_SECONDS)
                
                if strikes >= self.config.STRIKES_FOR_AUTOBAN:
                    action, reason = "ban", f"Автобан после {strikes} нарушений"
            except Exception as e:
                logger.error(f"Ошибка при обновлении страйков для user {user_id} в чате {chat_id}: {e}")
        
        return action, reason

    async def inspect_message(self, message: Message) -> SecurityVerdict:
        """
        Проводит комплексную проверку сообщения и выносит вердикт.
        """
        user = message.from_user
        if not user:
            return SecurityVerdict()

        text = (message.text or message.caption or "").strip()
        total_score = 0
        all_reasons: List[str] = []
        
        # Шаг 1: Эвристика текста
        score, reasons = self._inspect_text_heuristics(text)
        total_score += score
        all_reasons.extend(reasons)

        # Шаг 2: Анализ доменов
        domains = await self._extract_domains(text)
        score, reasons = await self._inspect_domains(domains)
        total_score += score
        all_reasons.extend(reasons)

        # Шаг 3: Анализ по базе знаний
        score, reasons = await self._inspect_learned_phrases(text)
        total_score += score
        all_reasons.extend(reasons)

        # Шаг 4: Анализ изображений
        score, reasons = await self._inspect_image(message)
        total_score += score
        all_reasons.extend(reasons)
        
        # Шаг 5: Вынесение финального вердикта
        action, reason = await self._calculate_final_verdict(total_score, message.chat.id, user.id)

        verdict = SecurityVerdict(
            score=total_score,
            action=action,
            reason=reason,
            details=all_reasons,
            domains=domains
        )
        
        if verdict.action:
            logger.warning(f"Обнаружена угроза от user_id={user.id}: {verdict}")

        return verdict