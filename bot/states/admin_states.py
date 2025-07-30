# =================================================================================
# Файл: bot/states/admin_states.py (ВЕРСИЯ "ГЕНИЙ 2.0" - ПОЛНАЯ И ОКОНЧАТЕЛЬНАЯ)
# Описание: Состояния для админ-панели, включая управление игрой.
# =================================================================================

from aiogram.fsm.state import State, StatesGroup

class MailingStates(StatesGroup):
    """Состояния для процесса рассылки."""
    entering_message = State()
    confirming_mailing = State()

class GameAdminStates(StatesGroup):
    """Определяет шаги конечного автомата для администрирования игры."""
    # Состояния для процесса изменения баланса
    entering_user_id_for_balance = State()
    entering_balance_amount = State()