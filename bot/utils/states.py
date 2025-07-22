# ===============================================================
# Файл: bot/utils/states.py (ОБЪЕДИНЕННАЯ АЛЬФА-ВЕРСИЯ)
# Описание: Сохранены все твои состояния и добавлено новое
# для выбора ASIC в калькуляторе.
# ===============================================================
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
    # --- НОВОЕ: Добавлено состояние для выбора ASIC ---
    waiting_for_asic_selection = State()
    # -------------------------------------------------

class VirtualMining(StatesGroup):
    """
    Состояния для многошаговых действий в игре "Виртуальный Майнинг".
    """
    confirm_tariff_purchase = State() # Для подтверждения покупки тарифа
    confirm_withdraw = State()      # Для подтверждения вывода средств
