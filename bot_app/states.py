from aiogram.fsm.state import State, StatesGroup


class AddCarStates(StatesGroup):
    title = State()
    brand = State()
    model = State()
    vin_or_plate = State()
    vin_photo = State()
    description = State()
    photo = State()


class AddDefectPhotoStates(StatesGroup):
    photo = State()
    comment = State()


class AddExpenseStates(StatesGroup):
    car = State()
    amount = State()
    currency = State()
    category = State()
    description = State()
    comment = State()
    receipt = State()


class QuickExpenseStates(StatesGroup):
    car = State()
    currency = State()
    category = State()


class EditCarStates(StatesGroup):
    title = State()
    brand = State()
    model = State()
    vin_or_plate = State()
    vin_photo = State()
    description = State()
