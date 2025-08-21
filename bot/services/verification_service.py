# =================================================================================
# Файл: bot/services/verification_service.py
# Версия: "Distinguished Engineer" — ПРОДАКШН-СБОРКА (Aug 21, 2025)
# Описание: Сервис для управления данными верификации пользователей.
# Инкапсулирует всю бизнес-логику работы с репутацией и статусами.
# =================================================================================

from typing import Optional

from loguru import logger

from bot.services.user_service import UserService
from bot.utils.models import User


class VerificationService:
    """
    Сервис-фасад для управления верификацией пользователей.
    Предоставляет методы для изменения статуса верификации, депозита
    и форматирования итогового сообщения для пользователя.
    """

    def __init__(self, user_service: UserService):
        """
        Инициализирует сервис с зависимостью от UserService.
        :param user_service: Сервис для управления данными пользователей.
        """
        self.user_service = user_service
        logger.info("Сервис VerificationService инициализирован.")

    async def set_verification_status(
        self, user_id: int, is_verified: bool, passport_verified: bool
    ) -> bool:
        """
        Устанавливает или снимает статус верификации для пользователя.
        Все изменения атомарно сохраняются через UserService.

        :param user_id: ID пользователя.
        :param is_verified: Основной статус верификации.
        :param passport_verified: Статус проверки паспорта.
        :return: True в случае успеха, False если пользователь не найден.
        """
        user = await self.user_service.get_user(user_id)
        if not user:
            logger.error(f"Попытка изменить статус верификации для несуществующего пользователя {user_id}.")
            return False
        
        user.verification_data.is_verified = is_verified
        user.verification_data.passport_verified = passport_verified
        
        await self.user_service.save_user(user)
        logger.info(f"Статус верификации для {user_id} изменен на: is_verified={is_verified}.")
        return True

    async def update_deposit(self, user_id: int, amount: float) -> bool:
        """
        Обновляет сумму депозита пользователя.

        :param user_id: ID пользователя.
        :param amount: Новая сумма депозита (должна быть неотрицательной).
        :return: True в случае успеха, False если пользователь не найден или сумма некорректна.
        """
        if amount < 0:
            logger.warning(f"Попытка установить отрицательный депозит ({amount}) для {user_id}.")
            return False
            
        user = await self.user_service.get_user(user_id)
        if not user:
            logger.error(f"Попытка обновить депозит для несуществующего пользователя {user_id}.")
            return False
            
        user.verification_data.deposit = amount
        await self.user_service.save_user(user)
        logger.info(f"Депозит для {user_id} обновлен на ${amount:,.2f}.")
        return True

    def format_check_message(self, user: User) -> str:
        """
        Форматирует итоговое сообщение о статусе верификации пользователя
        для команды /check.

        :param user: Объект пользователя.
        :return: Готовая HTML-строка для отправки в Telegram.
        """
        vd = user.verification_data
        
        header = "✅ <b>ПРОВЕРЕННЫЙ ПОСТАВЩИК</b> ✅" if vd.is_verified else "⚠️ <b>НЕ ПРОВЕРЕН</b> ⚠️"
        passport_status = "✅ Проверен" if vd.passport_verified else "⚠️ Не проверен"
        deposit_text = f"${vd.deposit:,.0f}" if vd.deposit > 0 else "Отсутствует"
        warning = "\nПри переводе предоплаты есть риск потерять денежные средства." if not vd.is_verified else ""

        return (
            f"{header}{warning}\n\n"
            f"<b>Пользователь:</b> @{user.username or user.id}\n"
            f"<b>Имя:</b> {user.first_name}\n"
            f"<b>ID:</b> <code>{user.id}</code>\n\n"
            f"<b>Паспорт:</b> {passport_status}\n"
            f"<b>Депозит:</b> {deposit_text}"
        )