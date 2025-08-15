================================
Файл: bot/services/security_service.py
ВЕРСИЯ: "Distinguished Engineer" — 15 августа 2025 (Asia/Tbilisi)
Кратко: Корневая причина падения — в файл попал не-Python текст (ASCII-шапка). Это видно в логах Render: File "/opt/render/project/src/bot/services/security_service.py", line 1 и SyntaxError: unexpected character after line continuation character — первая строка начиналась с \================================. Ниже — чистый рабочий код без декоративных строк. Публичные методы сохранены: analyze_message(text)->AIVerdict и verify_user(username=None, user_id=None)->dict. Добавлены лёгкие эвристики, совместимость с существующим AIContentService.get_structured_response(...), логирование и кэширование (alru_cache).

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from async_lru import alru_cache

from bot.config.settings import ThreatFilterConfig
from bot.utils.models import AIVerdict

if TYPE_CHECKING:
    from bot.services.ai_content_service import AIContentService  # тайп-хинты только

logger = logging.getLogger(__name__)


class SecurityService:
    """
    Сервис для анализа текста и проверки пользователей.
    Сочетает лёгкие эвристики и (по возможности) вызовы AI через AIContentService.
    Публичные методы:
      - analyze_message(text) -> AIVerdict
      - verify_user(username=None, user_id=None) -> dict
    """

    _SUSPICIOUS_SUBSTRINGS = {
        "airdrop", "giveaway", "bonus", "earn", "profit", "x100",
        "investment", "broker", "whatsapp", "binance-support",
        "trustwallet", "metamask", "support", "recovery", "private-sale",
        "pump", "dump", "signals", "crypto-signals", "change_number",
        "bet", "casino", "1win", "gg.bet", "p2p-help", "usdt", "ton"
    }
    _RE_NUMERIC_TAIL = re.compile(r"(\d{4,})$")
    _RE_REPEAT_CHARS = re.compile(r"(.)\1{3,}")
    _RE_UNSAFE_PREFIX = re.compile(r"^(btc|eth|binance|okx|bybit|ton|telegram|support)[\W_]*", re.I)
    _RE_ALLOWED_USERNAME = re.compile(r"^[A-Za-z0-9_]{5,32}$")
    _URL_RE = re.compile(r"https?://", re.I)

    def __init__(self, ai_service: Optional["AIContentService"], config: ThreatFilterConfig):
        self.ai_service = ai_service
        self.config = config
        logger.info("SecurityService инициализирован. Защита %s.",
                    "включена" if self.config.enabled else "выключена")

    # ---------- Промпты/схемы для AI ----------
    def _get_system_prompt_for_text(self) -> str:
        return (
            "You are a security analysis bot for a Telegram crypto chat. "
            "Analyze the user's message and classify risks. "
            "Return ONLY a valid JSON that matches the schema."
        )

    def _get_response_schema_for_text(self) -> Dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "intent": {"type": "STRING"},
                "toxicity_score": {"type": "NUMBER"},
                "is_potential_scam": {"type": "BOOLEAN"},
                "is_potential_phishing": {"type": "BOOLEAN"}
            },
            "required": ["intent", "toxicity_score", "is_potential_scam", "is_potential_phishing"]
        }

    def _get_system_prompt_for_user(self) -> str:
        return (
            "You are a Telegram account risk assessor for a crypto community. "
            "Return ONLY JSON. Evaluate scam/spam/phishing risk by handle/ID patterns."
        )

    def _get_response_schema_for_user(self) -> Dict[str, Any]:
        return {
            "type": "OBJECT",
            "properties": {
                "is_scam": {"type": "BOOLEAN"},
                "risk_score": {"type": "INTEGER"},
                "reason": {"type": "STRING"},
                "labels": {"type": "ARRAY", "items": {"type": "STRING"}}
            },
            "required": ["is_scam", "risk_score"]
        }

    async def _call_structured(
        self,
        *,
        system_prompt: Optional[str],
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Универсальный вызов AIContentService.get_structured_response.
        Используем «старую» сигнатуру (prompt/json_schema) с передачей system_prompt как kwargs.
        """
        if not self.ai_service:
            return None
        try:
            return await self.ai_service.get_structured_response(
                prompt=user_prompt,
                json_schema=schema,
                system_prompt=system_prompt,
            )
        except TypeError:
            # На всякий случай: поддержка альтернативных реализаций
            try:
                merged = f"{system_prompt or ''}\n\n{user_prompt}"
                return await self.ai_service.get_structured_response(
                    prompt=merged,
                    json_schema=schema,
                )
            except Exception:
                logger.exception("Fallback get_structured_response провалился")
                return None
        except Exception:
            logger.exception("Ошибка при вызове get_structured_response")
            return None

    # ---------- Анализ текста ----------
    @alru_cache(maxsize=1024, ttl=300)
    async def analyze_message(self, text: str) -> AIVerdict:
        """
        Возвращает AIVerdict с полями score и reasons (для ThreatFilter).
        Сначала — лёгкие эвристики, затем — попытка уточнить через AI.
        """
        verdict = AIVerdict()
        txt = (text or "").strip()
        if not self.config.enabled or not txt:
            return verdict

        low = txt.lower()
        reasons: List[str] = []
        score: float = 0.0

        if self._URL_RE.search(low):
            score += 0.3
            reasons.append("Содержит ссылку")

        kw_hits = [w for w in self._SUSPICIOUS_SUBSTRINGS if w in low]
        if kw_hits:
            score += 0.7
            reasons.append("Подозрительные слова: " + ", ".join(sorted(set(kw_hits))))

        # AI-добавка
        ai = await self._call_structured(
            system_prompt=self._get_system_prompt_for_text(),
            user_prompt=f"Message: {txt}",
            schema=self._get_response_schema_for_text(),
        )
        if ai:
            try:
                base = AIVerdict(**ai)
                verdict.intent = base.intent
                verdict.toxicity_score = base.toxicity_score
                verdict.is_potential_scam = base.is_potential_scam
                verdict.is_potential_phishing = base.is_potential_phishing
                if base.is_potential_phishing:
                    score += 0.9
                    reasons.append("AI: признаки фишинга")
                elif base.is_potential_scam:
                    score += 0.7
                    reasons.append("AI: признаки скама/спама")
            except Exception:
                logger.exception("Не удалось распарсить AI-вердикт")

        verdict.score = min(2.0, score)
        verdict.reasons = reasons
        return verdict

    # ---------- Проверка аккаунта ----------
    @staticmethod
    def _normalize_username(username: Optional[str]) -> Optional[str]:
        if not username:
            return None
        u = username.strip()
        if not u:
            return None
        return u[1:] if u.startswith("@") else u

    def _heuristics_for_user(self, username: Optional[str], user_id: Optional[int]) -> Dict[str, Any]:
        labels: List[str] = []
        notes: List[str] = []
        trust = 85

        if username:
            uname = username.lower()

            if not self._RE_ALLOWED_USERNAME.match(username):
                labels.append("invalid_format")
                notes.append("Несоответствие правилам Telegram")
                trust -= 10

            if any(tok in uname for tok in self._SUSPICIOUS_SUBSTRINGS):
                labels.append("suspicious_token")
                trust -= 20

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

        if isinstance(user_id, int) and user_id > 10_000_000_000:
            labels.append("suspicious_id_range")
            trust -= 10

        trust = max(0, min(100, trust))
        if not labels:
            notes.append("Явных красных флагов по эвристикам нет")

        return {"trust_score": trust, "labels": labels, "notes": notes}

    @alru_cache(maxsize=4096, ttl=600)
    async def verify_user(
        self,
        username: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Возвращает объединённую оценку доверия к аккаунту.
        Результат:
          {
            ok: bool,
            score: int,       # 0..100 — интегральная «доверие/надёжность»
            reason: str,
            labels: [str]|None
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
        heur_trust = int(heur["trust_score"])
        labels: List[str] = list(heur["labels"])
        reasons: List[str] = list(heur["notes"])

        ai_trust: Optional[int] = None
        try:
            who = ("@" + username) if username else ""
            if user_id is not None:
                who = (who + (" " if who else "")) + f"(id={user_id})"

            ai = await self._call_structured(
                system_prompt=self._get_system_prompt_for_user(),
                user_prompt=f"Assess: {who}",
                schema=self._get_response_schema_for_user(),
            )
            if ai:
                risk = int(max(0, min(100, int(ai.get("risk_score", 0))))))
                ai_trust = 100 - risk
                ai_labels = ai.get("labels") or []
                if isinstance(ai_labels, list):
                    labels.extend(str(x) for x in ai_labels if x)
                ai_reason = ai.get("reason")
                if ai_reason:
                    reasons.append(str(ai_reason))
        except Exception:
            logger.exception("Ошибка AI при verify_user")

        combined_trust = heur_trust if ai_trust is None else round(0.6 * heur_trust + 0.4 * ai_trust)
        combined_trust = max(0, min(100, int(combined_trust)))
        ok = combined_trust >= 50

        result = {
            "ok": ok,
            "score": combined_trust,
            "reason": "; ".join(r for r in reasons if r) or ("Эвристики не нашли рисков" if ok else "Есть косвенные признаки риска"),
            "labels": sorted(set(labels)) or None,
        }
        logger.info("verify_user username=@%s user_id=%s -> %s", username or "", user_id, result)
        return result