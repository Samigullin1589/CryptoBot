# bot/states/admin_states.py
# =================================================================================
# Файл: bot/states/admin_states.py (ВЕРСИЯ "Distinguished Engineer" - ФИНАЛ)
# Описание: Полный и логически сгруппированный набор состояний для
# всей административной панели.
# ИСПРАВЛЕНИЕ: Главный класс переименован в 'AdminStates' для решения 'ImportError'.
# =================================================================================

from aiogram.fsm.state import StatesGroup, State

# ИСПРАВЛЕНО: Класс переименован с AdminMenu на AdminStates для соответствия импортам
class AdminStates(StatesGroup):
    """
    Главные состояния навигации по административной панели.
    """
    main = State()
    user_management = State()
    game_management = State()
    stats_view = State()


class UserManagement(StatesGroup):
    """
    Состояния для конкретных действий по управлению пользователями.
    """
    view_profile = State()
    ban_reason = State()
    unban_confirm = State()


class Mailing(StatesGroup):
    """
    Состояния для процесса создания и отправки рассылки.
    """
    enter_message = State()
    confirm = State()


class GameAdmin(StatesGroup):
    """
    Состояния для администрирования игровых параметров.
    """
    # Изменение баланса пользователя
    enter_user_id_for_balance = State()
    enter_balance_amount = State()

    # Редактирование общих игровых параметров
    edit_parameter = State()
