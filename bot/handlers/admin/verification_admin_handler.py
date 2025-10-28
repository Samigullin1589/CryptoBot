# bot/handlers/admin/verification_admin_handler.py
# Версия: 1.0.0 (28.10.2025)
# Описание: Админская панель для управления верификацией пользователей через кнопки

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.settings import settings
from bot.utils.dependencies import Deps

logger = logging.getLogger(__name__)

router = Router(name="verification_admin")


# ====================== FSM Состояния ======================

class VerificationStates(StatesGroup):
    waiting_username = State()
    waiting_deposit_amount = State()


# ====================== Клавиатуры ======================

def get_verification_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    """Главное меню управления верификацией"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Верифицировать пользователя", callback_data=f"verify_user:{user_id}")],
        [InlineKeyboardButton(text="❌ Снять верификацию", callback_data=f"unverify_user:{user_id}")],
        [InlineKeyboardButton(text="📝 Верифицировать паспорт", callback_data=f"verify_passport:{user_id}")],
        [InlineKeyboardButton(text="💰 Установить депозит", callback_data=f"set_deposit:{user_id}")],
        [InlineKeyboardButton(text="« Назад", callback_data="admin_menu")],
    ])


def get_confirm_verification_kb(user_id: int) -> InlineKeyboardMarkup:
    """Подтверждение верификации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, верифицировать", callback_data=f"confirm_verify:{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"verify_menu:{user_id}")
        ]
    ])


def get_confirm_unverify_kb(user_id: int) -> InlineKeyboardMarkup:
    """Подтверждение снятия верификации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, снять", callback_data=f"confirm_unverify:{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"verify_menu:{user_id}")
        ]
    ])


# ====================== Команды ======================

@router.message(Command("verify"))
async def cmd_verify(message: Message, state: FSMContext, deps: Deps):
    """
    /verify @username - открыть панель управления верификацией
    """
    # Проверка прав админа
    if not message.from_user or message.from_user.id not in settings.admin_ids:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    # Проверяем аргументы
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await state.set_state(VerificationStates.waiting_username)
        await message.answer(
            "👤 Введите username или ID пользователя:\n\n"
            "Примеры:\n"
            "• @username\n"
            "• 123456789"
        )
        return
    
    target = args[1].strip().lstrip("@")
    
    # Ищем пользователя
    user_service = deps.user_service
    user = None
    
    if target.isdigit():
        user = await user_service.get_user(int(target))
    else:
        user = await user_service.get_user_by_username(target)
    
    if not user:
        await message.answer(f"❌ Пользователь {target} не найден в базе.")
        return
    
    # Показываем панель управления
    vd = user.verification_data
    status = "✅ Верифицирован" if vd.is_verified else "❌ Не верифицирован"
    passport = "✅ Проверен" if vd.passport_verified else "❌ Не проверен"
    deposit = f"${vd.deposit:,.0f}".replace(",", " ") if vd.deposit > 0 else "Не установлен"
    
    text = (
        f"<b>🔐 Управление верификацией</b>\n\n"
        f"<b>Пользователь:</b> {user.first_name}\n"
        f"<b>Username:</b> @{user.username or 'не указан'}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Текущий статус:</b>\n"
        f"• Верификация: {status}\n"
        f"• Паспорт: {passport}\n"
        f"• Депозит: {deposit}\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(text, reply_markup=get_verification_menu_kb(user.id), parse_mode="HTML")


# ====================== FSM Handlers ======================

@router.message(VerificationStates.waiting_username, F.text)
async def process_username_input(message: Message, state: FSMContext, deps: Deps):
    """Обработка введенного username"""
    target = message.text.strip().lstrip("@")
    
    # Ищем пользователя
    user = None
    if target.isdigit():
        user = await deps.user_service.get_user(int(target))
    else:
        user = await deps.user_service.get_user_by_username(target)
    
    if not user:
        await message.answer(f"❌ Пользователь {target} не найден. Попробуйте снова или /cancel")
        return
    
    await state.clear()
    
    # Показываем панель
    vd = user.verification_data
    status = "✅ Верифицирован" if vd.is_verified else "❌ Не верифицирован"
    passport = "✅ Проверен" if vd.passport_verified else "❌ Не проверен"
    deposit = f"${vd.deposit:,.0f}".replace(",", " ") if vd.deposit > 0 else "Не установлен"
    
    text = (
        f"<b>🔐 Управление верификацией</b>\n\n"
        f"<b>Пользователь:</b> {user.first_name}\n"
        f"<b>Username:</b> @{user.username or 'не указан'}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Текущий статус:</b>\n"
        f"• Верификация: {status}\n"
        f"• Паспорт: {passport}\n"
        f"• Депозит: {deposit}\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(text, reply_markup=get_verification_menu_kb(user.id), parse_mode="HTML")


@router.message(VerificationStates.waiting_deposit_amount, F.text)
async def process_deposit_amount(message: Message, state: FSMContext, deps: Deps):
    """Обработка введенной суммы депозита"""
    data = await state.get_data()
    user_id = data.get("user_id")
    
    if not user_id:
        await state.clear()
        await message.answer("❌ Ошибка: пользователь не найден.")
        return
    
    # Парсим сумму
    try:
        amount_str = message.text.strip().replace(" ", "").replace(",", "")
        amount = float(amount_str)
        
        if amount < 0:
            await message.answer("❌ Сумма не может быть отрицательной. Попробуйте снова:")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (например: 5000):")
        return
    
    # Устанавливаем депозит
    success = await deps.verification_service.update_deposit(user_id, amount)
    
    if success:
        await message.answer(
            f"✅ <b>Депозит установлен!</b>\n\n"
            f"Сумма: <b>${amount:,.0f}</b>".replace(",", " "),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка при установке депозита.")
    
    await state.clear()


# ====================== Callback Handlers ======================

@router.callback_query(F.data.startswith("verify_menu:"))
async def show_verification_menu(callback: CallbackQuery, deps: Deps):
    """Показать меню верификации"""
    user_id = int(callback.data.split(":")[1])
    
    user = await deps.user_service.get_user(user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    vd = user.verification_data
    status = "✅ Верифицирован" if vd.is_verified else "❌ Не верифицирован"
    passport = "✅ Проверен" if vd.passport_verified else "❌ Не проверен"
    deposit = f"${vd.deposit:,.0f}".replace(",", " ") if vd.deposit > 0 else "Не установлен"
    
    text = (
        f"<b>🔐 Управление верификацией</b>\n\n"
        f"<b>Пользователь:</b> {user.first_name}\n"
        f"<b>Username:</b> @{user.username or 'не указан'}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Текущий статус:</b>\n"
        f"• Верификация: {status}\n"
        f"• Паспорт: {passport}\n"
        f"• Депозит: {deposit}\n\n"
        f"Выберите действие:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_verification_menu_kb(user.id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("verify_user:"))
async def ask_confirm_verify(callback: CallbackQuery, deps: Deps):
    """Запрос подтверждения верификации"""
    user_id = int(callback.data.split(":")[1])
    
    user = await deps.user_service.get_user(user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    text = (
        f"<b>⚠️ Подтверждение верификации</b>\n\n"
        f"Вы уверены, что хотите верифицировать пользователя?\n\n"
        f"<b>Пользователь:</b> {user.first_name}\n"
        f"<b>Username:</b> @{user.username or 'не указан'}\n"
        f"<b>ID:</b> <code>{user.id}</code>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_confirm_verification_kb(user.id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_verify:"))
async def confirm_verify(callback: CallbackQuery, deps: Deps):
    """Подтверждение верификации"""
    user_id = int(callback.data.split(":")[1])
    
    # Верифицируем
    success = await deps.verification_service.set_verification_status(
        user_id=user_id,
        is_verified=True,
        passport_verified=True
    )
    
    if success:
        user = await deps.user_service.get_user(user_id)
        await callback.message.edit_text(
            f"✅ <b>Пользователь верифицирован!</b>\n\n"
            f"<b>Пользователь:</b> {user.first_name}\n"
            f"<b>Username:</b> @{user.username or 'не указан'}\n"
            f"<b>ID:</b> <code>{user_id}</code>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Ошибка при верификации.")
    
    await callback.answer()


@router.callback_query(F.data.startswith("unverify_user:"))
async def ask_confirm_unverify(callback: CallbackQuery, deps: Deps):
    """Запрос подтверждения снятия верификации"""
    user_id = int(callback.data.split(":")[1])
    
    user = await deps.user_service.get_user(user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    text = (
        f"<b>⚠️ Подтверждение снятия верификации</b>\n\n"
        f"Вы уверены, что хотите снять верификацию?\n\n"
        f"<b>Пользователь:</b> {user.first_name}\n"
        f"<b>Username:</b> @{user.username or 'не указан'}\n"
        f"<b>ID:</b> <code>{user.id}</code>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_confirm_unverify_kb(user.id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_unverify:"))
async def confirm_unverify(callback: CallbackQuery, deps: Deps):
    """Подтверждение снятия верификации"""
    user_id = int(callback.data.split(":")[1])
    
    # Снимаем верификацию
    success = await deps.verification_service.set_verification_status(
        user_id=user_id,
        is_verified=False,
        passport_verified=False
    )
    
    if success:
        user = await deps.user_service.get_user(user_id)
        await callback.message.edit_text(
            f"✅ <b>Верификация снята!</b>\n\n"
            f"<b>Пользователь:</b> {user.first_name}\n"
            f"<b>Username:</b> @{user.username or 'не указан'}\n"
            f"<b>ID:</b> <code>{user_id}</code>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Ошибка при снятии верификации.")
    
    await callback.answer()


@router.callback_query(F.data.startswith("verify_passport:"))
async def verify_passport_only(callback: CallbackQuery, deps: Deps):
    """Верификация только паспорта (без полной верификации)"""
    user_id = int(callback.data.split(":")[1])
    
    user = await deps.user_service.get_user(user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    # Верифицируем паспорт
    success = await deps.verification_service.set_verification_status(
        user_id=user_id,
        is_verified=user.verification_data.is_verified,  # Сохраняем текущий статус
        passport_verified=True
    )
    
    if success:
        await callback.answer("✅ Паспорт верифицирован!", show_alert=True)
        # Обновляем меню
        await show_verification_menu(callback, deps)
    else:
        await callback.answer("❌ Ошибка при верификации паспорта", show_alert=True)


@router.callback_query(F.data.startswith("set_deposit:"))
async def start_set_deposit(callback: CallbackQuery, state: FSMContext):
    """Начать процесс установки депозита"""
    user_id = int(callback.data.split(":")[1])
    
    await state.set_state(VerificationStates.waiting_deposit_amount)
    await state.update_data(user_id=user_id)
    
    await callback.message.edit_text(
        f"💰 <b>Установка депозита</b>\n\n"
        f"Введите сумму депозита в USD:\n\n"
        f"<i>Например: 5000</i>",
        parse_mode="HTML"
    )
    await callback.answer()