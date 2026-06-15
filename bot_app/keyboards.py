from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


ADD_CAR = "➕ Добавить заказ"
LIST_CARS = "📋 Список заказов"
ACTIVE_ORDERS = "🟢 Активные заказы"
ADD_EXPENSE = "💸 Добавить расход"
SHOW_EXPENSES = "📊 Посмотреть расходы"
MY_EXPENSES = "🧾 Мои последние расходы"
TOTALS = "📈 Итоги по заказам"
ARCHIVE = "🗄 Архив"
EXPORT = "📤 Выгрузка"
HELP = "❓ Помощь"
SKIP = "Пропустить"
DONE = "Готово"
CANCEL = "Отмена"

REPAIR_STAGES = [
    ("accepted", "Принят в работу"),
    ("defect", "Дефектовка с фото"),
    ("waiting_parts", "Ожидание деталей"),
    ("body_work", "Кузовные работы"),
    ("paint_assembly", "Подготовка/покраска/сборка"),
    ("ready", "Готов к выдаче"),
    ("done", "Завершен"),
]


def employee_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD_EXPENSE), KeyboardButton(text=ACTIVE_ORDERS)],
            [KeyboardButton(text=MY_EXPENSES), KeyboardButton(text=HELP)],
        ],
        resize_keyboard=True,
    )


def manager_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD_CAR), KeyboardButton(text=LIST_CARS)],
            [KeyboardButton(text=ADD_EXPENSE), KeyboardButton(text=SHOW_EXPENSES)],
            [KeyboardButton(text=TOTALS), KeyboardButton(text=ARCHIVE)],
            [KeyboardButton(text=EXPORT), KeyboardButton(text=HELP)],
        ],
        resize_keyboard=True,
    )


def main_menu(is_manager: bool = True) -> ReplyKeyboardMarkup:
    return manager_menu() if is_manager else employee_menu()


def skip_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=SKIP), KeyboardButton(text=CANCEL)]], resize_keyboard=True)


def photo_collection_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=DONE), KeyboardButton(text=SKIP), KeyboardButton(text=CANCEL)]], resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=CANCEL)]], resize_keyboard=True)


def cars_inline(cars: list[dict], prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    for car in cars:
        label = car["title"]
        if car.get("make_model"):
            label = f"{label} ({car['make_model']})"
        buttons.append([InlineKeyboardButton(text=label[:64], callback_data=f"{prefix}:{car['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cars_page_inline(cars: list[dict], status_value: str, page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    total_pages = max((len(cars) + page_size - 1) // page_size, 1)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    buttons = []
    for car in cars[start:start + page_size]:
        label = f"#{car['id']} {car['title']}"
        if car.get("make_model"):
            label = f"{label} ({car['make_model']})"
        if car.get("status_display"):
            label = f"{label} - {car['status_display']}"
        buttons.append([InlineKeyboardButton(text=label[:64], callback_data=f"car_detail:{car['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Назад", callback_data=f"cars_page:{status_value}:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="cars_page_noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="Вперёд", callback_data=f"cars_page:{status_value}:{page + 1}"))
    buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def categories_inline(categories: list[dict], prefix: str = "category") -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=category["name"], callback_data=f"{prefix}:{category['id']}")] for category in categories]
    if not any(category["name"].lower() == "прочее" for category in categories):
        buttons.append([InlineKeyboardButton(text="Прочее", callback_data=f"{prefix}_name:Прочее")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def currency_inline(prefix: str = "currency") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="BYN", callback_data=f"{prefix}:BYN")],
            [InlineKeyboardButton(text="USD", callback_data=f"{prefix}:USD")],
        ]
    )


def status_filter_inline(prefix: str, include_all: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if include_all:
        buttons.append([InlineKeyboardButton(text="Все", callback_data=f"{prefix}:all")])
    buttons.extend(
        [
            [InlineKeyboardButton(text="В работе", callback_data=f"{prefix}:in_work")],
            [InlineKeyboardButton(text="Завершенные", callback_data=f"{prefix}:completed")],
            [InlineKeyboardButton(text="Архив", callback_data=f"{prefix}:archived")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def repair_stages_inline(car_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=f"car_stage:{car_id}:{value}")] for value, label in REPAIR_STAGES]
    )


def car_actions_inline(car: dict, is_manager: bool = True) -> InlineKeyboardMarkup:
    car_id = car["id"]
    buttons = [
        [InlineKeyboardButton(text="Расходы", callback_data=f"report_car:{car_id}")],
        [InlineKeyboardButton(text="Фото дефектовки", callback_data=f"defect_photos:{car_id}")],
        [InlineKeyboardButton(text="Добавить фото дефектовки", callback_data=f"defect_photo_start:{car_id}")],
    ]
    if is_manager:
        buttons.append(
            [
                InlineKeyboardButton(text="Изменить название", callback_data=f"edit_car_title:{car_id}"),
                InlineKeyboardButton(text="Изменить работы", callback_data=f"edit_car_description:{car_id}"),
            ]
        )
        buttons.append([InlineKeyboardButton(text="Изменить этап", callback_data=f"stage_menu:{car_id}")])
        if car["status"] == "in_work":
            buttons.append([InlineKeyboardButton(text="Завершить", callback_data=f"car_status:{car_id}:completed")])
            buttons.append([InlineKeyboardButton(text="В архив", callback_data=f"car_status:{car_id}:archived")])
        elif car["status"] == "completed":
            buttons.append([InlineKeyboardButton(text="Вернуть в работу", callback_data=f"car_status:{car_id}:in_work")])
            buttons.append([InlineKeyboardButton(text="В архив", callback_data=f"car_status:{car_id}:archived")])
        else:
            buttons.append([InlineKeyboardButton(text="Вернуть в работу", callback_data=f"car_status:{car_id}:in_work")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def expenses_inline(expenses: list[dict], is_manager: bool = False) -> InlineKeyboardMarkup | None:
    return None


def confirm_delete_expense_inline(expense_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, удалить", callback_data=f"expense_delete:{expense_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data="expense_delete_cancel")],
        ]
    )
