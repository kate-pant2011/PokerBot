from aiogram.fsm.state import StatesGroup, State


class ChipsState(StatesGroup):
    waiting_for_amount = State()
