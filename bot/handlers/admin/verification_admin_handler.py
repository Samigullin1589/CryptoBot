# =================================================================================
# Файл: bot/handlers/admin/verification_admin_handler.py (НОВЫЙ ФАЙЛ)
# Описание: Обработчики для административных команд верификации.
# =================================================================================
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from bot.utils.dependencies import Deps
from bot.utils.user_helpers import extract_target_user
from bot.filters.access_filters import PrivilegeFilter, UserRole

router = Router(name="verification_admin_router")
# Применяем фильтр ко всему роутеру, чтобы только админы могли использовать эти команды
router.message.filter(PrivilegeFilter(min_role=UserRole.ADMIN))
logger = logging.getLogger(__name__)

@router.message(Command("verif"))
async def handle_verif_command(message: Message, deps: Deps):
    """Команда для установки статуса верификации пользователю."""
    target_user = await extract_target_user(message, deps.user_service)
    if not target_user:
        await message.reply("⚠️ Не удалось найти пользователя. Используйте команду в ответ на сообщение или укажите ID.")
        return
    
    success = await deps.verification_service.set_verification_status(target_user.id, is_verified=True, passport_verified=True)
    if success:
        await message.reply(f"✅ Статус «ПРОВЕРЕННЫЙ ПОСТАВЩИК» успешно установлен для пользователя {target_user.id}.")
    else:
        await message.reply("❌ Произошла ошибка при установке статуса.")

@router.message(Command("verifOff"))
async def handle_verif_off_command(message: Message, deps: Deps):
    """Команда для снятия статуса верификации с пользователя."""
    target_user = await extract_target_user(message, deps.user_service)
    if not target_user:
        await message.reply("⚠️ Не удалось найти пользователя. Используйте команду в ответ на сообщение или укажите ID.")
        return
        
    success = await deps.verification_service.set_verification_status(target_user.id, is_verified=False, passport_verified=False)
    if success:
        await message.reply(f"✅ Статус верификации успешно снят с пользователя {target_user.id}.")
    else:
        await message.reply("❌ Произошла ошибка при снятии статуса.")

@router.message(Command("deposit"))
async def handle_deposit_command(message: Message, deps: Deps):
    """Команда для установки или обновления депозита пользователя."""
    target_user = await extract_target_user(message, deps.user_service)
    if not target_user:
        await message.reply("⚠️ Не удалось найти пользователя. Используйте команду в ответ на сообщение или укажите ID.")
        return

    args = message.text.split()
    # Ищем сумму депозита в аргументах
    amount_arg = next((arg for arg in args if arg.isdigit()), None)
    
    if not amount_arg:
        await message.reply("⚠️ Укажите сумму депозита. Пример: `/deposit 1000` или `/deposit @username 1000`.")
        return

    try:
        amount = float(amount_arg)
        if amount < 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.reply("❌ Сумма депозита должна быть положительным числом.")
        return
    
    success = await deps.verification_service.update_deposit(target_user.id, amount)
    if success:
        await message.reply(f"✅ Депозит для пользователя {target_user.id} установлен в размере ${amount:,.2f}.")
    else:
        await message.reply("❌ Произошла ошибка при обновлении депозита.")
