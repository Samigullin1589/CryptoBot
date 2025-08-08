# =================================================================================
# Файл: bot/states/info_states.py (ВЕРСИЯ "Distinguished Engineer" - ПОЛНАЯ)
# Описание: Определяет состояния (FSM) для всех информационных сценариев.
# =================================================================================

from aiogram.fsm.state import State, StatesGroup

class PriceInquiryState(StatesGroup):
    """Состояния для сценария запроса цены криптовалюты."""
    waiting_for_ticker = State()

class CalculatorState(StatesGroup):
    """Состояния для калькулятора доходности."""
    waiting_for_hashrate = State()
    waiting_for_power = State()
    waiting_for_cost = State()

class CryptoCenterStates(StatesGroup):
    """Состояния для навигации в Крипто-Центре."""
    main_menu = State()
    airdrop_list = State()
    airdrop_view = State()
    mining_alpha_list = State()
    news_feed = State()
