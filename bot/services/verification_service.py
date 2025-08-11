# =================================================================================
# Файл: bot/services/verification_service.py (НОВЫЙ ФАЙЛ)
# Описание: Сервис для управления данными верификации пользователей.
# Инкапсулирует всю бизнес-логику работы с репутацией.
# =================================================================================
import logging
from typing import Optional

from bot.services.user_service import UserService
from bot.utils.models import User

logger = logging.getLogger(__name__)

class VerificationService:
    def __init__(self, user_service: UserService):
        self.user_service = user_service

    async def get_user_for_verification(self, user_id: int) -> Optional[User]:
        """Получает пользователя для операций верификации."""
        return await self.user_service.get_user(user_id)

    async def set_verification_status(self, user_id: int, is_verified: bool, passport_verified: bool) -> bool:
        """Устанавливает или снимает статус верификации."""
        user = await self.get_user_for_verification(user_id)
        if not user:
            return False
        
        user.verification_data.is_verified = is_verified
        user.verification_data.passport_verified = passport_verified
        
        await self.user_service.save_user(user)
        logger.info(f"Статус верификации для пользователя {user_id} изменен на {is_verified}.")
        return True

    async def update_deposit(self, user_id: int, amount: float) -> bool:
        """Обновляет сумму депозита пользователя."""
        if amount < 0:
            logger.warning(f"Попытка установить отрицательный депозит ({amount}) для пользователя {user_id}.")
            return False
            
        user = await self.get_user_for_verification(user_id)
        if not user:
            return False
            
        user.verification_data.deposit = amount
        await self.user_service.save_user(user)
        logger.info(f"Депозит для пользователя {user_id} обновлен на ${amount:,.2f}.")
        return True

    def format_check_message(self, user: User) -> str:
        """Форматирует сообщение для команды /check на основе данных пользователя."""
        vd = user.verification_data
        
        if vd.is_verified:
            status_header = "✅ <b>ПРОВЕРЕННЫЙ ПОСТАВЩИК</b> ✅"
            passport_status = "✅ Проверен"
            deposit_text = f"${vd.deposit:,.0f}" if vd.deposit > 0 else "Отсутствует"
            warning_text = ""
        else:
            status_header = "⚠️ <b>НЕ ПРОВЕРЕН</b> ⚠️"
            passport_status = "⚠️ Не проверен"
            deposit_text = "Отсутствует"
            warning_text = "\n<i>При переводе предоплаты есть риск потерять денежные средства.</i>"

        username_str = f"@{user.username}" if user.username else "Не указан"

        return (
            f"<b>Бот-куратор</b>\n"
            f"--------------------\n"
            f"<b>Статус:</b>\n{status_header}{warning_text}\n\n"
            f"<b>Пользователь</b>\n"
            f"ID: <code>{user.id}</code>\n"
            f"Имя: {user.first_name}\n"
            f"Username: {username_str}\n\n"
            f"<b>Детали верификации</b>\n"
            f"Страна: {vd.country_code}\n"
            f"Паспорт: {passport_status}\n"
            f"Депозит: {deposit_text}"
        )