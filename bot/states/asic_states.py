# ===============================================================
# Файл: bot/states/asic_states.py (НОВЫЙ ФАЙЛ)
# Описание: Состояния FSM для навигации по разделу ASIC.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class AsicExplorerStates(StatesGroup):
    showing_top = State()       # Пользователь просматривает список
    showing_passport = State()  # Пользователь смотрит паспорт устройства
    prompt_electricity_cost = State() # Ожидание ввода стоимости электроэнергии
