# =================================================================================
# Файл: bot/states/game_states.py (ВЕРСЯ "Distinguished Engineer" - УНИФИЦИРОВАННАЯ)
# Описание: Определяет все состояния (FSM) для сценариев внутри игрового модуля.
# ИСПРАВЛЕНИЕ: Добавлено недостающее состояние `in_shop`.
# =================================================================================

from aiogram.fsm.state import State, StatesGroup

class MiningGameStates(StatesGroup):
    """Состояния для навигации в разделе 'Виртуальный Майнинг'."""
    main_menu = State()
    choosing_asic_for_session = State()
    in_market = State()
    in_tariffs = State()
    in_shop = State()
    confirm_tariff_purchase = State()
    confirm_withdraw = State()