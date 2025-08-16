# =============================================================================
# File: bot/services/image_guard_service.py
# Purpose: Anti-spam for images with OCR (Gemini) + perceptual hash + escalation
# Ban policy: autoban after N triggers (default: 3, override via settings.security.image_spam_autoban_threshold)
# =============================================================================
from __future__ import annotations

import contextlib
import io
import re
from dataclasses import dataclass
from typing import Optional, Tuple, Iterable, Any

from PIL import Image
import numpy as np

from aiogram import Bot
from aiogram.types import Message, PhotoSize

from bot.utils.dependencies import Deps


_SPAM_PATTERNS = (
    r"(airdrop|bonus|claim|gift|giveaway|win\s+\$?\d+|guarantee|support|客服|赠送|抽奖)",
    r"(usdt|trx|bnb|eth|btc)\b",
    r"(free\s+(crypto|money|nft))",
    r"(подпис(ывайся|ка)|розыгрыш|бонус|подарок|приз|выиграй)",
    r"(100%\s*доход|быстрые\s*деньги|инвестиции\s*без\s*риска)",
    r"(t\.me/|@[\w_]{3,})",
    r"(wa\.me/|bit\.ly/|goo\.gl/|tinyurl\.com/)",
)
_SPAM_RX = re.compile("|".join(_SPAM_PATTERNS), re.IGNORECASE)


@dataclass
class ImageVerdict:
    action: str     # "allow" | "delete" | "ban"
    reason: str = ""


class ImageGuardService:
    """
    Анализ фото:
      1) Скачиваем байты.
      2) Сверяем aHash с базой известных спам-баннеров (устойчиво к сжатию/скейлу).
      3) OCR через Gemini (если доступен) + эвристики по тексту/подписи.
      4) Эскалация: при повторе — автобан.
    """

    def __init__(self, deps: Deps):
        self.deps = deps
        self.redis = deps.redis
        self.settings = deps.settings
        # Redis keys
        self._k_hashes = "security:spam_image_hashes"    # set of hex64
        self._k_seen_cnt = "security:user_spam_img_cnt"  # hash: user_id -> count

    # -------------------- public API --------------------

    async def check_message_with_photo(self, bot: Bot, message: Message) -> ImageVerdict:
        photo = self._pick_best_photo(message.photo or [])
        if not photo:
            return ImageVerdict("allow")

        img_bytes = await self._download_photo(bot, photo)
        if not img_bytes:
            return ImageVerdict("allow")

        # 1) быстрый hash-check
        h = self._ahash(img_bytes)
        if h is not None:
            is_known, dist = await self._is_known_spam_hash(h, max_distance=5)
            if is_known:
                return await self._punish(message, f"Известная спам-картинка (dist={dist}).")

        # 2) подпись + OCR текст
        full_text = (message.caption or "").strip()
        ocr_text = await self._ocr_with_gemini(img_bytes)
        if ocr_text:
            full_text = f"{full_text}\n{ocr_text}".strip()

        if self._looks_spam(full_text):
            return await self._punish(message, "Подозрительный текст на изображении/в подписи.")

        return ImageVerdict("allow")

    async def mark_current_photo_as_spam(self, bot: Bot, message: Message) -> str:
        """Админский хелпер: добавить хэш текущего изображения в чёрный список."""
        photo = self._pick_best_photo(message.photo or [])
        if not photo:
            return "Нет фото в сообщении."
        img_bytes = await self._download_photo(bot, photo)
        if not img_bytes:
            return "Не удалось скачать фото."
        h = self._ahash(img_bytes)
        if h is None:
            return "Не удалось вычислить хэш."
        await self.redis.sadd(self._k_hashes, f"{h:016x}")
        return "Хэш изображения добавлен в черный список."

    # -------------------- internals --------------------

    def _pick_best_photo(self, photos: Iterable[PhotoSize]) -> Optional[PhotoSize]:
        best = None
        max_area = -1
        for ph in photos:
            w = getattr(ph, "width", 0) or 0
            h = getattr(ph, "height", 0) or 0
            area = w * h
            if area > max_area:
                max_area = area
                best = ph
        return best

    async def _download_photo(self, bot: Bot, photo: PhotoSize) -> Optional[bytes]:
        buff = io.BytesIO()
        try:
            await bot.download(photo, destination=buff)  # aiogram v3
            return buff.getvalue()
        except Exception:
            pass
        try:
            f = await bot.get_file(photo.file_id)
            dst = io.BytesIO()
            await bot.download_file(f.file_path, dst)  # fallback
            return dst.getvalue()
        except Exception:
            return None

    def _ahash(self, image_bytes: bytes, size: int = 8) -> Optional[int]:
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((size, size), Image.LANCZOS)
            arr = np.asarray(img, dtype=np.float32)
            avg = arr.mean()
            bits = (arr >= avg).astype(np.uint8)
            v = 0
            for b in bits.flatten():
                v = (v << 1) | int(b)
            return v
        except Exception:
            return None

    async def _is_known_spam_hash(self, h: int, max_distance: int = 5) -> Tuple[bool, int]:
        try:
            members = await self.redis.smembers(self._k_hashes)
        except Exception:
            return False, 64
        if not members:
            return False, 64

        hv = int(h)
        best = 64
        for m in members:
            try:
                mv = int(m, 16) if isinstance(m, str) else int(m.decode(), 16)
            except Exception:
                continue
            d = self._hamming(hv, mv)
            if d < best:
                best = d
                if d <= max_distance:
                    return True, d
        return False, best

    def _hamming(self, a: int, b: int) -> int:
        return (a ^ b).bit_count()

    async def _ocr_with_gemini(self, img_bytes: bytes) -> Optional[str]:
        svc = getattr(self.deps, "ai_content_service", None)
        if svc is None:
            return None
        model = getattr(svc, "gemini_pro", None) or getattr(svc, "gemini_flash", None)
        if model is None:
            return None

        prompt = (
            "Извлеки читабельный текст с изображения как есть (без домыслов). "
            "Верни только текст без лишних комментариев."
        )
        try:
            result = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_bytes}])
            text = getattr(result, "text", None)
            if not text and getattr(result, "candidates", None):
                parts = result.candidates[0].content.parts
                if parts and getattr(parts[0], "text", None):
                    text = parts[0].text
            return (text or "").strip() or None
        except Exception:
            return None

    def _looks_spam(self, text: str) -> bool:
        if not text:
            return False
        if _SPAM_RX.search(text):
            return True
        money_marks = len(re.findall(r"[💰💵🪙\$€₽₿₮₺₹₩₪₫₴₦₱]", text))
        links = len(re.findall(r"https?://|t\.me/", text, re.IGNORECASE))
        at_tags = len(re.findall(r"@\w{3,}", text))
        score = money_marks + links + at_tags
        return score >= 4

    async def _punish(self, message: Message, reason: str) -> ImageVerdict:
        # 1) удаляем сообщение
        with contextlib.suppress(Exception):
            await message.delete()

        # 2) увеличиваем счётчик нарушений
        try:
            uid = message.from_user.id if message.from_user else 0
            await self.redis.hincrby(self._k_seen_cnt, uid, 1)
            cnt = int(await self.redis.hget(self._k_seen_cnt, uid) or 0)
        except Exception:
            cnt = 1

        # 3) порог автобана
        sec = getattr(self.settings, "security", None)
        threshold = 3
        with contextlib.suppress(Exception):
            threshold = int(getattr(sec, "image_spam_autoban_threshold", 3))
        if threshold < 1:
            threshold = 1

        # 4) эскалация: баним в группах/супергруппах
        chat_type = getattr(message.chat, "type", "private")
        should_ban = cnt >= threshold and chat_type in ("group", "supergroup")

        if should_ban:
            banned = await self._ban_user(message, reason=f"Автобан (спам-картинки), count={cnt}. {reason}")
            if banned:
                with contextlib.suppress(Exception):
                    await message.answer(f"🚫 Пользователь заблокирован (антиспам: изображение). Причина: {reason}")
                return ImageVerdict("ban", f"{reason} (count={cnt})")

        # 5) мягкое уведомление
        with contextlib.suppress(Exception):
            await message.answer(f"🚫 Сообщение удалено (антиспам: изображение). Причина: {reason} (повторов: {cnt})")

        return ImageVerdict("delete", reason)

    async def _ban_user(self, message: Message, reason: str) -> bool:
        try:
            user_id = message.from_user.id if message.from_user else None
            if user_id is None:
                return False
            chat_id = message.chat.id

            # Пытаемся использовать централизованный ModerationService, если он есть
            mod = getattr(self.deps, "moderation_service", None)
            if mod is not None:
                # пытаемся аккуратно определить "админа"-инициатора
                admin_id = 0
                with contextlib.suppress(Exception):
                    # у некоторых ботов есть bot.id / bot.me.id
                    admin_id = getattr(message.bot, "id", 0) or getattr(getattr(message.bot, "me", None), "id", 0) or 0
                await mod.ban_user(
                    admin_id=admin_id,
                    target_user_id=user_id,
                    target_chat_id=chat_id,
                    reason=reason,
                )
                return True

            # Фоллбек: напрямую через Telegram API
            await message.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            return True
        except Exception:
            return False