# ===============================================================
# Файл: bot/states/mining_states.py (ПРОДАКШН-ВЕРСИЯ 2025)
# Описание: Определяет состояния (FSM) для игры "Виртуальный
# Майнинг" и для Калькулятора доходности.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class MiningGameStates(StatesGroup):
    """
    Состояния для многошаговых действий в игре "Виртуальный Майнинг".
    """
    confirm_tariff_purchase = State()
    confirm_withdraw = State()

class CalculatorStates(StatesGroup):
    """
    Состояния для многошагового процесса калькулятора доходности.
    """
    waiting_for_currency = State()
    waiting_for_electricity_cost = State()
    waiting_for_asic_selection = State()
    waiting_for_pool_commission = State()
