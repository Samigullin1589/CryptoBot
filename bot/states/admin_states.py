# ===============================================================
# Файл: bot/states/admin_states.py (НОВЫЙ ФАЙЛ)
# Описание: Состояния FSM для админ-панели.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    main_menu = State()
    stats_menu = State()
    system_menu = State()