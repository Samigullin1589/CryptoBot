# bot/services/verification_service.py
# Дата обновления: 21.08.25
# Версия: 2.0.0
# Описание: Сервис для управления данными верификации пользователей.
# Инкапсулирует всю бизнес-логику работы с репутацией и статусами.

from typing import Optional

from loguru import logger

from bot.services.user_service import UserService
from bot.utils.models import User, VerificationDetails


class VerificationService:
    """
    Сервис-фасад для управления верификацией пользователей.
    Предоставляет методы для изменения статуса верификации, депозита
    и получения структурированных данных для отображения.
    """

    def __init__(self, user_service: UserService):
        """
        Инициализирует сервис с зависимостью от UserService.

        :param user_service: Сервис для управления данными пользователей.
        """
        self.user_service = user_service
        logger.info("Сервис VerificationService инициализирован.")

    async def get_user_for_verification(self, user_id: int) -> Optional[User]:
        """
        Получает пользователя для операций верификации.
        Является удобной оберткой над user_service.get_user.
        """
        return await self.user_service.get_user(user_id)

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
        user = await self.get_user_for_verification(user_id)
        if not user:
            logger.error(f"Попытка изменить статус верификации для несуществующего пользователя {user_id}.")
            return False
        
        # Обновляем данные в Pydantic модели
        user.verification_data.is_verified = is_verified
        user.verification_data.passport_verified = passport_verified
        
        # Сохраняем обновленный объект пользователя
        await self.user_service.save_user(user)
        logger.info(f"Статус верификации для пользователя {user_id} изменен на: is_verified={is_verified}, passport_verified={passport_verified}.")
        return True

    async def update_deposit(self, user_id: int, amount: float) -> bool:
        """
        Обновляет сумму депозита пользователя.

        :param user_id: ID пользователя.
        :param amount: Новая сумма депозита (должна быть неотрицательной).
        :return: True в случае успеха, False если пользователь не найден или сумма некорректна.
        """
        if amount < 0:
            logger.warning(f"Попытка установить отрицательный депозит ({amount}) для пользователя {user_id}.")
            return False
            
        user = await self.get_user_for_verification(user_id)
        if not user:
            logger.error(f"Попытка обновить депозит для несуществующего пользователя {user_id}.")
            return False
            
        user.verification_data.deposit = amount
        await self.user_service.save_user(user)
        logger.info(f"Депозит для пользователя {user_id} обновлен на ${amount:,.2f}.")
        return True

    def get_verification_details(self, user: User) -> VerificationDetails:
        """
        Формирует структурированные данные для отображения статуса верификации.
        Возвращает Pydantic-модель вместо готового HTML-сообщения.

        :param user: Объект пользователя.
        :return: Модель VerificationDetails с подготовленными для вывода данными.
        """
        vd = user.verification_data
        
        if vd.is_verified:
            status_header = "✅ ПРОВЕРЕННЫЙ ПОСТАВЩИК ✅"
            passport_status = "✅ Проверен"
            deposit_text = f"${vd.deposit:,.0f}" if vd.deposit > 0 else "Отсутствует"
            warning_text = ""
        else:
            status_header = "⚠️ НЕ ПРОВЕРЕН ⚠️"
            passport_status = "⚠️ Не проверен"
            deposit_text = "Отсутствует"
            warning_text = "При переводе предоплаты есть риск потерять денежные средства."

        return VerificationDetails(
            status_header=status_header,
            warning_text=warning_text,
            user_id=user.id,
            username=user.username or "Не указан",
            first_name=user.first_name,
            country_code=vd.country_code or "Не указана",
            passport_status=passport_status,
            deposit_text=deposit_text
        )