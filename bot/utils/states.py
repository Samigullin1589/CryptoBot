from aiogram.fsm.state import State, StatesGroup

class UserState(StatesGroup):
    # Состояние, когда бот ждет тикер криптовалюты от пользователя
    awaiting_ticker = State()