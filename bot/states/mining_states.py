# ===============================================================
# Файл: bot/states/mining_states.py (НОВЫЙ ФАЙЛ)
# Описание: Определяет и изолирует состояния (FSM) для
# Игры "Виртуальный Майнинг" и Калькулятора доходности.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class MiningGameStates(StatesGroup):
    """
    Состояния для навигации по игре "Виртуальный Майнинг".
    """
    main_menu = State()
    shop = State()
    my_farm = State()
    electricity_menu = State()

class ProfitCalculatorStates(StatesGroup):
    """
    Состояния для пошагового сценария калькулятора доходности.
    """
    waiting_for_currency = State()
    waiting_for_electricity_cost = State()
    waiting_for_asic_selection = State()
    waiting_for_pool_commission = State()
