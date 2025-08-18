# ======================================================================================
# File: bot/middlewares/security_middleware.py
# Version: "Distinguished Engineer" — MAX Build (Aug 16, 2025)
# Description:
#   Inline anti-spam middleware using AIContentService + Redis counters.
#   - Text moderation (heuristics + optional OpenAI)
#   - Image spam scoring via Gemini-Vision (if configured)
#   - Progressive enforcement: warn → delete → mute/ban on repeat
#   - Respects existing SecurityService if present (delegates when available)
# ======================================================================================

from __future__ import annotations

import contextlib
import logging
from typing import Any, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseMiddleware):
    """
    Middleware chain:
      1) if deps.security_service has `handle_incoming_update(message, deps)` -> delegate (project's logic)
      2) else:
         - score text via deps.ai_content_service.moderate_text()
         - for photos/stickers: estimate spam via deps.ai_content_service.spam_score_image()
         - maintain counters in Redis; escalate actions on repeat
    """

    def __init__(
        self,
        deps: Deps,
        *,
        warn_threshold: float = 0.65,
        delete_threshold: float = 0.80,
        autoban_threshold: float = 0.90,
        repeat_window_seconds: int = 24 * 3600,
        repeat_ban_count: int = 2,
    ) -> None:
        super().__init__()
        self.deps = deps
        self.warn_th = warn_threshold
        self.del_th = delete_threshold
        self.ban_th = autoban_threshold
        self.window = repeat_window_seconds
        self.repeat_ban = repeat_ban_count

    async def __call__(self, handler, event: Message, data: Dict[str, Any]):
        # allow other updates (callbacks etc.)
        if not isinstance(event, Message):
            return await handler(event, data)

        deps = self.deps
        # 0) If project has its own security_service, delegate first
        sec = getattr(deps, "security_service", None)
        if sec is not None and hasattr(sec, "handle_incoming_update"):
            try:
                handled = await sec.handle_incoming_update(event, deps)  # type: ignore[misc]
                if handled:
                    return  # already moderated
            except Exception as e:
                logger.warning("security_service.handle_incoming_update failed: %s", e)

        # 1) Our built-in path
        try:
            score = 0.0
            cues = {}

            if event.text or event.caption:
                text = (event.text or "") + "\n" + (event.caption or "")
                try:
                    res = await deps.ai_content_service.moderate_text(text)
                    score = max(score, float(res.get("score", 0.0)))
                    cues.update(res.get("flags", {}))
                except Exception as e:
                    logger.debug("moderate_text() error: %s", e)

            # Vision for images/stickers/documents (images)
            if event.photo or (event.sticker and getattr(event.sticker, "is_video", False) is False):
                # Get best resolution photo bytes
                images = []
                try:
                    if event.photo:
                        photo = event.photo[-1]
                        file = await event.bot.get_file(photo.file_id)
                        b = await event.bot.download_file(file.file_path)
                        images.append(b.read())
                    elif event.sticker and event.sticker.is_animated is False and event.sticker.file_id:
                        file = await event.bot.get_file(event.sticker.file_id)
                        b = await event.bot.download_file(file.file_path)
                        images.append(b.read())
                except Exception as e:
                    logger.debug("Failed to fetch image bytes: %s", e)

                if images:
                    try:
                        vis = await deps.ai_content_service.spam_score_image(
                            caption=(event.caption or event.text or ""),
                            images=images,
                        )
                        score = max(score, float(vis.get("score", 0.0)))
                        cues.update(vis.get("cues", {}))
                    except Exception as e:
                        logger.debug("spam_score_image() error: %s", e)

            # 2) Enforcement based on thresholds + repeats
            if score < self.warn_th:
                return await handler(event, data)

            # Track repeats (per chat+user)
            chat_id = getattr(event.chat, "id", None)
            user_id = getattr(event.from_user, "id", None) if event.from_user else None
            if chat_id is None or user_id is None:
                return await handler(event, data)

            r = deps.redis
            key_base = f"sec:chat:{chat_id}:user:{user_id}"
            try:
                await r.hsetnx(key_base, "first_ts", int(event.date.timestamp()))
                await r.hincrbyfloat(key_base, "score_sum", score)
                c = await r.hincrby(key_base, "cnt", 1)
                await r.expire(key_base, self.window)
            except Exception:
                c = 1

            # Action selection
            # a) delete on high score
            if score >= self.del_th:
                with contextlib.suppress(Exception):
                    await event.delete()

            # b) warn
            try:
                await event.answer(
                    "⚠️ Сообщение отмечено системой защиты как потенциальный спам."
                    " Повторные нарушения приведут к ограничениям."
                )
            except Exception:
                pass

            # c) autoban if very high score or if repeats exceed N
            #    (mute attempt if ban fails)
            need_ban = score >= self.ban_th or c >= self.repeat_ban
            if need_ban and event.chat.type in ("group", "supergroup", "channel"):
                try:
                    await event.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
                    try:
                        await event.answer("🚫 Пользователь автоматически заблокирован системой защиты.")
                    except Exception:
                        pass
                    return
                except Exception as e:
                    logger.debug("Auto-ban failed (%s). Trying to restrict...", e)
                    # Try to restrict for 24h
                    try:
                        until = int(event.date.timestamp()) + 24 * 3600
                        await event.bot.restrict_chat_member(
                            chat_id=chat_id,
                            user_id=user_id,
                            permissions={"can_send_messages": False},
                            until_date=until,
                        )
                        try:
                            await event.answer("⛔ Включено временное ограничение отправки сообщений (24ч).")
                        except Exception:
                            pass
                        return
                    except Exception as e2:
                        logger.debug("Auto-restrict failed: %s", e2)

            # If we reached here, pass to next handler
            return await handler(event, data)

        except Exception as e:
            logger.error("SecurityMiddleware unexpected error: %s", e, exc_info=True)
            return await handler(event, data)
