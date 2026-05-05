from aiogram.fsm.state import StatesGroup, State


class NickState(StatesGroup):
    waiting_for_name = State()