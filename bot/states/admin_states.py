# ===============================================================
# Файл: bot/states/admin_states.py (НОВЫЙ ФАЙЛ)
# Описание: Введены состояния (FSM) для админ-панели.
# Это позволяет создавать более сложные и управляемые
# сценарии взаимодействия в административном разделе.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    """
    Состояния для навигации по административной панели.
    """
    main_menu = State()  # Основное меню админки
    
    # Сюда можно будет добавлять другие состояния для нового функционала, например:
    # broadcast_message_prompt = State()
    # broadcast_message_confirm = State()
    # view_statistics_period = State()
    # manage_user_find = State()
    # manage_user_profile = State()
