# =================================================================================
# Файл: bot/states/game_states.py (ВЕРСИЯ "Distinguished Engineer" - НОВЫЙ)
# Описание: Определяет состояния (FSM) для сценариев внутри игрового модуля.
# =================================================================================

from aiogram.fsm.state import State, StatesGroup

class MiningGameStates(StatesGroup):
    """Состояния для навигации в разделе 'Виртуальный Майнинг'."""
    main_menu = State()
    choosing_asic_for_session = State()
    in_market = State()
    in_tariffs = State()

