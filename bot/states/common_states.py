# ===============================================================
# Файл: bot/states/crypto_center_states.py (НОВЫЙ ФАЙЛ)
# Описание: Состояния FSM для Крипто-Центра.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class CryptoCenterStates(StatesGroup):
    main_menu = State()
    viewing_guides_menu = State()
    viewing_feed = State()
    viewing_airdrops_list = State()
    viewing_airdrop_details = State()
    viewing_mining_signals = State()
