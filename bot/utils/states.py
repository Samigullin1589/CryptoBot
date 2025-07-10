from aiogram.fsm.state import State, StatesGroup

class PriceInquiry(StatesGroup):
    """
    Состояния для процесса запроса цены на криптовалюту.
    """
    waiting_for_ticker = State()

class ProfitCalculator(StatesGroup):
    """
    Состояния для многошагового процесса калькулятора доходности.
    """
    waiting_for_electricity_cost = State()
    waiting_for_pool_commission = State()

# --- НОВЫЙ БЛОК ---
class VirtualMining(StatesGroup):
    """
    Состояния для многошаговых действий в игре "Виртуальный Майнинг".
    """
    confirm_tariff_purchase = State() # Для подтверждения покупки тарифа
    confirm_withdraw = State()        # Для подтверждения вывода средств