# ===============================================================
# Файл: bot/states/mining_states.py (ПРОДАКШН-ВЕРСИЯ 2025 - СКОРРЕКТИРОВАННЫЙ)
# Описание: Определяет состояния (FSM) только для Калькулятора доходности.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class CalculatorStates(StatesGroup):
    """
    Состояния для многошагового процесса калькулятора доходности.
    """
    waiting_for_currency = State()
    waiting_for_electricity_cost = State()
    waiting_for_asic_selection = State()
    waiting_for_pool_commission = State()