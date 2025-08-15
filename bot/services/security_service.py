\================================
Файл: bot/services/security\_service.py
ВЕРСИЯ: "Distinguished Engineer" - АВГУСТ 2025 (Азия/Тбилиси)
Кратко: Убран не-Python заголовок, добавлена совместимость с обеими сигнатурами AIContentService.get\_structured\_response (новая: system\_prompt/user\_prompt/response\_schema и старая: prompt/json\_schema). Исправлены вызовы и усилено логирование.

from **future** import annotations

import logging
import re
from typing import Dict, Any, Optional, TYPE\_CHECKING, List

from async\_lru import alru\_cache

from bot.config.settings import ThreatFilterConfig
from bot.utils.models import AIVerdict

if TYPE\_CHECKING:
from bot.services.ai\_content\_service import AIContentService

logger = logging.getLogger(**name**)

class SecurityService:
"""
Сервис для анализа текста и проверки пользователей с использованием AI.
Делегирует вызовы AI специализированному AIContentService и добавляет
поверх простые, прозрачные эвристики.
"""

```
# базовые списки/паттерны эвристик
_SUSPICIOUS_SUBSTRINGS = {
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
# Внутренние промпты/схемы
# ==========================

def _get_system_prompt_for_text(self) -> str:
    return (
        "You are a security analysis bot for a Telegram chat about cryptocurrency. "
        "Analyze the following message. Respond with ONLY a valid JSON object. "
        "Do not add any other text or markdown formatting. Your task is to classify "
        "the message's intent and assess its potential threat level."
    )

def _get_response_schema_for_text(self) -> Dict[str, Any]:
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

def _get_system_prompt_for_user(self) -> str:
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

async def _call_structured(
    self,
    system_prompt: str,
    user_prompt: str,
    schema: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Унифицированный вызов AIContentService.get_structured_response с поддержкой
    двух сигнатур:
      - новая: (system_prompt=..., user_prompt=..., response_schema=...)
      - старая: (prompt=..., json_schema=...)
    """
    try:
        # попытка новой сигнатуры
        return await self.ai_service.get_structured_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=schema,
        )
    except TypeError as e:
        logger.info("Fallback to legacy get_structured_response signature: %s", e)
        try:
            # fallback к старой сигнатуре
            merged_prompt = f"{system_prompt}\n\n{user_prompt}"
            return await self.ai_service.get_structured_response(
                prompt=merged_prompt,
                json_schema=schema,
            )
        except Exception as e2:
            logger.error("Legacy get_structured_response failed: %s", e2, exc_info=True)
            return None
    except Exception as e:
        logger.error("get_structured_response failed: %s", e, exc_info=True)
        return None

# ==========================
# 1) AI-анализ СООБЩЕНИЯ
# ==========================

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
        verdict_dict = await self._call_structured(
            system_prompt=self._get_system_prompt_for_text(),
            user_prompt=user_prompt,
            schema=self._get_response_schema_for_text(),
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

    trust = 85

    if username:
        uname = username.lower()

        if not self._RE_ALLOWED_USERNAME.match(username):
            labels.append("invalid_format")
            notes.append("Несоответствие правилам Telegram (допускаются A-Z/a-z/0-9/_)")
            trust -= 10

        for token in self._SUSPICIOUS_SUBSTRINGS:
            if token in uname:
                labels.append(f"token:{token}")
                trust -= 20
                break

        if self._RE_NUMERIC_TAIL.search(uname):
            labels.append("numeric_tail")
            trust -= 10

        if self._RE_REPEAT_CHARS.search(uname):
            labels.append("repeated_chars")
            trust -= 5

        if self._RE_UNSAFE_PREFIX.search(uname):
            labels.append("impersonation_prefix")
            trust -= 20

        if len(uname) < 5:
            labels.append("too_short")
            trust -= 10
        if len(uname) > 32:
            labels.append("too_long")
            trust -= 10

    if user_id is not None:
        try:
            if user_id > 10_000_000_000:
                labels.append("suspicious_id_range")
                trust -= 10
        except Exception:
            pass

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
        "ok": bool,
        "score": int,        # 0..100, чем выше — тем безопаснее
        "reason": str,
        "labels": [str, ...]
      }
    """
    username = self._normalize_username(username)

    if username and username.isdigit() and user_id is None:
        try:
            user_id = int(username)
            username = None
        except ValueError:
            pass

    heur = self._heuristics_for_user(username, user_id)
    heur_trust = heur["trust_score"]
    labels: List[str] = list(heur["labels"])
    reasons: List[str] = list(heur["notes"])

    ai_trust: Optional[int] = None
    if self.config.enabled:
        try:
            who = f"username=@{username}" if username else ""
            if user_id is not None:
                who = (who + (" " if who else "")) + f"user_id={user_id}"

            user_prompt = (
                "Assess the following Telegram account:\n"
                f"{who}\n"
                "Return ONLY JSON per the schema."
            )

            ai_dict = await self._call_structured(
                system_prompt=self._get_system_prompt_for_user(),
                user_prompt=user_prompt,
                schema=self._get_response_schema_for_user(),
            )

            if ai_dict:
                risk = int(max(0, min(100, int(ai_dict.get("risk_score", 0)))))
                ai_trust = 100 - risk

                ai_labels = ai_dict.get("labels") or []
                if isinstance(ai_labels, list):
                    labels.extend(str(x) for x in ai_labels if x)

                ai_reason = ai_dict.get("reason")
                if ai_reason:
                    reasons.append(str(ai_reason))

        except Exception as e:
            logger.error("Ошибка AI при проверке пользователя: %s", e, exc_info=True)

    combined_trust = heur_trust if ai_trust is None else round(0.6 * heur_trust + 0.4 * ai_trust)
    combined_trust = max(0, min(100, combined_trust))
    ok = combined_trust >= 50

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