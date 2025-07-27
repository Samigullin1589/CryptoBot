# ===============================================================
# Файл: bot/states/crypto_center_states.py (НОВЫЙ ФАЙЛ)
# Описание: Определяет состояния (FSM) для навигации
# по разделам Крипто-Центра.
# ===============================================================
from aiogram.fsm.state import State, StatesGroup

class CryptoCenterStates(StatesGroup):
    """
    Состояния для сценариев взаимодействия в Крипто-Центре.
    """
    main_menu = State()               # Главное меню Крипто-Центра
    viewing_feed = State()            # Просмотр ленты новостей
    viewing_guides_menu = State()     # Меню выбора гайдов (Airdrops, Mining)
    viewing_airdrops_list = State()   # Просмотр списка Airdrop'ов
    viewing_airdrop_details = State() # Просмотр детальной информации по Airdrop'у
    viewing_mining_signals = State()  # Просмотр майнинг-сигналов
