# =================================================================================
# Файл: bot/states/game_states.py (ВЕРСИЯ "Distinguished Engineer" - УНИФИЦИРОВАННАЯ)
# Описание: Определяет все состояния (FSM) для сценариев внутри игрового модуля.
# ИСПРАВЛЕНИЕ: Добавлено состояние `confirm_purchase` для корректной покупки.
# =================================================================================

from aiogram.fsm.state import State, StatesGroup

class MiningGameStates(StatesGroup):
    """Состояния для навигации в разделе 'Виртуальный Майнинг'."""
    main_menu = State()
    choosing_asic_for_session = State()
    in_market = State()
    in_tariffs = State()
    in_shop = State()
    confirm_purchase = State() # <-- НОВОЕ СОСТОЯНИЕ ДЛЯ ПОДТВЕРЖДЕНИЯ ПОКУПКИ
    confirm_tariff_purchase = State()
    confirm_withdraw = State()