# ======================================================================================
# File: bot/handlers/public/onboarding_handler.py
# Version: "Distinguished Engineer" — Aug 16, 2025
# Description:
#   Lightweight onboarding:
#     • Показывает правила при первом /start
#     • Кнопка "Согласен ✅" — помечает пользователя в Redis на 365 дней
#     • Админы пропускаются автоматически
# ======================================================================================

from __future__ import annotations

import time

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config.settings import settings

router = Router(name="onboarding_public")

ONBOARD_TTL = 365 * 24 * 3600  # 1 год


def _is_admin(uid: int | None) -> bool:
    return bool(uid and uid in (settings.admin_ids or []))


def _kb_agree() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Согласен ✅", callback_data="onb:agree")],
            [InlineKeyboardButton(text="Правила⚖️", url="https://t.me/")],  # при желании укажи реальную ссылку
        ]
    )


def _rules_text() -> str:
    return (
        "<b>Добро пожаловать!</b>\n"
        "Перед использованием подтвердите согласие с правилами:\n"
        "• Не публиковать спам/скам/реферальные свалки\n"
        "• Уважать других участников\n"
        "• Понимать риски рынка криптовалют\n\n"
        "Нажимая «Согласен», вы принимаете правила."
    )


@router.message(CommandStart())
async def maybe_onboard(message: Message, deps) -> None:
    uid = message.from_user.id if message.from_user else 0
    if _is_admin(uid):
        return  # админам не мешаем — их /start обработает start_handler

    r = deps.redis  # type: ignore[attr-defined]
    key = f"user:onboarded:{uid}"
    try:
        ok = await r.exists(key)
    except Exception:
        ok = 1  # если Redis недоступен — не блокируем

    if ok:
        return  # уже прошёл — дальше поймает start_handler

    # показать правила
    await message.answer(_rules_text(), parse_mode="HTML", reply_markup=_kb_agree())


@router.callback_query(F.data == "onb:agree")
async def cb_agree(call: CallbackQuery, deps) -> None:
    uid = call.from_user.id if call.from_user else 0
    r = deps.redis  # type: ignore[attr-defined]
    key = f"user:onboarded:{uid}"
    try:
        await r.setex(key, ONBOARD_TTL, int(time.time()))
    except Exception:
        pass

    await call.answer("Спасибо! Онбординг завершён.")
    # аккуратно заменяем сообщение
    try:
        await call.message.edit_text("Готово ✅ Вы можете открыть /menu.", parse_mode="HTML")  # type: ignore[union-attr]
    except Exception:
        pass
