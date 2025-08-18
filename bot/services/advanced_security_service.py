# bot/services/advanced_security_service.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = object  # type: ignore

URL_RE = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)
INVITE_RE = re.compile(
    r"(t\.me/joinchat/|t\.me/\+|discord\.gg/|wa\.me/)", re.IGNORECASE
)


@dataclass
class Verdict:
    action: str | None = None  # None|delete|warn|mute|ban
    reason: str = ""
    minutes: int = 60


class AdvancedSecurityService:
    """
    Opinionated anti-spam engine that uses Redis for counters and memory.
    Features:
      - Heuristic text & link checks
      - Self-learning memory (via AntiSpamLearning)
      - Optional image analysis (via ImageVisionService)
      - Autoban on repeated offenses within a window
    """

    def __init__(
        self,
        redis: Redis,
        learning,
        image_vision=None,
        settings=None,
        ns: str = "sec",
    ) -> None:
        self.r = redis
        self.learning = learning
        self.vision = image_vision
        self.settings = settings
        self.ns = ns

    # Redis keys
    def k_user_strikes(self, chat_id: int, user_id: int) -> str:
        return f"{self.ns}:strikes:{chat_id}:{user_id}"

    def _cfg(self, name: str, default: Any) -> Any:
        tf = getattr(getattr(self.settings, "threat_filter", None), name, None)
        return tf if tf is not None else default

    async def _extract_domains(self, text: str) -> list[str]:
        hosts: list[str] = []
        for m in URL_RE.finditer(text or ""):
            try:
                host = urlparse(m.group(1)).hostname or ""
                if not host:
                    continue
                # Ignore obvious safe hosts (Telegram itself, youtube, etc.) – config later
                hosts.append(host.lower())
            except Exception:
                continue
        return hosts

    def _text_suspicions(self, text: str) -> int:
        score = 0
        t = (text or "").lower()
        if any(
            x in t
            for x in (
                "быстрый заработок",
                "доход",
                "ставки",
                "казино",
                "подписывайся",
                "заработай",
                "успей",
            )
        ):
            score += 60
        if INVITE_RE.search(t):
            score += 30
        if len(t) > 350:
            score += 10
        return score

    async def _image_verdict(self, message) -> tuple[bool, str] | None:
        if not self.vision:
            return None
        try:
            # pick largest photo
            p = max(message.photo, key=lambda x: (x.width or 0) * (x.height or 0))
            file = await message.bot.get_file(p.file_id)
            buf = await message.bot.download_file(file.file_path)
            data = buf.read()
            ok, details = await self.vision.analyze(data)
            if ok:
                return True, details.get(
                    "explanation"
                ) or "Image marked as advertising/spam"
        except Exception:
            return None
        return None

    async def inspect_message(self, message) -> dict[str, Any]:
        """
        Returns dict with optional 'action' and more fields.
        """
        user = message.from_user
        if not user:
            return {}

        chat_id = message.chat.id

        # 1) Gather text from various content types
        text_parts = []
        if message.text:
            text_parts.append(message.text)
        if message.caption:
            text_parts.append(message.caption)
        text = "\n".join(text_parts).strip()

        # 2) Heuristics
        score = self._text_suspicions(text)

        # 3) Links / domains
        bad_domain = False
        domains = await self._extract_domains(text)
        for host in domains:
            if await self.learning.is_bad_domain(host):
                bad_domain = True
                score += 50
                break
            # suspicious TLDs heuristic
            if host.endswith((".xyz", ".top", ".tokyo", ".icu", ".bet", ".casino")):
                score += 10

        # 4) Self-learning phrases
        best_ratio, best_phrase = await self.learning.score_text(text, min_ratio=85)
        if best_ratio and best_phrase:
            score += min(40, best_ratio // 3)

        # 5) Images
        if getattr(message, "photo", None):
            iv = await self._image_verdict(message)
            if iv and iv[0]:
                score += 60

        # 6) Decide action
        _ = getattr(
            getattr(self.settings, "threat_filter", object()),
            "toxicity_threshold",
            0.75,
        )
        # convert to 0..1 scale roughly
        prob = min(1.0, max(0.0, score / 100.0))

        action: str | None = None
        reason = ""

        # progressive actions
        if prob >= 0.95 or bad_domain:
            action, reason = "ban", "Autoban (bad domain or very high score)"
        elif prob >= 0.85:
            action, reason = "mute", "Temporary mute due to suspicious content"
        elif prob >= 0.75:
            action, reason = "warn", "Suspicious content – warning"
        elif prob >= 0.60:
            action, reason = "delete", "Low-confidence spam – deleted"

        # 7) Strikes escalation on repeat
        if action in ("delete", "warn", "mute"):
            strikes_window = int(
                getattr(
                    getattr(self.settings, "threat_filter", object()),
                    "repeat_window_seconds",
                    3600,
                )
            )
            strikes_for_ban = int(
                getattr(
                    getattr(self.settings, "threat_filter", object()),
                    "strikes_for_autoban",
                    2,
                )
            )
            key = self.k_user_strikes(chat_id, user.id)
            try:
                # increment with TTL window
                pipe = self.r.pipeline()
                pipe.incr(key)
                pipe.expire(key, strikes_window)
                v, _ = await pipe.execute()
                strikes = int(v or 0)
            except Exception:
                strikes = 1

            if strikes >= strikes_for_ban:
                action, reason = "ban", "Autoban on repeated offenses"

        return {
            "action": action,
            "reason": reason,
            "score": score,
            "domains": domains,
            "best_phrase": getattr(best_phrase, "phrase", None),
        }
