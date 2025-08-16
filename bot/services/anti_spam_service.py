# =============================================================================
# File: bot/services/anti_spam_service.py
# Purpose: Text+Image Anti-Spam with online learning + Redis persistence
# Requires: aiogram, redis (async), pillow (already in your deps)
# =============================================================================

from __future__ import annotations

import asyncio
import hashlib
import html
import io
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from aiogram import Bot
from aiogram.types import Message, PhotoSize
from PIL import Image, ImageOps  # pillow

# --- Small utilities ---------------------------------------------------------

ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200F\uFEFF]", re.UNICODE)
URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
CONTACT_RE = re.compile(r"(?:t\.me/|@[\w\d_]{4,}|wa\.me/\d+|https?://\S*telegram\.me/\S+)", re.IGNORECASE)
MASS_REPEAT_RE = re.compile(r"(.)\1{6,}")  # 7+ одинаковых символов подряд
EMOJI_SPAM_RE = re.compile(r"(?:[\U0001F300-\U0001FAFF]\uFE0F?){8,}")

# Латиница↔кириллица часто обфусцируют одинаково выглядящими символами.
CONFUSABLES = str.maketrans(
    {
        "о": "o", "О": "O", "а": "a", "А": "A", "е": "e", "Е": "E",
        "р": "p", "Р": "P", "с": "c", "С": "C", "х": "x", "Х": "X",
        "у": "y", "У": "Y", "к": "k", "К": "K", "В": "B", "Т": "T",
        "М": "M", "Н": "H",
    }
)
LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t"})

def normalize_text(text: str) -> str:
    txt = text or ""
    txt = html.unescape(txt)
    txt = ZERO_WIDTH_RE.sub("", txt)
    txt = txt.translate(CONFUSABLES)
    txt = txt.translate(LEET)
    txt = txt.lower()
    # нормализуем пробелы/пунктуацию
    txt = re.sub(r"[^a-z0-9а-яё@#\.\:/\-\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def sha1_short(data: bytes, nbits: int = 64) -> int:
    h = hashlib.sha1(data).digest()
    # первые 8 байт -> 64 бита
    return int.from_bytes(h[:8], "big") if nbits == 64 else int.from_bytes(h, "big") >> (len(h) * 8 - nbits)

# --- Hashing trick vectorizer (feature hashing) ------------------------------

def hashed_features(tokens: list[str], n_bits: int = 20) -> Dict[int, int]:
    """
    Простейший «feature hashing»: хэшируем токены в 2^n_bits корзин.
    Возвращает {index: count}.
    """
    size = 1 << n_bits
    feats: Dict[int, int] = {}
    for tok in tokens:
        idx = sha1_short(tok.encode("utf-8"), nbits=64) % size
        feats[idx] = feats.get(idx, 0) + 1
    return feats

def tokenize(txt: str) -> list[str]:
    # токены + шинглы 3-символьные (для устойчивости к обфускации)
    parts = txt.split()
    chars = re.sub(r"\s+", "", txt)
    shingles = [chars[i : i + 3] for i in range(max(0, len(chars) - 2))]
    return parts + shingles

# --- Online Multinomial Naive Bayes ------------------------------------------

@dataclass
class NBModel:
    n_bits: int = 20
    alpha: float = 1.0  # Лаплас
    spam_docs: int = 0
    ham_docs: int = 0
    spam_counts_key: str = "antispam:nb:spam"
    ham_counts_key: str = "antispam:nb:ham"
    meta_key: str = "antispam:nb:meta"

    @property
    def vocab_size(self) -> int:
        return 1 << self.n_bits

class AntiSpamService:
    """
    Самодостаточный антиспам:
      - текст: эвристики + онлайн NB с feature hashing;
      - картинки: dHash (64 бита) + Hamming, Redis-бакеты по префиксу;
      - эскалация по Redis-счётчикам.
    """

    def __init__(self, redis, bot: Bot, settings: Optional[Any] = None):
        self.r = redis
        self.bot = bot
        self.settings = settings

        # thresholds / конфиг с безопасными дефолтами
        sec = getattr(settings, "security", None)
        self.warn_threshold = getattr(sec, "warn_threshold", 1)           # 1 нарушение → предупреждение/удаление
        self.mute_threshold = getattr(sec, "mute_threshold", 2)           # 2 → мут
        self.ban_threshold = getattr(sec, "ban_threshold", 3)             # 3 → бан
        self.window_sec = getattr(sec, "window_sec", 6 * 60 * 60)         # окно повторов (6ч)
        self.mute_minutes = getattr(sec, "mute_minutes", 60)              # длительность мута

        # image hashing
        self.phash_prefix_bits = getattr(sec, "phash_prefix_bits", 16)
        self.phash_distance = getattr(sec, "phash_distance", 10)          # 64-битный dHash; 8–12 обычно разумно

        # NB model
        self.nb = NBModel(n_bits=getattr(sec, "nb_bits", 20), alpha=1.0)

    # ---------- public API ----------------------------------------------------

    async def analyze_and_act(self, message: Message) -> Optional[str]:
        """
        Возвращает строку с действием для логов (или None), применяет меры:
        delete / warn / mute / ban (эскалация).
        """
        # только для чатов/групп
        if not message.chat or message.chat.type == "private":
            return None

        verdict, reason = await self._classify_message(message)

        if verdict == "ok":
            return None

        # удаляем сообщение
        with contextlib.suppress(Exception):
            await message.delete()

        # увеличиваем счётчик нарушений пользователя
        count = await self._bump_user_violations(message.chat.id, message.from_user.id)

        if count >= self.ban_threshold:
            await self._ban_user(message.chat.id, message.from_user.id, reason)
            action = "ban"
        elif count >= self.mute_threshold:
            await self._mute_user(message.chat.id, message.from_user.id)
            action = "mute"
        else:
            # предупреждение тостом (без шума в чате)
            with contextlib.suppress(Exception):
                await message.answer(
                    "⛔️ Сообщение удалено как спам. Повтор — авто-мут, дальше — авто-бан."
                )
            action = "warn"

        return f"{action}:{reason}"

    async def learn_from_admin_action(self, *, is_spam: bool, text: Optional[str] = None) -> None:
        """Вызывайте из модерации: ban → is_spam=True, pardon → False."""
        if not text:
            return
        await self._nb_partial_fit(text, int(is_spam))

    # ---------- core classification ------------------------------------------

    async def _classify_message(self, m: Message) -> Tuple[str, str]:
        # 1) быстрые правила
        raw_txt = (m.text or m.caption or "")[:4096]
        txt = normalize_text(raw_txt)

        heuristics = self._heuristics(txt, m)
        if heuristics:
            return "spam", heuristics  # уже понятно

        # 2) dHash изображений (если есть)
        if m.photo:
            if await self._is_spam_image(m):
                return "spam", "image-similar"

        # 3) Байес — мягкий сигнал
        prob_spam = await self._nb_predict(txt)
        if prob_spam >= 0.92:
            return "spam", f"nb:{prob_spam:.2f}"

        return "ok", "clean"

    def _heuristics(self, txt: str, m: Message) -> Optional[str]:
        if URL_RE.search(txt):
            return "url"
        if CONTACT_RE.search(txt):
            return "contact"
        if MASS_REPEAT_RE.search(txt):
            return "mass-repeat"
        if EMOJI_SPAM_RE.search(txt):
            return "emoji-mass"
        # файлы-изображения как документ
        if m.document and (m.document.mime_type or "").startswith("image/"):
            return "image-doc"
        return None

    # ---------- Redis counters / escalation ----------------------------------

    async def _bump_user_violations(self, chat_id: int, user_id: int) -> int:
        key = f"antispam:viol:{chat_id}:{user_id}"
        count = await self.r.incr(key)
        await self.r.expire(key, self.window_sec)
        return int(count)

    async def _mute_user(self, chat_id: int, user_id: int) -> None:
        until = int(time.time()) + self.mute_minutes * 60
        with contextlib.suppress(Exception):
            await self.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions={"can_send_messages": False},  # aiogram преобразует
                until_date=until,
            )

    async def _ban_user(self, chat_id: int, user_id: int, reason: str) -> None:
        with contextlib.suppress(Exception):
            await self.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        # след для аудита — отпечаток причины
        await self.r.setex(f"antispam:banreason:{chat_id}:{user_id}", 3 * 24 * 3600, reason)

    # ---------- Image hashing (dHash 64-bit) ---------------------------------

    async def _is_spam_image(self, m: Message) -> bool:
        try:
            ph = await self._message_dhash(m)
        except Exception:
            return False
        if ph is None:
            return False
        # префикс-бакет по старшим self.phash_prefix_bits
        pref = ph >> (64 - self.phash_prefix_bits)
        key = f"antispam:phash:{pref:0{self.phash_prefix_bits//4}x}"

        # проверяем соседей
        candidates = await self.r.smembers(key)
        for c in candidates or []:
            other = int(c)
            if hamming64(ph, other) <= self.phash_distance:
                return True

        # не спам — добавим в индекс (TTL чтобы не пухло)
        await self.r.sadd(key, str(int(ph)))
        await self.r.expire(key, 14 * 24 * 3600)
        return False

    async def _message_dhash(self, m: Message) -> Optional[int]:
        file_id: Optional[str] = None
        # возьмём самое крупное фото
        if m.photo:
            p: PhotoSize = max(m.photo, key=lambda x: x.file_size or 0)
            file_id = p.file_id
        elif m.document and (m.document.mime_type or "").startswith("image/"):
            file_id = m.document.file_id
        if not file_id:
            return None

        f = await self.bot.get_file(file_id)
        buf = io.BytesIO()
        await self.bot.download(f, destination=buf)
        buf.seek(0)
        img = Image.open(buf).convert("L")  # grayscale
        # классический dHash: 9x8 -> соседние сравнения по ширине
        img = ImageOps.exif_transpose(img)
        img = img.resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(img.getdata())
        bits = 0
        for row in range(8):
            for col in range(8):
                left = pixels[row * 9 + col]
                right = pixels[row * 9 + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
        return bits

    # ---------- Online NB in Redis -------------------------------------------

    async def _nb_predict(self, text: str) -> float:
        toks = tokenize(text)
        feats = hashed_features(toks, n_bits=self.nb.n_bits)

        # загрузим метаданные
        meta = await self.r.hgetall(self.nb.meta_key)
        spam_docs = int(meta.get(b"spam_docs", b"0"))
        ham_docs = int(meta.get(b"ham_docs", b"0"))
        total_docs = max(1, spam_docs + ham_docs)

        log_prior_spam = math.log((spam_docs + 1) / (total_docs + 2))
        log_prior_ham = math.log((ham_docs + 1) / (total_docs + 2))

        # суммируем по фичам
        spam_loglik = log_prior_spam
        ham_loglik = log_prior_ham

        # Получаем веса через Redis hash (hget «на лету»)
        # Ключи с индексами фич — строки
        for idx, cnt in feats.items():
            sval = await self.r.hget(self.nb.spam_counts_key, str(idx))
            hval = await self.r.hget(self.nb.ham_counts_key, str(idx))
            s = int(sval or 0)
            h = int(hval or 0)
            # частоты с Лапласовым сглаживанием
            s_prob = (s + self.nb.alpha) / (spam_docs + self.nb.alpha * self.nb.vocab_size + 1e-9)
            h_prob = (h + self.nb.alpha) / (ham_docs + self.nb.alpha * self.nb.vocab_size + 1e-9)
            # умножение вероятностей -> сложение логов
            spam_loglik += cnt * math.log(s_prob + 1e-12)
            ham_loglik += cnt * math.log(h_prob + 1e-12)

        # logit -> prob
        mmax = max(spam_loglik, ham_loglik)
        s = math.exp(spam_loglik - mmax)
        h = math.exp(ham_loglik - mmax)
        return s / (s + h + 1e-12)

    async def _nb_partial_fit(self, text: str, label_spam: int) -> None:
        """
        label_spam: 1 (spam) | 0 (ham)
        """
        toks = tokenize(normalize_text(text))
        feats = hashed_features(toks, n_bits=self.nb.n_bits)

        pipe = self.r.pipeline()
        # обновляем метаданные
        if label_spam:
            pipe.hincrby(self.nb.meta_key, "spam_docs", 1)
        else:
            pipe.hincrby(self.nb.meta_key, "ham_docs", 1)

        # инкременты по фичам
        key = self.nb.spam_counts_key if label_spam else self.nb.ham_counts_key
        for idx, cnt in feats.items():
            pipe.hincrby(key, str(idx), int(cnt))

        # храним месяц
        pipe.expire(self.nb.meta_key, 30 * 24 * 3600)
        pipe.expire(self.nb.spam_counts_key, 30 * 24 * 3600)
        pipe.expire(self.nb.ham_counts_key, 30 * 24 * 3600)
        await pipe.execute()

# --- helpers -----------------------------------------------------------------

import contextlib  # keep at end to avoid circular import in some setups

def hamming64(a: int, b: int) -> int:
    return (a ^ b).bit_count()