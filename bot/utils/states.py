from aiogram.fsm.state import State, StatesGroup

class PriceInquiry(StatesGroup):
    """
    Состояния для процесса запроса цены на "другую монету".
    """
    waiting_for_ticker = State()

class ProfitCalculator(StatesGroup):
    """
    Состояния для калькулятора доходности.
    """
    waiting_for_electricity_cost = State()

# В будущем здесь можно будет добавить состояния для Виртуального Майнинга,
# например, для покупки тарифа на электроэнергию.