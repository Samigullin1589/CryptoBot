# =============================================================================
# Файл: bot/handlers/threats/threat_handler.py
# Версия: PRODUCTION 2025 — совместимо со старыми и новыми кнопками
#
# Что делает:
#   • Поддерживает ВСЕ форматы callback_data для карточек угроз:
#       - "pardon:<user_id>:<chat_id>"
#       - "ban:<user_id>:<chat_id>"
#       - "threat_action:pardon:<user_id>:<chat_id>"
#       - "threat_action:ban:<user_id>:<chat_id>"
#       - "threat:pardon:<user_id>:<chat_id>"
#   • Если chat_id не удаётся вытащить из callback_data, парсит его из
#     текста карточки (строки вида "ID: 123" и "Чат ID: -100...").
#   • Безопасно делает unban: ловит TelegramBadRequest ("method is available
#     for supergroup and channel chats only") и другие исключения — карточка
#     не падает, пользователю показывается мягкий успех.
#   • Совместимо с текущей зависимостью Deps и moderation_service.ban_user.
# =============================================================================

from __future__ import annotations

import contextlib
import logging
import re
from typing import Optional, Tuple

from aiogram import F, Router, types
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
)
from aiogram.filters import Command
from aiogram.types import Message

from bot.utils.dependencies import Deps

# --- необязательная поддержка новой фабрики (если вы её используете где-то ещё) ---
try:
    from bot.keyboards.callback_factories import ThreatCallback  # noqa: F401
    _HAS_THREAT_FACTORY = True
except Exception:  # фабрики может не быть — это ок
    _HAS_THREAT_FACTORY = False

# Экспортируем под разными именами на случай разных импортов в проекте
threats_router = Router()
threat_router = threats_router
router = threats_router

logger = logging.getLogger(__name__)

# ------------------------------- ВСПОМОГАТЕЛЬНЫЕ -------------------------------

def _parse_ids_from_callback_data(data: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """
    Поддерживаем форматы:
      - "threat_action:pardon:<user_id>:<chat_id>"
      - "threat_action:ban:<user_id>:<chat_id>"
      - "threat:pardon:<user_id>:<chat_id>"
      - "threat:ban:<user_id>:<chat_id>"
      - "pardon:<user_id>:<chat_id>"
      - "ban:<user_id>:<chat_id>"
    Возвращает (user_id, chat_id) или (None, None).
    """
    if not data:
        return None, None

    parts = data.split(":")
    try:
        if len(parts) >= 4 and parts[0] in ("threat_action", "threat"):
            # threat_action:<action>:<user_id>:<chat_id>
            return int(parts[2]), int(parts[3])
        if len(parts) >= 3 and parts[0] in ("pardon", "ban"):
            # pardon:<user_id>:<chat_id>
            return int(parts[1]), int(parts[2])
    except Exception:
        return None, None
    return None, None


_ID_RE = re.compile(r"\bID:\s*(\d+)")
_CHAT_ID_RE = re.compile(r"Чат\s+ID:\s*([\-]?\d+)", re.IGNORECASE)


def _parse_ids_from_card_text(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Парсинг из текста карточки (пример):
      ID: 161465196
      Чат ID: -1002408729915
    """
    user_id = None
    chat_id = None
    if not text:
        return None, None

    m = _ID_RE.search(text)
    if m:
        with contextlib.suppress(Exception):
            user_id = int(m.group(1))

    m = _CHAT_ID_RE.search(text)
    if m:
        with contextlib.suppress(Exception):
            chat_id = int(m.group(1))

    return user_id, chat_id


async def _safe_edit_append_html(cb: types.CallbackQuery, append_html: str) -> None:
    """
    Аккуратно дописывает блок к исходному сообщению-уведомлению.
    Если редактирование невозможно — покажем toast, а ошибку залогируем.
    """
    msg = getattr(cb, "message", None)
    if msg is None:
        with contextlib.suppress(Exception):
            await cb.answer(append_html.replace("<b>", "").replace("</b>", ""), show_alert=False)
        return

    base_html = (getattr(msg, "html_text", None) or getattr(msg, "text", None) or "").strip()
    new_html = f"{base_html}\n\n— — —\n{append_html}".strip()

    try:
        await msg.edit_text(new_html, reply_markup=None, parse_mode="HTML")
    except TelegramBadRequest as e:
        logger.warning("Edit threat card failed: %s", e)
        with contextlib.suppress(Exception):
            await cb.answer(append_html.replace("<b>", "").replace("</b>", ""), show_alert=False)
    except Exception as e:
        logger.error("Unexpected error while editing threat card: %s", e, exc_info=True)
        with contextlib.suppress(Exception):
            await cb.answer(append_html.replace("<b>", "").replace("</b>", ""), show_alert=False)


def _choose_ids_for_action(
    cq: types.CallbackQuery,
    need_user: bool = True,
    need_chat: bool = True,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Выбирает user_id и chat_id:
    1) из callback_data,
    2) из текста карточки,
    3) (chat) из cq.message.chat.id как последний шанс (может быть личка).
    """
    from_cb_user, from_cb_chat = _parse_ids_from_callback_data(cq.data)

    user_id = from_cb_user
    chat_id = from_cb_chat

    card_text = (getattr(cq.message, "html_text", None) or getattr(cq.message, "text", None) or "")

    if need_user and user_id is None:
        user_id, _ = _parse_ids_from_card_text(card_text)

    if need_chat and chat_id is None:
        _, chat_id = _parse_ids_from_card_text(card_text)

    if need_chat and chat_id is None and cq.message:
        # Последний шанс — но это может быть личка админа (unban не сработает).
        chat_id = cq.message.chat.id

    return user_id, chat_id


def _fmt_done(text: str) -> str:
    return f"✅ <b>Действие выполнено:</b> {text}"


# ------------------------ ОБРАБОТЧИКИ КОЛЛБЭКОВ (СТАРЫЕ) ------------------------

@threats_router.callback_query(F.data.startswith("pardon"))
async def cb_pardon(cq: types.CallbackQuery, deps: Deps) -> None:
    """
    Старый формат кнопки «Помиловать».
    """
    with contextlib.suppress(Exception):
        await cq.answer()

    user_id, chat_id = _choose_ids_for_action(cq, need_user=True, need_chat=True)

    # Мягкий успех по умолчанию
    response_text = "Пользователь помилован (или не был забанен)."

    try:
        if chat_id is not None and user_id is not None:
            # Попытка разбанить (будет исключение, если это не супер-группа/канал)
            await cq.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
    except TelegramBadRequest as e:
        # Например: "method is available for supergroup and channel chats only"
        logger.info("pardon_user bad request: %s", e)
    except TelegramForbiddenError as e:
        logger.warning("pardon_user forbidden: %s", e)
    except TelegramAPIError as e:
        logger.warning("pardon_user API error: %s", e)
    except Exception as e:
        logger.error("pardon_user unexpected error: %s", e, exc_info=True)

    await _safe_edit_append_html(cq, _fmt_done(response_text))


@threats_router.callback_query(F.data.startswith("ban"))
async def cb_ban(cq: types.CallbackQuery, deps: Deps) -> None:
    """
    Старый формат кнопки «Забанить».
    """
    with contextlib.suppress(Exception):
        await cq.answer()

    user_id, chat_id = _choose_ids_for_action(cq, need_user=True, need_chat=True)

    if user_id is None or chat_id is None:
        await _safe_edit_append_html(cq, "Не удалось определить пользователя или чат для бана.")
        return

    try:
        txt = await deps.moderation_service.ban_user(
            admin_id=cq.from_user.id,
            target_user_id=user_id,
            target_chat_id=chat_id,
            reason="Бан из карточки угрозы",
        )
        response_text = txt if isinstance(txt, str) else "Пользователь забанен."
    except Exception as e:
        logger.error("Ban from threat card failed: %s", e, exc_info=True)
        response_text = "Ошибка бана: нет прав или уже заблокирован."

    await _safe_edit_append_html(cq, _fmt_done(response_text))


# -------------------- МОСТ ДЛЯ НОВЫХ ПРЕФИКСОВ threat_action:/threat: --------------------

@threats_router.callback_query(F.data.startswith("threat_action:"))
async def cb_threat_action_bridge(cq: types.CallbackQuery, deps: Deps) -> None:
    """
    Совместимость: пробрасываем threat_action:* в соответствующие обработчики.
    """
    action = (cq.data or "").split(":")[1] if (cq.data and ":" in cq.data) else ""
    if action == "pardon":
        await cb_pardon(cq, deps)
    elif action == "ban":
        await cb_ban(cq, deps)
    else:
        with contextlib.suppress(Exception):
            await cq.answer("Неизвестное действие.", show_alert=True)


@threats_router.callback_query(F.data.startswith("threat:"))
async def cb_threat_prefix_bridge(cq: types.CallbackQuery, deps: Deps) -> None:
    """
    Совместимость: пробрасываем threat:* в соответствующие обработчики.
    """
    # threat:action:user_id:chat_id
    parts = (cq.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    if action == "pardon":
        await cb_pardon(cq, deps)
    elif action == "ban":
        await cb_ban(cq, deps)
    else:
        with contextlib.suppress(Exception):
            await cq.answer("Неизвестное действие.", show_alert=True)


# ----------------- (ОПЦИОНАЛЬНО) КОМАНДЫ-ЗАГЛУШКИ ДЛЯ РУЧНОЙ МОДЕРАЦИИ -----------------

@threats_router.message(Command("pardon"))
async def cmd_pardon_stub(message: Message) -> None:
    await message.reply("Эта команда недоступна. Используйте кнопки в карточке угрозы.")


@threats_router.message(Command("ban"))
async def cmd_ban_stub(message: Message) -> None:
    await message.reply("Эта команда недоступна. Используйте кнопки в карточке угрозы.")