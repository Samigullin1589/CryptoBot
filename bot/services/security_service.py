# ======================================================================================
# File: bot/services/security_service.py
# Version: "Distinguished Engineer" — MAX Build (Aug 17, 2025)
# Description:
#   Production-grade anti-spam & safety service for aiogram + Redis.
#   Features:
#     • Fast heuristics for spam/toxicity/raid
#     • Offense tracking in Redis with escalation (warn → mute → autoban)
#     • Media analysis (photos/docs) via AIContentService vision (Gemini/OpenAI fallback)
#     • Domain allow/deny lists, link density, mention storms, repeats
#     • Safe-by-default: if AI unavailable — heuristics still protect
#     • Pluggable thresholds via settings.threat_filter (with safe defaults)
#
#   Public API (used by middlewares/handlers):
#     - is_enabled() -> bool
#     - is_blocked(user_id) -> bool                   # uses ModerationService if present
#     - analyze_message(message) -> Verdict
#     - register_violation(user_id, chat_id, reason, weight=1) -> Escalation
#     - decide_and_enforce(bot, message, verdict)     # deletes/mutes/bans in groups
#     - ban_user(admin_id, target_user_id, target_chat_id, reason)
#     - pardon_user(admin_id, target_user_id, target_chat_id)
#
#   Redis keys (with project prefix):
#     <pfx>:sec:off:u:<uid>:c:<chat_id>   -> integer offense counter (EX=window)
#     <pfx>:sec:last:u:<uid>:c:<chat_id>  -> last offense timestamp
# ======================================================================================

from __future__ import annotations

import asyncio
import contextlib
import html
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from collections.abc import Sequence

import redis.asyncio as redis
from aiogram import Bot
from aiogram import types as tg

from bot.config.settings import Settings
from bot.services.ai_content_service import AIContentService

try:
    # Опционально — даёт «жёсткий» глобальный бан по твоему ModerationService
    from bot.services.moderation_service import ModerationService  # type: ignore
except Exception:  # noqa: BLE001
    ModerationService = None  # type: ignore

logger = logging.getLogger(__name__)

# ---------- regexes & helpers ----------
URL_RE = re.compile(
    r"(?i)\b((?:https?://|www\.)[^\s<>\"']+|t\.me/[A-Za-z0-9_]+|@[A-Za-z0-9_]{4,})"
)
REPEAT_CHUNK_RE = re.compile(r"(.)\1{6,}")  # 7+ same chars подряд
CAPS_HEAVY_RE = re.compile(r"[A-ZА-ЯЁ]{8,}")
INVITE_RE = re.compile(
    r"(joinchat|invite|airdrop|free\s+crypto|bonus|giveaway)", re.IGNORECASE
)

# ---------- defaults (overridden by settings.threat_filter if present) ----------
DEF_ENABLED = True
DEF_TOXICITY_THRESHOLD = 0.75
DEF_OFFENSE_WINDOW_SEC = 6 * 3600
DEF_WARN_THRESHOLD = 1
DEF_MUTE_THRESHOLD = 3
DEF_BAN_THRESHOLD = 5
DEF_MUTE_SECONDS = 3600  # 1 hour

# Allow/Deny lists
DEF_DOMAIN_ALLOW: Sequence[str] = (
    "t.me",
    "telegram.me",
    "coingecko.com",
    "cointelegraph.com",
    "forklog.com",
    "beincrypto.com",
    "beincrypto.ru",
    "mempool.space",
    "blockchain.info",
)
DEF_DOMAIN_DENY: Sequence[str] = (
    "bit-ly",
    "bitly.",
    "goo.gl",
    "cutt.ly",
    "tinyurl",
    "ow.ly",
    "grabfree",
    "free-crypto",
    "bonus-crypto",
    "giveaway-crypto",
    "aird0p",
    "xn--",
)


# ---------- data models ----------
@dataclass
class Verdict:
    ok: bool
    reasons: list[str]
    action: str  # "allow" | "delete" | "restrict" | "ban"
    score: float = 0.0
    labels: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.labels is None:
            self.labels = []


@dataclass
class Escalation:
    count: int
    decision: str  # "none" | "warn" | "mute" | "ban"
    mute_seconds: int = 0


class SecurityService:
    def __init__(
        self,
        *,
        redis: redis.Redis,
        settings: Settings | None = None,
        ai_content_service: AIContentService | None = None,
        moderation_service: Any | None = None,
        **_: Any,
    ) -> None:
        """
        Safe-by-default. If AI is missing, heuristics still protect.
        """
        self.redis = redis
        self.settings: Settings = settings or globals().get("settings")  # type: ignore[assignment]
        self.ai = ai_content_service
        self.moderation: ModerationService | None = moderation_service  # type: ignore[assignment]

        tf = getattr(self.settings, "threat_filter", None)
        self.enabled: bool = getattr(tf, "enabled", DEF_ENABLED) if tf else DEF_ENABLED
        self.toxicity_thr: float = (
            getattr(tf, "toxicity_threshold", DEF_TOXICITY_THRESHOLD)
            if tf
            else DEF_TOXICITY_THRESHOLD
        )

        self.window_sec: int = (
            getattr(tf, "offense_window_seconds", DEF_OFFENSE_WINDOW_SEC)
            if tf
            else DEF_OFFENSE_WINDOW_SEC
        )
        self.warn_thr: int = (
            getattr(tf, "warn_threshold", DEF_WARN_THRESHOLD)
            if tf
            else DEF_WARN_THRESHOLD
        )
        self.mute_thr: int = (
            getattr(tf, "mute_threshold", DEF_MUTE_THRESHOLD)
            if tf
            else DEF_MUTE_THRESHOLD
        )
        self.ban_thr: int = (
            getattr(tf, "ban_threshold", DEF_BAN_THRESHOLD) if tf else DEF_BAN_THRESHOLD
        )
        self.mute_seconds: int = (
            getattr(tf, "mute_seconds", DEF_MUTE_SECONDS) if tf else DEF_MUTE_SECONDS
        )
        self.allow_domains: Sequence[str] = tuple(
            getattr(tf, "allow_domains", DEF_DOMAIN_ALLOW) or DEF_DOMAIN_ALLOW
        )
        self.deny_domains: Sequence[str] = tuple(
            getattr(tf, "deny_domains", DEF_DOMAIN_DENY) or DEF_DOMAIN_DENY
        )

        # Project-wide Redis prefix (isolation across envs)
        self._pfx: str = (
            getattr(self.settings, "redis_prefix", None)
            or getattr(self.settings, "project_slug", None)
            or "bot"
        )

        logger.info(
            "SecurityService initialized: enabled=%s, window=%ss, thresholds(warn/mute/ban)=%s/%s/%s.",
            self.enabled,
            self.window_sec,
            self.warn_thr,
            self.mute_thr,
            self.ban_thr,
        )

    # -------- lifecycle --------

    @classmethod
    async def create(cls, **kwargs: Any) -> SecurityService:
        inst = cls(**kwargs)
        return inst

    async def close(self) -> None:  # for DI .close()
        pass

    async def aclose(self) -> None:  # for DI .aclose()
        await self.close()

    # -------- toggles --------

    def is_enabled(self) -> bool:
        return bool(self.enabled)

    # External ban integration for middleware compatibility
    async def is_blocked(self, user_id: int) -> bool:
        """
        If ModerationService is present, defer to it for global/user-level bans.
        Otherwise, return False (anti-spam works per-chat via escalation).
        """
        if self.moderation and hasattr(self.moderation, "is_banned"):
            try:
                return bool(await self.moderation.is_banned(user_id))  # type: ignore[misc]
            except Exception:
                return False
        return False

    # -------- high-level API --------

    async def analyze_message(self, message: tg.Message) -> Verdict:
        """
        Main entry for message safety. Heuristics + optional AI vision/text.
        """
        if not self.enabled:
            return Verdict(ok=True, reasons=["disabled"], action="allow")

        reasons: list[str] = []
        labels: list[str] = []
        score = 0.0

        text = (message.text or message.caption or "") or ""
        media_types = self._detect_media(message)

        # 1) Quick heuristics on text
        if text:
            t_ok, t_labels, t_score = self._heuristics_text(text)
            if not t_ok:
                reasons.append("heuristics_text")
            labels.extend(t_labels)
            score = max(score, t_score)

        # 2) Links & mentions density
        if text:
            link_penalty, link_bad = self._check_links(text)
            if link_bad:
                reasons.append("links_blacklist")
                labels.append("suspicious_link")
                score = max(score, 0.9)
            elif link_penalty:
                labels.append("link_heavy")
                score = max(score, 0.6)

            at_count = text.count("@")
            if at_count >= 8 and len(text) < 2000:
                labels.append("mentions_storm")
                score = max(score, 0.8)
                reasons.append("mentions_storm")

        # 3) Media vision (if present)
        if media_types:
            v_ok, v_labels, v_score = await self._vision_media_gate(
                message, media_types
            )
            if not v_ok:
                reasons.append("vision_block")
            labels.extend(v_labels)
            score = max(score, v_score)

        # Decision
        if reasons:
            action = "delete"
            if "nsfw" in labels or score >= 0.95:
                action = "delete"
            if "phishing" in labels or "suspicious_link" in labels:
                action = "delete"
            return Verdict(
                ok=False,
                reasons=sorted(set(reasons)),
                action=action,
                score=score,
                labels=sorted(set(labels)),
            )

        return Verdict(
            ok=True, reasons=[], action="allow", score=score, labels=sorted(set(labels))
        )

    async def decide_and_enforce(
        self, bot: Bot, message: tg.Message, verdict: Verdict
    ) -> Escalation | None:
        """
        Applies the verdict and updates offense counters with escalation.
        - In private chats: only delete & warn.
        - In groups/supergroups: delete + (warn/mute/ban).
        Returns Escalation or None.
        """
        if verdict.ok:
            return None

        user_id = message.from_user.id if message.from_user else None
        chat_id = message.chat.id if message.chat else None
        chat_type = message.chat.type if message.chat else "private"
        if not user_id or not chat_id:
            return None

        # 1) delete message (if possible)
        with contextlib.suppress(Exception):
            await message.delete()

        # 2) register offense & escalate
        esc = await self.register_violation(
            user_id, chat_id, reason=";".join(verdict.reasons)
        )

        is_group = chat_type in ("group", "supergroup")

        # 3) enforce escalation
        if esc.decision == "warn":
            await self._send_ephemeral(
                bot,
                chat_id,
                f"⚠️ {self._u_mention(message)}: предупреждение за спам/нарушение.",
            )
        elif esc.decision == "mute" and is_group:
            until = datetime.now(timezone.utc) + timedelta(
                seconds=esc.mute_seconds or self.mute_seconds
            )
            with contextlib.suppress(Exception):
                await bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=tg.ChatPermissions(can_send_messages=False),
                    until_date=until,
                )
            await self._send_ephemeral(
                bot,
                chat_id,
                f"🔇 {self._u_mention(message)} заглушен на {(esc.mute_seconds or self.mute_seconds) // 60} мин.",
            )
        elif esc.decision == "ban" and is_group:
            # Баним в чате
            with contextlib.suppress(Exception):
                await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await self._send_ephemeral(
                bot,
                chat_id,
                f"⛔ {self._u_mention(message)} заблокирован за повторные нарушения.",
            )

            # При наличии ModerationService — фиксируем глобальный бан (опционально)
            if self.moderation and hasattr(self.moderation, "ban"):
                with contextlib.suppress(Exception):
                    await self.moderation.ban(
                        user_id=user_id,
                        by_id=0,
                        reason="auto-ban by security",
                        duration=None,
                    )  # type: ignore[misc]

        return esc

    async def register_violation(
        self, user_id: int, chat_id: int, *, reason: str, weight: int = 1
    ) -> Escalation:
        """
        Increments offense counter within window. Decides escalation stage.
        """
        k = f"{self._pfx}:sec:off:u:{user_id}:c:{chat_id}"
        k_last = f"{self._pfx}:sec:last:u:{user_id}:c:{chat_id}"
        try:
            pipe = self.redis.pipeline()
            pipe.incrby(k, amount=max(1, int(weight)))
            pipe.expire(k, self.window_sec)
            pipe.set(k_last, int(time.time()), ex=self.window_sec)
            res = await pipe.execute()
            count = int(res[0]) if res and len(res) >= 1 else 1
        except Exception as e:
            logger.debug("register_violation error: %s", e)
            count = self.warn_thr

        # Decide
        if count >= self.ban_thr:
            return Escalation(count=count, decision="ban")
        if count >= self.mute_thr:
            return Escalation(
                count=count, decision="mute", mute_seconds=self.mute_seconds
            )
        if count >= self.warn_thr:
            return Escalation(count=count, decision="warn")
        return Escalation(count=count, decision="none")

    async def ban_user(
        self, admin_id: int, target_user_id: int, target_chat_id: int, reason: str = ""
    ) -> str:
        """
        Helper for handlers (admin panels). Does not perform Telegram API calls here.
        """
        txt = f"Администратор {admin_id} инициировал бан {target_user_id} в чате {target_chat_id}."
        if reason:
            txt += f" Причина: {reason}"
        logger.info("SecurityService: %s", txt)
        return txt

    async def pardon_user(
        self, admin_id: int, target_user_id: int, target_chat_id: int
    ) -> str:
        """
        Clears counters and returns text for UI.
        """
        with contextlib.suppress(Exception):
            await self.redis.delete(
                f"{self._pfx}:sec:off:u:{target_user_id}:c:{target_chat_id}"
            )
            await self.redis.delete(
                f"{self._pfx}:sec:last:u:{target_user_id}:c:{target_chat_id}"
            )
        txt = f"Администратор {admin_id} помиловал {target_user_id} в чате {target_chat_id}."
        logger.info("SecurityService: %s", txt)
        return txt

    # -------- internals --------

    def _detect_media(self, m: tg.Message) -> list[str]:
        types: list[str] = []
        if m.photo:
            types.append("photo")
        if m.document:
            mime = getattr(m.document, "mime_type", "") or ""
            if mime.startswith("image/"):
                types.append("image")
            else:
                types.append("document")
        if m.video:
            types.append("video")
        if m.animation:
            types.append("gif")
        return types

    def _heuristics_text(self, text: str) -> tuple[bool, list[str], float]:
        labels: list[str] = []
        score = 0.0
        ok = True

        # Massive repeats / caps
        if REPEAT_CHUNK_RE.search(text):
            labels.append("repeat")
            score = max(score, 0.7)
            ok = False
        # caps — сигнал, но не всегда блокирующий
        if CAPS_HEAVY_RE.search(text) and len(text) >= 16:
            labels.append("caps")
            score = max(score, 0.55)

        # Invite spam / phishing words
        if INVITE_RE.search(text):
            labels.append("phishing")
            score = max(score, 0.9)
            ok = False

        # Link density
        links = URL_RE.findall(text)
        if links:
            density = len(links) / max(1, len(text) / 40.0)  # ~1 link per 40 chars ok
            if density > 0.6:
                labels.append("link_dense")
                score = max(score, 0.7)

        return ok, labels, score

    def _check_links(self, text: str) -> tuple[bool, bool]:
        """
        Returns (penalty, hard_block_by_blacklist)
        """
        penalty = False
        hard = False
        for m in URL_RE.findall(text):
            host = self._extract_host(str(m))
            if not host:
                continue
            if any(bad in host for bad in self.deny_domains):
                hard = True
            if not any(allow in host for allow in self.allow_domains):
                penalty = True
        return penalty, hard

    @staticmethod
    def _extract_host(url: str) -> str | None:
        u = url.lower()
        u = u.replace("https://", "").replace("http://", "")
        if u.startswith("www."):
            u = u[4:]
        return u.split("/")[0] if "/" in u else u

    async def _vision_media_gate(
        self, message: tg.Message, media_types: list[str]
    ) -> tuple[bool, list[str], float]:
        """
        If AI vision available, analyze images/photos. Otherwise, pass-through.
        """
        if not self.ai:
            return True, [], 0.0

        labels: list[str] = []
        score = 0.0

        # Try various method names for best compatibility
        method = None
        for name in (
            "analyze_vision_content",
            "analyze_image_content",
            "vision_moderate",
        ):
            if hasattr(self.ai, name):
                method = getattr(self.ai, name)
                break

        if not method:
            return True, [], 0.0

        # Invoke with flexible signature
        try:
            # Preferred signature: (message=..., bot=...) so service can fetch bytes by itself
            res: dict[str, Any]
            try:
                res = await method(message=message, bot=getattr(message, "bot", None))  # type: ignore[misc]
            except TypeError:
                prompt = "Проверь изображение/медиа на спам, фишинг, NSFW, QR/фишинговые линки, крипто-лохотроны."
                res = await method(prompt)  # type: ignore[misc]

            # Expected res format (flexible):
            # {
            #   "ok": bool,
            #   "labels": ["nsfw","phishing_image",...],
            #   "score": float,
            #   "reason": "..."
            # }
            v_ok = bool(res.get("ok", True))
            v_labels = list(res.get("labels", []))
            v_score = float(res.get("score", 0.0))
            reason = str(res.get("reason", ""))

            if not v_ok and reason:
                v_labels.append(reason)

            # Normalize NSFW/phishing hints from AI
            if any(lbl.lower() in {"nsfw", "adult", "explicit"} for lbl in v_labels):
                labels.append("nsfw")
                v_ok = False
                v_score = max(v_score, 0.95)
            if any("phish" in lbl.lower() for lbl in v_labels):
                labels.append("phishing_image")
                v_ok = False
                v_score = max(v_score, 0.9)

            labels.extend(v_labels)
            score = max(score, v_score)
            return v_ok, labels, score
        except Exception as e:
            logger.debug("Vision gate error: %s", e)
            return True, [], 0.0

    async def _send_ephemeral(self, bot: Bot, chat_id: int, text: str) -> None:
        """
        Sends a temporary message and deletes it after 5 seconds.
        """
        with contextlib.suppress(Exception):
            msg = await bot.send_message(chat_id, text)
            await asyncio.sleep(5)
            with contextlib.suppress(Exception):
                await msg.delete()

    @staticmethod
    def _u_mention(message: tg.Message) -> str:
        u = message.from_user
        if not u:
            return "user"
        name = (u.full_name or u.username or str(u.id)).strip()
        return f'<a href="tg://user?id={u.id}">{html.escape(name)}</a>'


__all__ = ["SecurityService", "Verdict", "Escalation"]
