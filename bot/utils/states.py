from aiogram.fsm.state import State, StatesGroup

class PriceInquiry(StatesGroup):
    waiting_for_ticker = State()

class ProfitCalculator(StatesGroup):
    waiting_for_electricity_cost = State()