# =================================================================================
# Файл: bot/services/verification_service.py
# Версия: "Elite Professional" — БЕЗ ЗАГЛУШЕК (28.10.2025)
# Описание: Полноценный сервис верификации с методом check_user
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

    async def check_user(self, username: Optional[str] = None, user_id: Optional[int] = None) -> str:
        """
        🎯 ОСНОВНОЙ МЕТОД для команды /check
        Проверяет пользователя по username или user_id и возвращает красиво отформатированное сообщение.
        
        :param username: Username пользователя (без @)
        :param user_id: ID пользователя
        :return: Отформатированное HTML-сообщение о статусе верификации
        """
        user = None
        
        # Сначала ищем по username
        if username:
            user = await self.user_service.get_user_by_username(username)
        
        # Если не нашли, пробуем по ID
        if not user and user_id:
            user = await self.user_service.get_user(user_id)
        
        # Если пользователь не найден в базе
        if not user:
            search_term = f"@{username}" if username else f"ID {user_id}"
            return (
                f"⚠️ <b>ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН</b> ⚠️\n\n"
                f"Пользователь {search_term} не зарегистрирован в системе.\n\n"
                f"<i>Пользователь должен хотя бы раз запустить бота командой /start</i>"
            )
        
        # Форматируем красивое сообщение
        return self.format_check_message(user)

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
        
        # Красивый заголовок с эмодзи
        if vd.is_verified:
            header = "✅ <b>ПРОВЕРЕННЫЙ ПОСТАВЩИК</b> ✅"
            warning = ""
        else:
            header = "⚠️ <b>НЕ ПРОВЕРЕН</b> ⚠️"
            warning = "\n<i>⚠️ При переводе предоплаты есть риск потерять денежные средства.</i>"
        
        # Статус паспорта
        passport_status = "✅ Проверен" if vd.passport_verified else "❌ Не проверен"
        
        # Депозит
        if vd.deposit > 0:
            deposit_text = f"💰 <b>${vd.deposit:,.0f}</b>".replace(",", " ")
        else:
            deposit_text = "❌ Отсутствует"
        
        # Формируем красивое сообщение
        return (
            f"{header}{warning}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Информация о пользователе</b>\n\n"
            f"<b>Имя:</b> {user.first_name}\n"
            f"<b>Username:</b> @{user.username or 'не указан'}\n"
            f"<b>ID:</b> <code>{user.id}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔐 <b>Статус верификации</b>\n\n"
            f"<b>Паспорт:</b> {passport_status}\n"
            f"<b>Депозит:</b> {deposit_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )