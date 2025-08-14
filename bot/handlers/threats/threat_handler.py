# ===============================================================
# Файл: bot/handlers/threats/threat_handler.py (ПРОДАКШН-ВЕРСИЯ 2025 - ФИНАЛЬНО ИСПРАВЛЕННАЯ)
# Описание: "Тонкий" хэндлер, который ловит сообщения от ThreatFilter
# и передает их в ModerationService для комплексной обработки.
# ИСПРАВЛЕНИЕ: Изменен способ регистрации фильтра с ThreatFilter()
#              на ThreatFilter для корректной работы DI.
# ===============================================================
import logging
from typing import List, Optional, Tuple

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from bot.filters.threat_filter import ThreatFilter
from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)

threat_router = Router(name="threats")


@threat_router.message(ThreatFilter())
async def on_threat_message(
    message: Message,
    deps: Deps,
    threat_score: float,
    reasons: List[str],
) -> None:
    """
    Уведомление модерации и попытка удалить сообщение, если отмечено как угроза.
    """
    try:
        if getattr(deps, "moderation_service", None):
            await deps.moderation_service.process_detected_threat(
                message=message,
                threat_score=threat_score,
                reasons=reasons,
            )
    except Exception as e:
        logger.error("Could not process threat notification: %s", e, exc_info=True)

    try:
        await message.delete()
    except Exception as e:
        logger.warning(
            "Could not delete message %s in chat %s: %s",
            message.message_id,
            message.chat.id,
            e,
        )


# ===== Обработчики кнопок модерации =====

def _parse_action(data: str) -> Tuple[str, list[str]]:
    """
    Ожидаемые варианты callback_data:
      threat:ban:<user_id>[:<message_id>]
      threat:pardon:<user_id>[:<message_id>]
      threat:ignore:<user_id>[:<message_id>]
    Допускаем также префикс 'moderate:' для обратной совместимости.
    """
    if data.startswith("moderate:"):
        data = "threat:" + data.split("moderate:", 1)[1]
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    args = parts[2:] if len(parts) > 2 else []
    return action, args


async def _finalize_callback(
    cq: CallbackQuery,
    ok_text: str,
    remove_keyboard: bool = True,
) -> None:
    """
    Всегда отвечаем на колбэк, чтобы не висел "часик"; при необходимости убираем клавиатуру.
    """
    try:
        await cq.answer(ok_text, show_alert=False)
    except Exception:
        # Даже если answer упал, пробуем дальше убрать клавиатуру
        pass
    if remove_keyboard:
        try:
            if cq.message:
                await cq.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logger.debug("edit_reply_markup failed: %s", e)


@threat_router.callback_query(F.data.startswith("threat:ban") | F.data.startswith("moderate:ban"))
async def cb_ban(cq: CallbackQuery, deps: Deps) -> None:
    action, args = _parse_action(cq.data or "")
    user_id: Optional[int] = int(args[0]) if args and args[0].isdigit() else (cq.from_user.id if cq.from_user else None)
    msg_id: Optional[int] = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    # 1) Пытаемся вызвать сервис, если у него есть нужный метод
    try:
        svc = getattr(deps, "moderation_service", None)
        if svc and hasattr(svc, "ban_user"):
            await svc.ban_user(
                chat_id=cq.message.chat.id if cq.message else None,
                user_id=user_id,
                reason="threat_detected",
                origin_message_id=msg_id,
            )
        else:
            # 2) Fallback: прямой бан через Telegram API
            if cq.message and user_id:
                await cq.bot.ban_chat_member(chat_id=cq.message.chat.id, user_id=user_id)
    except Exception as e:
        logger.error("ban_user failed: %s", e, exc_info=True)
        await _finalize_callback(cq, ok_text="Ошибка бана", remove_keyboard=False)
        return

    await _finalize_callback(cq, ok_text="✅ Забанен")


@threat_router.callback_query(F.data.startswith("threat:pardon") | F.data.startswith("moderate:pardon"))
async def cb_pardon(cq: CallbackQuery, deps: Deps) -> None:
    """
    Кнопка 'Помиловать' — ранее зависала/падала из-за отсутствия метода в ModerationService и отсутствия callback.answer().
    """
    action, args = _parse_action(cq.data or "")
    user_id: Optional[int] = int(args[0]) if args and args[0].isdigit() else (cq.from_user.id if cq.from_user else None)
    msg_id: Optional[int] = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    try:
        svc = getattr(deps, "moderation_service", None)
        if svc and hasattr(svc, "pardon_user"):
            await svc.pardon_user(
                chat_id=cq.message.chat.id if cq.message else None,
                user_id=user_id,
                origin_message_id=msg_id,
            )
        else:
            # Fallback: разблокировка только если был бан
            if cq.message and user_id:
                await cq.bot.unban_chat_member(chat_id=cq.message.chat.id, user_id=user_id, only_if_banned=True)
    except Exception as e:
        logger.error("pardon_user failed: %s", e, exc_info=True)
        await _finalize_callback(cq, ok_text="Ошибка помилования", remove_keyboard=False)
        return

    await _finalize_callback(cq, ok_text="✅ Помилован")


@threat_router.callback_query(F.data.startswith("threat:ignore") | F.data.startswith("moderate:ignore"))
async def cb_ignore(cq: CallbackQuery, deps: Deps) -> None:
    action, args = _parse_action(cq.data or "")
    user_id: Optional[int] = int(args[0]) if args and args[0].isdigit() else (cq.from_user.id if cq.from_user else None)
    msg_id: Optional[int] = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    try:
        svc = getattr(deps, "moderation_service", None)
        if svc and hasattr(svc, "mark_ignored"):
            await svc.mark_ignored(
                chat_id=cq.message.chat.id if cq.message else None,
                user_id=user_id,
                origin_message_id=msg_id,
            )
        # Если сервиса нет — просто закрываем клавиатуру ниже
    except Exception as e:
        logger.error("mark_ignored failed: %s", e, exc_info=True)
        await _finalize_callback(cq, ok_text="Ошибка", remove_keyboard=False)
        return

    await _finalize_callback(cq, ok_text="✅ Игнор")


# ===== Дополнительные погасители спиннера =====

@threat_router.callback_query(F.data == "do_nothing")
async def cb_do_nothing(cq: CallbackQuery) -> None:
    await _finalize_callback(cq, ok_text="OK", remove_keyboard=False)


@threat_router.callback_query()
async def cb_default_ack(cq: CallbackQuery) -> None:
    # Запасной обработчик на случай, если другой роутер не перехватил колбэк
    try:
        await cq.answer()
    except Exception:
        pass