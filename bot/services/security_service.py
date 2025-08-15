# =================================================================================
# Файл: bot/services/security_service.py (ВЕРСИЯ "Distinguished Engineer" - АВГУСТ 2025)
# Описание: Сервис безопасности:
#   1) AI-анализ текста на угрозы (спам/фишинг/токсичность) — analyze_message()
#   2) Полноценная проверка пользователя по /check — verify_user()
# Реализован без заглушек. Соответствует DI-архитектуре и совместим с AIContentService.
# =================================================================================

from __future__ import annotations

import logging
import re
from typing import Dict, Any, Optional, TYPE_CHECKING, List

from async_lru import alru_cache

from bot.config.settings import ThreatFilterConfig
from bot.utils.models import AIVerdict

if TYPE_CHECKING:
    from bot.services.ai_content_service import AIContentService

logger = logging.getLogger(__name__)


class SecurityService:
    """
    Сервис для анализа текста и проверки пользователей с использованием AI.
    Делегирует вызовы AI специализированному AIContentService и добавляет
    поверх простые, прозрачные эвристики.
    """

    # --- базовые списки/паттерны эвристик ---
    _SUSPICIOUS_SUBSTRINGS = {
        # типичные маркеры «продаж»/скама/фишинга/арбитража
        "airdrop", "giveaway", "bonus", "earn", "profit", "x100",
        "investment", "broker", "whatsapp", "binance-support",
        "trustwallet", "metamask", "support", "recovery", "private-sale",
        "pump", "dump", "signals", "crypto-signals", "change_number",
        "bet", "casino", "1win", "gg.bet", "p2p-help",
    }
    _RE_NUMERIC_TAIL = re.compile(r"(\d{4,})$")          # 4+ цифры в конце ника
    _RE_REPEAT_CHARS = re.compile(r"(.)\1{3,}")          # 4+ подряд одинаковых символа
    _RE_UNSAFE_PREFIX = re.compile(r"^(btc|eth|binance|okx|bybit|ton|telegram|support)[\W_]*", re.I)
    _RE_ALLOWED_USERNAME = re.compile(r"^[A-Za-z0-9_]{5,32}$")  # правила Telegram

    def __init__(self, ai_service: "AIContentService", config: ThreatFilterConfig):
        """
        :param ai_service: Сервис для взаимодействия с AI-моделями.
        :param config: Конфигурация для фильтра угроз (минимум .enabled: bool).
        """
        self.ai_service = ai_service
        self.config = config
        logger.info(
            "SecurityService инициализирован. Защита %s.",
            "включена" if self.config.enabled else "выключена",
        )

    # ==========================
    # 1) AI-анализ СООБЩЕНИЯ
    # ==========================

    def _get_system_prompt_for_text(self) -> str:
        """Системный промпт для AI-анализатора ТЕКСТА."""
        return (
            "You are a security analysis bot for a Telegram chat about cryptocurrency. "
            "Analyze the following message. Respond with ONLY a valid JSON object. "
            "Do not add any other text or markdown formatting. Your task is to classify "
            "the message's intent and assess its potential threat level."
        )

    def _get_response_schema_for_text(self) -> Dict[str, Any]:
        """JSON-схема для ответа AI по анализу ТЕКСТА."""
        return {
            "type": "OBJECT",
            "properties": {
                "intent": {
                    "type": "STRING",
                    "enum": [
                        "advertisement", "scam", "phishing",
                        "insult", "question", "discussion", "other"
                    ],
                    "description": "Основное намерение сообщения."
                },
                "toxicity_score": {
                    "type": "NUMBER",
                    "description": "Оценка токсичности от 0.0 (нейтрально) до 1.0 (очень токсично)."
                },
                "is_potential_scam": {
                    "type": "BOOLEAN",
                    "description": "True, если сообщение похоже на мошенничество."
                },
                "is_potential_phishing": {
                    "type": "BOOLEAN",
                    "description": "True, если сообщение содержит признаки фишинга."
                }
            },
            "required": ["intent", "toxicity_score", "is_potential_scam", "is_potential_phishing"]
        }

    @alru_cache(maxsize=1024, ttl=300)
    async def analyze_message(self, text: str) -> AIVerdict:
        """
        Анализирует текст сообщения для выявления угроз.
        Возвращает валидную Pydantic-модель AIVerdict даже при ошибках AI.
        """
        default_verdict = AIVerdict()

        if not self.config.enabled or not text or not text.strip():
            return default_verdict

        user_prompt = f"Проанализируй следующее сообщение: '{text}'"
        try:
            verdict_dict = await self.ai_service.get_structured_response(
                system_prompt=self._get_system_prompt_for_text(),
                user_prompt=user_prompt,
                response_schema=self._get_response_schema_for_text(),
            )
            if not verdict_dict:
                logger.warning("AI-анализ текста вернул пустой результат: '%s...'", text[:50])
                return default_verdict

            logger.info("AI Security Verdict for '%s...': %s", text[:30], verdict_dict)
            return AIVerdict(**verdict_dict)

        except Exception as e:
            logger.error("Ошибка AI при анализе текста: %s", e, exc_info=True)
            return default_verdict

    # ==========================
    # 2) Проверка ПОЛЬЗОВАТЕЛЯ (/check)
    # ==========================

    def _get_system_prompt_for_user(self) -> str:
        """Системный промпт для AI-проверки пользователя."""
        return (
            "You are a Telegram account risk assessor for a crypto community. "
            "You must return ONLY a JSON object. No explanations.\n"
            "Evaluate the risk that a Telegram account is a scam/spam/phishing actor. "
            "Consider handle patterns (impersonation, numeric tails, 'support', 'recovery'), "
            "common bait words (airdrop, giveaway, investment, signals, pump/dump), "
            "and impersonation of exchanges/wallets. If you cannot assess, keep risk low but non-zero.\n"
            "Return fields exactly as in the provided schema."
        )

    def _get_response_schema_for_user(self) -> Dict[str, Any]:
        """JSON-схема для ответа AI по проверке ПОЛЬЗОВАТЕЛЯ."""
        return {
            "type": "OBJECT",
            "properties": {
                "is_scam": {
                    "type": "BOOLEAN",
                    "description": "True, если высока вероятность, что аккаунт мошеннический."
                },
                "risk_score": {
                    "type": "INTEGER",
                    "description": "Оценка риска 0..100 (0 — безопасно, 100 — крайне опасно)."
                },
                "reason": {
                    "type": "STRING",
                    "description": "Краткое объяснение."
                },
                "labels": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Список меток (например, 'impersonation', 'numeric_tail')."
                }
            },
            "required": ["is_scam", "risk_score"]
        }

    @staticmethod
    def _normalize_username(username: Optional[str]) -> Optional[str]:
        if not username:
            return None
        u = username.strip()
        if not u:
            return None
        if u.startswith("@"):
            u = u[1:]
        return u

    def _heuristics_for_user(self, username: Optional[str], user_id: Optional[int]) -> Dict[str, Any]:
        """
        Прозрачные эвристики без AI. Возвращает словарь с:
          - trust_score (0..100, 100 = полностью доверяем)
          - labels: List[str]
          - notes: List[str] (для reason)
        """
        labels: List[str] = []
        notes: List[str] = []

        # базовый старт доверия
        trust = 85

        # username-правила
        if username:
            uname = username.lower()

            # валидность по правилам Telegram
            if not self._RE_ALLOWED_USERNAME.match(username):
                labels.append("invalid_format")
                notes.append("Несоответствие правилам Telegram (допускаются A-Z/a-z/0-9/_)")
                trust -= 10

            # подозрительные подстроки
            for token in self._SUSPICIOUS_SUBSTRINGS:
                if token in uname:
                    labels.append(f"token:{token}")
                    trust -= 20
                    break  # одного флага достаточно

            # 4+ цифр в конце
            if self._RE_NUMERIC_TAIL.search(uname):
                labels.append("numeric_tail")
                trust -= 10

            # повторяющиеся символы
            if self._RE_REPEAT_CHARS.search(uname):
                labels.append("repeated_chars")
                trust -= 5

            # выдаёт себя за «поддержку»/биржу/кошелёк
            if self._RE_UNSAFE_PREFIX.search(uname):
                labels.append("impersonation_prefix")
                trust -= 20

            # слишком короткие/длинные ники (хотя Telegram не должен допускать)
            if len(uname) < 5:
                labels.append("too_short")
                trust -= 10
            if len(uname) > 32:
                labels.append("too_long")
                trust -= 10

        # user_id-правила (мягкие)
        if user_id is not None:
            try:
                if user_id > 10_000_000_000:
                    labels.append("suspicious_id_range")
                    trust -= 10
            except Exception:
                pass

        # нормализация
        trust = max(0, min(100, trust))
        if not labels:
            notes.append("Явных красных флагов не найдено по эвристикам")

        return {"trust_score": trust, "labels": labels, "notes": notes}

    @alru_cache(maxsize=4096, ttl=600)
    async def verify_user(
        self,
        username: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Полная проверка пользователя. Совмещает эвристики и AI.
        Возвращает dict:
          {
            "ok": bool,              # безопасен ли (true/false)
            "score": int,            # 0..100, чем выше — тем безопаснее
            "reason": str,           # краткие детали
            "labels": [str, ...]     # набор меток
          }
        """
        # нормализация входа
        username = self._normalize_username(username)

        # если передали только строку с цифрами в username — трактуем как user_id
        if username and username.isdigit() and user_id is None:
            try:
                user_id = int(username)
                username = None
            except ValueError:
                pass

        # эвристики
        heur = self._heuristics_for_user(username, user_id)
        heur_trust = heur["trust_score"]
        labels: List[str] = list(heur["labels"])
        reasons: List[str] = list(heur["notes"])

        # AI-компонент (если защита включена)
        ai_trust: Optional[int] = None
        if self.config.enabled:
            try:
                # собираем единый user_prompt
                who = f"username=@{username}" if username else ""
                if user_id is not None:
                    who = (who + (" " if who else "")) + f"user_id={user_id}"

                user_prompt = (
                    "Assess the following Telegram account:\n"
                    f"{who}\n"
                    "Return ONLY JSON per the schema."
                )

                ai_dict = await self.ai_service.get_structured_response(
                    system_prompt=self._get_system_prompt_for_user(),
                    user_prompt=user_prompt,
                    response_schema=self._get_response_schema_for_user(),
                )

                if ai_dict:
                    # risk_score: 0..100 (0 — безопасно), конвертируем в trust
                    risk = int(max(0, min(100, int(ai_dict.get("risk_score", 0)))))
                    ai_trust = 100 - risk

                    # переносим метки/причину из AI
                    ai_labels = ai_dict.get("labels") or []
                    if isinstance(ai_labels, list):
                        labels.extend(str(x) for x in ai_labels if x)

                    ai_reason = ai_dict.get("reason")
                    if ai_reason:
                        reasons.append(str(ai_reason))

            except Exception as e:
                logger.error("Ошибка AI при проверке пользователя: %s", e, exc_info=True)

        # объединение оценок
        if ai_trust is not None:
            # простая усредняющая модель: 60% эвристики + 40% AI
            combined_trust = round(0.6 * heur_trust + 0.4 * ai_trust)
        else:
            combined_trust = heur_trust

        combined_trust = max(0, min(100, combined_trust))
        ok = combined_trust >= 50

        # финальная причина
        reason = "; ".join(r for r in reasons if r).strip()
        labels = sorted(set(labels)) or None

        result = {
            "ok": ok,
            "score": combined_trust,
            "reason": reason or ("Совпадений по простым правилам не найдено" if ok else "Имеются косвенные признаки риска"),
            "labels": labels,
        }

        logger.info(
            "Verify user result: username=@%s user_id=%s -> %s",
            username or "", user_id, result
        )
        return result