from __future__ import annotations

import asyncio
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

import httpx
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from dotenv import load_dotenv

from bot_app.api_client import api_client
from bot_app.keyboards import (
    ACTIVE_ORDERS,
    ADD_CAR,
    ADD_EXPENSE,
    ARCHIVE,
    CANCEL,
    DONE,
    EXPORT,
    HELP,
    LIST_CARS,
    MY_EXPENSES,
    SHOW_EXPENSES,
    SKIP,
    TOTALS,
    cancel_keyboard,
    car_actions_inline,
    cars_inline,
    categories_inline,
    currency_inline,
    employee_menu,
    expenses_inline,
    main_menu,
    manager_menu,
    photo_collection_keyboard,
    repair_stages_inline,
    skip_cancel_keyboard,
    status_filter_inline,
    confirm_delete_expense_inline,
)
from bot_app.states import AddCarStates, AddDefectPhotoStates, AddExpenseStates, QuickExpenseStates


load_dotenv(override=True)
router = Router()
logger = logging.getLogger(__name__)
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "media"))
GENERIC_ERROR_TEXT = "Не получилось выполнить действие. Попробуйте ещё раз. Если ошибка повторится, сообщите администратору."
SAVE_ERROR_TEXT = "Не получилось сохранить данные. Попробуйте ещё раз. Если ошибка повторится, сообщите администратору."
PHOTO_STATE_LOCKS: dict[str, asyncio.Lock] = {}
QUICK_EXPENSE_RE = re.compile(r"^(?P<description>.+?)\s+(?P<amount>\d+(?:[,.]\d{1,2})?)$")
MENU_TEXTS = {
    ACTIVE_ORDERS,
    ADD_CAR,
    ADD_EXPENSE,
    ARCHIVE,
    CANCEL,
    DONE,
    EXPORT,
    HELP,
    LIST_CARS,
    MY_EXPENSES,
    SHOW_EXPENSES,
    SKIP,
    TOTALS,
}
STATUS_TITLES = {
    "all": "Все заказы",
    "in_work": "Заказы в работе",
    "completed": "Завершенные заказы",
    "archived": "Архивные заказы",
}


def _telegram_image_file_id(message: Message) -> str:
    if message.photo:
        return message.photo[-1].file_id
    if message.document and (message.document.mime_type or "").startswith("image/"):
        return message.document.file_id
    return ""



def _photo_lock(message: Message, scope: str) -> asyncio.Lock:
    chat_id = message.chat.id if message.chat else 0
    user_id = message.from_user.id if message.from_user else 0
    key = f"{scope}:{chat_id}:{user_id}"
    lock = PHOTO_STATE_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        PHOTO_STATE_LOCKS[key] = lock
    return lock


async def _append_photo_state(message: Message, state: FSMContext, field_subdir: str) -> int:
    file_id = _telegram_image_file_id(message)
    if not file_id:
        return 0
    image_path = await _save_telegram_file_to_media(message, file_id, field_subdir)
    async with _photo_lock(message, field_subdir):
        data = await state.get_data()
        photos = list(data.get("photos") or [])
        photos.append({"file_id": file_id, "image_path": image_path})
        await state.update_data(photos=photos)
        return len(photos)


async def _save_telegram_file_to_media(message: Message, file_id: str, subdir: str) -> str:
    if not file_id:
        return ""
    try:
        tg_file = await message.bot.get_file(file_id)
        source_path = tg_file.file_path or ""
        ext = Path(source_path).suffix or ".jpg"
        rel_path = Path(subdir) / f"{uuid4().hex}{ext}"
        abs_path = MEDIA_ROOT / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        await message.bot.download_file(source_path, destination=abs_path)
        return str(rel_path)
    except Exception:
        logger.exception("Failed to download Telegram file to media: file_id=%s subdir=%s", file_id, subdir)
        return ""


def _access_control_enabled() -> bool:
    return os.getenv("BOT_ACCESS_CONTROL", "False").lower() == "true"


def _full_name(message: Message) -> str:
    user = message.from_user
    if not user:
        return ""
    return " ".join(part for part in [user.first_name, user.last_name] if part)


def _money(value, currency: str = "BYN") -> str:
    return f"{Decimal(str(value)):.2f} {currency}"


def _totals_text(car: dict) -> str:
    totals = car.get("total_expenses_by_currency") or {}
    if totals:
        return ", ".join(_money(amount, currency) for currency, amount in sorted(totals.items()))
    return _money(car.get("total_expenses") or 0)


def _is_manager_access(access: dict | None) -> bool:
    if not _access_control_enabled():
        return True
    return bool(access and access.get("role") in {"manager", "admin"})


async def _get_access(telegram_id: int | None) -> dict | None:
    if not telegram_id or not _access_control_enabled():
        return {"allowed": True, "role": "admin"}
    try:
        return await api_client.check_access(telegram_id)
    except httpx.HTTPError:
        return None


async def _message_menu(message: Message) -> object:
    access = await _get_access(message.from_user.id if message.from_user else None)
    return manager_menu() if _is_manager_access(access) else employee_menu()


async def _require_manager(message: Message) -> bool:
    access = await _get_access(message.from_user.id if message.from_user else None)
    if _is_manager_access(access):
        return True
    await message.answer("Это действие доступно только руководителю.", reply_markup=employee_menu())
    return False


async def _require_manager_callback(callback: CallbackQuery) -> bool:
    access = await _get_access(callback.from_user.id if callback.from_user else None)
    if _is_manager_access(access):
        return True
    if callback.message:
        await callback.message.answer("Это действие доступно только руководителю.")
    await callback.answer()
    return False


def _car_label(car: dict) -> str:
    label = car["title"]
    if car.get("make_model"):
        label = f"{label} ({car['make_model']})"
    return label


def _car_line(car: dict, include_totals: bool = True) -> str:
    vin = f"\nVIN/номер: {car['vin_or_plate']}" if car.get("vin_or_plate") else ""
    description = f"\nОписание: {car['description']}" if car.get("description") else ""
    total = f"\nРасходов: {car.get('expenses_count') or 0}\nИтого: {_totals_text(car)}" if include_totals else ""
    return (
        f"#{car['id']} {_car_label(car)}\n"
        f"Статус: {car['status_display']}\n"
        f"Этап: {car.get('repair_stage_display') or '-'}"
        f"{vin}{description}{total}"
    )


def _expense_line(expense: dict) -> str:
    employee = expense.get("employee") or "не указан"
    created = str(expense.get("created_at") or "")[:10]
    category = expense.get("category") or "без категории"
    return f"{_money(expense['amount'], expense.get('currency') or 'BYN')} - {expense['description']} - {category} - {employee} - {created}"


async def _safe_register(message: Message) -> None:
    if not message.from_user or _access_control_enabled():
        return
    await api_client.register_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=_full_name(message),
    )


async def _active_cars() -> list[dict]:
    return await api_client.list_cars(status="in_work")


async def _send_api_error(message: Message, text: str = GENERIC_ERROR_TEXT) -> None:
    await message.answer(text, reply_markup=await _message_menu(message))


@router.message(CommandStart())
async def start(message: Message, access_user: dict | None = None) -> None:
    try:
        await _safe_register(message)
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    access = access_user or await _get_access(message.from_user.id if message.from_user else None)
    menu = manager_menu() if _is_manager_access(access) else employee_menu()
    await message.answer("Меню учета заказов и расходов по кузовному ремонту.", reply_markup=menu)


@router.message(F.text == CANCEL)
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=await _message_menu(message))


@router.message(F.text == HELP)
async def help_message(message: Message) -> None:
    await message.answer(
        "Быстрый расход: напишите сообщение в формате `капот 200`.\n"
        "Расходы добавляются только к заказам со статусом В работе.",
        reply_markup=await _message_menu(message),
        parse_mode="Markdown",
    )


@router.message(F.text == ADD_CAR)
async def add_car_start(message: Message, state: FSMContext) -> None:
    if not await _require_manager(message):
        return
    await state.set_state(AddCarStates.title)
    await message.answer("Введите название / условное описание заказа.", reply_markup=cancel_keyboard())


@router.message(AddCarStates.title)
async def add_car_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=(message.text or "").strip())
    await state.set_state(AddCarStates.brand)
    await message.answer("Введите марку автомобиля.", reply_markup=cancel_keyboard())


@router.message(AddCarStates.brand)
async def add_car_brand(message: Message, state: FSMContext) -> None:
    await state.update_data(brand=(message.text or "").strip())
    await state.set_state(AddCarStates.model)
    await message.answer("Введите модель автомобиля.", reply_markup=cancel_keyboard())


@router.message(AddCarStates.model)
async def add_car_model(message: Message, state: FSMContext) -> None:
    await state.update_data(model=(message.text or "").strip())
    await state.set_state(AddCarStates.vin_or_plate)
    await message.answer("Введите VIN или госномер, либо нажмите Пропустить.", reply_markup=skip_cancel_keyboard())


@router.message(AddCarStates.vin_or_plate)
async def add_car_vin_or_plate(message: Message, state: FSMContext) -> None:
    await state.update_data(vin_or_plate="" if message.text == SKIP else (message.text or "").strip())
    await state.set_state(AddCarStates.description)
    await message.answer("Введите краткое описание работ / повреждений, либо нажмите Пропустить.", reply_markup=skip_cancel_keyboard())


@router.message(AddCarStates.description)
async def add_car_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description="" if message.text == SKIP else (message.text or "").strip())
    await state.set_state(AddCarStates.photo)
    await message.answer("Отправьте одно или несколько фото автомобиля. Когда закончите, нажмите Готово.", reply_markup=photo_collection_keyboard())


@router.message(AddCarStates.photo, F.photo | F.document)
async def add_car_photo(message: Message, state: FSMContext) -> None:
    count = await _append_photo_state(message, state, "cars")
    if not count:
        await message.answer("Отправьте фото автомобиля или нажмите Готово.")
        return
    await message.answer(f"Фото добавлено. Всего фото: {count}. Можно отправить ещё или нажать Готово.", reply_markup=photo_collection_keyboard())


@router.message(AddCarStates.photo)
async def add_car_photo_done(message: Message, state: FSMContext) -> None:
    if message.text == SKIP:
        await state.update_data(car_photo_file_id="", car_photo_path="", photos=[])
        await _finish_car(message, state)
        return
    if message.text == DONE:
        await _finish_car(message, state)
        return
    await message.answer("Отправьте фото автомобиля или нажмите Готово.", reply_markup=photo_collection_keyboard())


async def _finish_car(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("title"):
        logger.info("Skip car creation without title, probably duplicate media group update")
        return
    if message.from_user:
        data["created_by_telegram_id"] = message.from_user.id
    try:
        car = await api_client.create_car(data)
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    await state.clear()
    photo_count = len(data.get("photos") or [])
    photo_line = f"\nФото: {photo_count} шт." if photo_count else "\nФото: не добавлено"
    await message.answer(
        "Заказ добавлен.\n"
        f"Заказ: {_car_label(car)}\n"
        f"Статус: {car['status_display']}\n"
        f"Этап: {car['repair_stage_display']}"
        f"{photo_line}",
        reply_markup=await _message_menu(message),
    )


@router.message(F.text == ACTIVE_ORDERS)
async def active_orders(message: Message) -> None:
    try:
        cars = await _active_cars()
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    if not cars:
        await message.answer("Активных заказов нет.", reply_markup=await _message_menu(message))
        return
    for car in cars[:30]:
        await message.answer(_car_line(car, include_totals=False), reply_markup=car_actions_inline(car, is_manager=False))
    if len(cars) > 30:
        await message.answer(f"Показаны первые 30 из {len(cars)}.")


@router.message(F.text == LIST_CARS)
async def list_cars(message: Message) -> None:
    if not await _require_manager(message):
        return
    await message.answer("Выберите статус заказов.", reply_markup=status_filter_inline("cars_status"))


@router.callback_query(F.data.startswith("cars_status:"))
async def list_cars_by_status(callback: CallbackQuery) -> None:
    if not await _require_manager_callback(callback):
        return
    status_value = callback.data.split(":", 1)[1]
    status_filter = None if status_value == "all" else status_value
    try:
        cars = await api_client.list_cars(status=status_filter)
    except httpx.HTTPError:
        await callback.message.answer(GENERIC_ERROR_TEXT)
        await callback.answer()
        return
    title = STATUS_TITLES.get(status_value, "Заказы")
    if not cars:
        await callback.message.answer(f"{title}: список пуст.")
        await callback.answer()
        return
    await callback.message.answer(title)
    for car in cars[:30]:
        await callback.message.answer(_car_line(car), reply_markup=car_actions_inline(car, is_manager=True))
    if len(cars) > 30:
        await callback.message.answer(f"Показаны первые 30 из {len(cars)}.")
    await callback.answer()


@router.callback_query(F.data.startswith("car_status:"))
async def change_car_status(callback: CallbackQuery) -> None:
    if not await _require_manager_callback(callback):
        return
    _, car_id, status_value = callback.data.split(":")
    try:
        car = await api_client.update_car_status(int(car_id), status_value)
    except httpx.HTTPError:
        await callback.message.answer("Не получилось изменить статус. Попробуйте ещё раз.")
        await callback.answer()
        return
    await callback.message.answer(
        f"Статус изменен.\nЗаказ: {_car_label(car)}\nНовый статус: {car['status_display']}",
        reply_markup=car_actions_inline(car, is_manager=True),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stage_menu:"))
async def stage_menu(callback: CallbackQuery) -> None:
    if not await _require_manager_callback(callback):
        return
    car_id = int(callback.data.split(":")[1])
    await callback.message.answer("Выберите новый этап ремонта.", reply_markup=repair_stages_inline(car_id))
    await callback.answer()


@router.callback_query(F.data.startswith("car_stage:"))
async def change_car_stage(callback: CallbackQuery) -> None:
    if not await _require_manager_callback(callback):
        return
    _, car_id, stage_value = callback.data.split(":")
    try:
        car = await api_client.update_car_stage(int(car_id), stage_value)
    except httpx.HTTPError:
        await callback.message.answer("Не получилось изменить этап. Попробуйте ещё раз.")
        await callback.answer()
        return
    await callback.message.answer(
        f"Этап ремонта изменен.\nНовый этап: {car['repair_stage_display']}.",
        reply_markup=car_actions_inline(car, is_manager=True),
    )
    await callback.answer()


@router.message(F.text == ADD_EXPENSE)
async def add_expense_start(message: Message, state: FSMContext) -> None:
    try:
        cars = await _active_cars()
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    if not cars:
        await message.answer("Активных заказов нет.", reply_markup=await _message_menu(message))
        return
    await state.set_state(AddExpenseStates.car)
    await message.answer("Выберите заказ в работе.", reply_markup=cars_inline(cars, "expense_car"))


@router.callback_query(AddExpenseStates.car, F.data.startswith("expense_car:"))
async def add_expense_car(callback: CallbackQuery, state: FSMContext) -> None:
    car_id = int(callback.data.split(":")[1])
    await state.update_data(car_id=car_id)
    await state.set_state(AddExpenseStates.amount)
    await callback.message.answer("Введите сумму расхода.", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(AddExpenseStates.amount)
async def add_expense_amount(message: Message, state: FSMContext) -> None:
    try:
        amount = Decimal((message.text or "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        await message.answer("Введите сумму числом, например 200 или 150.50.")
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return
    await state.update_data(amount=str(amount))
    await state.set_state(AddExpenseStates.currency)
    await message.answer("Выберите валюту расхода.", reply_markup=currency_inline())


@router.callback_query(AddExpenseStates.currency, F.data.startswith("currency:"))
async def add_expense_currency(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.split(":", 1)[1]
    await state.update_data(currency=currency)
    try:
        categories = await api_client.list_categories()
    except httpx.HTTPError:
        await callback.message.answer(GENERIC_ERROR_TEXT)
        await callback.answer()
        return
    await state.set_state(AddExpenseStates.category)
    await callback.message.answer("Выберите категорию расхода.", reply_markup=categories_inline(categories))
    await callback.answer()


@router.callback_query(AddExpenseStates.category, F.data.startswith("category:"))
async def add_expense_category(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=category_id, category_name="")
    await state.set_state(AddExpenseStates.description)
    await callback.message.answer("Введите описание расхода.", reply_markup=cancel_keyboard())
    await callback.answer()


@router.callback_query(AddExpenseStates.category, F.data.startswith("category_name:"))
async def add_expense_category_name(callback: CallbackQuery, state: FSMContext) -> None:
    category_name = callback.data.split(":", 1)[1]
    await state.update_data(category_id=None, category_name=category_name)
    await state.set_state(AddExpenseStates.description)
    await callback.message.answer("Введите описание расхода.", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(AddExpenseStates.description)
async def add_expense_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=(message.text or "").strip())
    await state.set_state(AddExpenseStates.comment)
    await message.answer("Добавьте комментарий или нажмите Пропустить.", reply_markup=skip_cancel_keyboard())


@router.message(AddExpenseStates.comment)
async def add_expense_comment(message: Message, state: FSMContext) -> None:
    await state.update_data(comment="" if message.text == SKIP else (message.text or "").strip())
    await state.set_state(AddExpenseStates.receipt)
    await message.answer("Отправьте одно или несколько фото чека/детали. Когда закончите, нажмите Готово.", reply_markup=photo_collection_keyboard())


@router.message(AddExpenseStates.receipt, F.photo | F.document)
async def add_expense_receipt_photo(message: Message, state: FSMContext) -> None:
    count = await _append_photo_state(message, state, "expense_receipts")
    if not count:
        await message.answer("Отправьте фото или нажмите Готово.")
        return
    await message.answer(f"Фото добавлено. Всего фото: {count}. Можно отправить ещё или нажать Готово.", reply_markup=photo_collection_keyboard())


@router.message(AddExpenseStates.receipt)
async def add_expense_receipt_done(message: Message, state: FSMContext) -> None:
    if message.text == SKIP:
        await state.update_data(receipt_photo_file_id="", receipt_photo_path="", photos=[])
        await _finish_expense(message, state)
        return
    if message.text == DONE:
        await _finish_expense(message, state)
        return
    await message.answer("Отправьте фото или нажмите Готово.", reply_markup=photo_collection_keyboard())


async def _finish_expense(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        expense = await api_client.create_expense(
            car_id=data["car_id"],
            amount=Decimal(data["amount"]),
            description=data["description"],
            employee_telegram_id=message.from_user.id if message.from_user else 0,
            category_id=data.get("category_id"),
            category_name=data.get("category_name", ""),
            currency=data.get("currency", "BYN"),
            comment=data.get("comment", ""),
            receipt_photo_file_id=data.get("receipt_photo_file_id", ""),
            receipt_photo_path=data.get("receipt_photo_path", ""),
            photos=data.get("photos") or [],
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            await message.answer("Расход можно добавить только к заказу со статусом В работе.", reply_markup=await _message_menu(message))
        else:
            await _send_api_error(message)
        return
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    await state.clear()
    await message.answer(
        "Расход сохранен.\n"
        f"Заказ: {expense['car']}\n"
        f"Категория: {expense.get('category') or 'без категории'}\n"
        f"Сумма: {_money(expense['amount'], expense.get('currency') or 'BYN')}\n"
        f"Описание: {expense['description']}",
        reply_markup=await _message_menu(message),
    )


@router.message(F.text == SHOW_EXPENSES)
async def show_expenses_start(message: Message) -> None:
    access = await _get_access(message.from_user.id if message.from_user else None)
    if _is_manager_access(access):
        await message.answer("Выберите статус заказов для просмотра расходов.", reply_markup=status_filter_inline("expenses_status"))
        return
    try:
        cars = await _active_cars()
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    if not cars:
        await message.answer("Активных заказов нет.", reply_markup=employee_menu())
        return
    await message.answer("Выберите заказ.", reply_markup=cars_inline(cars, "report_car"))


@router.callback_query(F.data.startswith("expenses_status:"))
async def show_expenses_status(callback: CallbackQuery) -> None:
    if not await _require_manager_callback(callback):
        return
    status_value = callback.data.split(":", 1)[1]
    status_filter = None if status_value == "all" else status_value
    try:
        cars = await api_client.list_cars(status=status_filter)
    except httpx.HTTPError:
        await callback.message.answer(GENERIC_ERROR_TEXT)
        await callback.answer()
        return
    if not cars:
        await callback.message.answer("По выбранному статусу заказов нет.")
        await callback.answer()
        return
    await callback.message.answer("Выберите заказ.", reply_markup=cars_inline(cars, "report_car"))
    await callback.answer()


@router.callback_query(F.data.startswith("report_car:"))
async def show_expenses_for_car(callback: CallbackQuery) -> None:
    access = await _get_access(callback.from_user.id if callback.from_user else None)
    is_manager = _is_manager_access(access)
    car_id = int(callback.data.split(":")[1])
    try:
        car = await api_client.get_car(car_id)
        if not is_manager and car.get("status") != "in_work":
            await callback.message.answer("Сотрудник может смотреть только активные заказы в работе.")
            await callback.answer()
            return
        expenses = await api_client.list_expenses(car_id=car_id)
    except httpx.HTTPError:
        await callback.message.answer(GENERIC_ERROR_TEXT)
        await callback.answer()
        return
    lines = [
        _car_line(car),
        "",
        "Расходы:",
    ]
    if expenses:
        lines.extend(_expense_line(expense) for expense in expenses[:20])
        if len(expenses) > 20:
            lines.append(f"Показаны первые 20 из {len(expenses)}.")
    else:
        lines.append("Расходов пока нет.")
    await callback.message.answer(
        "\n".join(lines),
        reply_markup=expenses_inline(expenses, is_manager=is_manager) or car_actions_inline(car, is_manager=is_manager),
    )
    await callback.answer()


@router.message(F.text == MY_EXPENSES)
async def my_expenses(message: Message) -> None:
    try:
        expenses = await api_client.list_expenses(employee_telegram_id=message.from_user.id if message.from_user else None)
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    if not expenses:
        await message.answer("У вас пока нет сохраненных расходов.", reply_markup=await _message_menu(message))
        return
    lines = ["Мои последние расходы:"]
    lines.extend(_expense_line(expense) for expense in expenses[:10])
    await message.answer("\n".join(lines), reply_markup=await _message_menu(message))


@router.message(F.text == TOTALS)
async def totals(message: Message) -> None:
    if not await _require_manager(message):
        return
    try:
        rows = await api_client.summary()
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    if not rows:
        await message.answer("Заказов пока нет.", reply_markup=manager_menu())
        return
    lines = ["Итоги по заказам:"]
    totals_all: dict[str, Decimal] = {}
    for row in rows[:30]:
        totals = row.get("total_expenses_by_currency") or {}
        if totals:
            total_text = ", ".join(_money(amount, currency) for currency, amount in sorted(totals.items()))
            for currency, amount in totals.items():
                totals_all[currency] = totals_all.get(currency, Decimal("0")) + Decimal(str(amount))
        else:
            total_text = _money(row.get("total_expenses") or 0)
            totals_all["BYN"] = totals_all.get("BYN", Decimal("0")) + Decimal(str(row.get("total_expenses") or 0))
        stage = row.get("repair_stage_display") or "-"
        lines.append(f"#{row['car_id']} {row['title']} - {row['status_display']} - {stage} - {total_text}")
    if totals_all and len(rows) > 1:
        lines.append("Всего: " + ", ".join(_money(amount, currency) for currency, amount in sorted(totals_all.items())))
    await message.answer("\n".join(lines), reply_markup=manager_menu())


@router.message(F.text == ARCHIVE)
async def archive(message: Message) -> None:
    if not await _require_manager(message):
        return
    try:
        cars = await api_client.list_cars(status="archived")
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    if not cars:
        await message.answer("Архив пуст.", reply_markup=manager_menu())
        return
    for car in cars[:30]:
        await message.answer(_car_line(car), reply_markup=car_actions_inline(car, is_manager=True))


@router.callback_query(F.data.startswith("expense_delete_confirm:"))
async def expense_delete_confirm(callback: CallbackQuery) -> None:
    if not await _require_manager_callback(callback):
        return
    expense_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        "Вы уверены, что хотите удалить расход?\nЭто действие нельзя отменить.",
        reply_markup=confirm_delete_expense_inline(expense_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("expense_delete:"))
async def expense_delete(callback: CallbackQuery) -> None:
    if not await _require_manager_callback(callback):
        return
    expense_id = int(callback.data.split(":")[1])
    try:
        await api_client.delete_expense(expense_id)
    except httpx.HTTPError:
        await callback.message.answer("Не получилось удалить расход. Попробуйте ещё раз.")
        await callback.answer()
        return
    await callback.message.answer("Расход удален.")
    await callback.answer()


@router.callback_query(F.data == "expense_delete_cancel")
async def expense_delete_cancel(callback: CallbackQuery) -> None:
    await callback.message.answer("Удаление отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("defect_photos:"))
async def defect_photos(callback: CallbackQuery) -> None:
    access = await _get_access(callback.from_user.id if callback.from_user else None)
    is_manager = _is_manager_access(access)
    car_id = int(callback.data.split(":")[1])
    try:
        car = await api_client.get_car(car_id)
        if not is_manager and car.get("status") != "in_work":
            await callback.message.answer("Сотрудник может смотреть фото дефектовки только активного заказа.")
            await callback.answer()
            return
        photos = await api_client.list_defect_photos(car_id=car_id)
    except httpx.HTTPError:
        await callback.message.answer(GENERIC_ERROR_TEXT)
        await callback.answer()
        return
    if not photos:
        await callback.message.answer("Фото дефектовки пока нет.", reply_markup=car_actions_inline(car, is_manager=is_manager))
        await callback.answer()
        return
    await callback.message.answer(f"Фото дефектовки: {_car_label(car)}")
    for photo in photos[:10]:
        caption = photo.get("comment") or "Фото дефектовки"
        try:
            await callback.message.answer_photo(photo["photo_file_id"], caption=caption[:1024])
        except Exception:
            await callback.message.answer(f"Фото file_id: {photo['photo_file_id']}" + (f"\n{caption}" if caption else ""))
    if len(photos) > 10:
        await callback.message.answer(f"Показаны первые 10 из {len(photos)}.")
    await callback.answer()


@router.callback_query(F.data.startswith("defect_photo_start:"))
async def defect_photo_start(callback: CallbackQuery, state: FSMContext) -> None:
    car_id = int(callback.data.split(":")[1])
    access = await _get_access(callback.from_user.id if callback.from_user else None)
    is_manager = _is_manager_access(access)
    try:
        car = await api_client.get_car(car_id)
    except httpx.HTTPError:
        await callback.message.answer(GENERIC_ERROR_TEXT)
        await callback.answer()
        return
    if not is_manager and car.get("status") != "in_work":
        await callback.message.answer("Сотрудник может добавлять фото дефектовки только к активному заказу.")
        await callback.answer()
        return
    await state.clear()
    await state.set_state(AddDefectPhotoStates.photo)
    await state.update_data(car_id=car_id, car_title=_car_label(car))
    await callback.message.answer("Отправьте одно или несколько фото повреждений, деталей или номеров. Когда закончите, нажмите Готово.", reply_markup=photo_collection_keyboard())
    await callback.answer()


@router.message(AddDefectPhotoStates.photo, F.photo | F.document)
async def defect_photo_received(message: Message, state: FSMContext) -> None:
    count = await _append_photo_state(message, state, "defect_photos")
    if not count:
        await message.answer("Нужно отправить фото.", reply_markup=photo_collection_keyboard())
        return
    await message.answer(f"Фото добавлено. Всего фото: {count}. Можно отправить ещё или нажать Готово.", reply_markup=photo_collection_keyboard())


@router.message(AddDefectPhotoStates.photo)
async def defect_photo_done(message: Message, state: FSMContext) -> None:
    if message.text == SKIP:
        await state.clear()
        await message.answer("Добавление фото дефектовки отменено.", reply_markup=await _message_menu(message))
        return
    if message.text == DONE:
        data = await state.get_data()
        photos = data.get("photos") or []
        if not photos:
            await message.answer("Сначала отправьте хотя бы одно фото или нажмите Пропустить.", reply_markup=photo_collection_keyboard())
            return
        try:
            await api_client.create_defect_photo(
                car_id=data["car_id"],
                created_by_telegram_id=message.from_user.id if message.from_user else 0,
                photos=photos,
            )
        except httpx.HTTPError:
            await _send_api_error(message)
            return
        await state.clear()
        await message.answer(f"Фото дефектовки сохранены. Всего фото: {len(photos)}.", reply_markup=await _message_menu(message))
        return
    await message.answer("Отправьте фото или нажмите Готово.", reply_markup=photo_collection_keyboard())


@router.message(F.text == EXPORT)
async def export_message(message: Message) -> None:
    if not await _require_manager(message):
        return
    try:
        report = await api_client.download_report()
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    document = BufferedInputFile(report, filename="auto_bot_report.xlsx")
    await message.answer_document(document, caption="Выгрузка: заказы, расходы и итоги.", reply_markup=manager_menu())


@router.message(F.text.regexp(QUICK_EXPENSE_RE.pattern))
async def quick_expense(message: Message, state: FSMContext) -> None:
    if not message.text or message.text in MENU_TEXTS:
        return
    match = QUICK_EXPENSE_RE.match(message.text.strip())
    if not match:
        return
    description = match.group("description").strip()
    amount = Decimal(match.group("amount").replace(",", "."))
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return
    try:
        cars = await _active_cars()
    except httpx.HTTPError:
        await _send_api_error(message)
        return
    if not cars:
        await message.answer("Активных заказов нет.", reply_markup=await _message_menu(message))
        return
    await state.set_state(QuickExpenseStates.car)
    await state.update_data(description=description, amount=str(amount))
    await message.answer("К какому активному заказу привязать расход?", reply_markup=cars_inline(cars, "quick_car"))


@router.callback_query(QuickExpenseStates.car, F.data.startswith("quick_car:"))
async def quick_expense_car(callback: CallbackQuery, state: FSMContext) -> None:
    car_id = int(callback.data.split(":")[1])
    await state.update_data(car_id=car_id)
    await state.set_state(QuickExpenseStates.currency)
    await callback.message.answer("Выберите валюту расхода.", reply_markup=currency_inline(prefix="quick_currency"))
    await callback.answer()


@router.callback_query(QuickExpenseStates.currency, F.data.startswith("quick_currency:"))
async def quick_expense_currency(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.split(":", 1)[1]
    await state.update_data(currency=currency)
    try:
        categories = await api_client.list_categories()
    except httpx.HTTPError:
        await callback.message.answer(GENERIC_ERROR_TEXT)
        await callback.answer()
        return
    await state.set_state(QuickExpenseStates.category)
    await callback.message.answer("Выберите категорию расхода.", reply_markup=categories_inline(categories, prefix="quick_category"))
    await callback.answer()


@router.callback_query(QuickExpenseStates.category, F.data.startswith("quick_category:"))
async def quick_expense_category(callback: CallbackQuery, state: FSMContext) -> None:
    category_id = int(callback.data.split(":")[1])
    await _finish_quick_expense(callback, state, category_id=category_id)


@router.callback_query(QuickExpenseStates.category, F.data.startswith("quick_category_name:"))
async def quick_expense_category_name(callback: CallbackQuery, state: FSMContext) -> None:
    category_name = callback.data.split(":", 1)[1]
    await _finish_quick_expense(callback, state, category_name=category_name)


async def _finish_quick_expense(
    callback: CallbackQuery,
    state: FSMContext,
    category_id: int | None = None,
    category_name: str = "",
) -> None:
    data = await state.get_data()
    try:
        expense = await api_client.create_expense(
            car_id=data["car_id"],
            amount=Decimal(data["amount"]),
            description=data["description"],
            employee_telegram_id=callback.from_user.id,
            category_id=category_id,
            category_name=category_name,
            currency=data.get("currency", "BYN"),
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            await callback.message.answer("Расход можно добавить только к заказу со статусом В работе.")
        else:
            await callback.message.answer(SAVE_ERROR_TEXT)
        await callback.answer()
        return
    except httpx.HTTPError:
        await callback.message.answer(SAVE_ERROR_TEXT)
        await callback.answer()
        return
    await state.clear()
    await callback.message.answer(
        "Расход сохранен.\n"
        f"Заказ: {expense['car']}\n"
        f"Категория: {expense.get('category') or 'без категории'}\n"
        f"Сумма: {_money(expense['amount'], expense.get('currency') or 'BYN')}\n"
        f"Описание: {expense['description']}",
        reply_markup=main_menu(_is_manager_access(await _get_access(callback.from_user.id))),
    )
    await callback.answer()


@router.message(F.text)
async def unknown_text(message: Message) -> None:
    if not message.text or message.text in MENU_TEXTS or message.text.startswith("/"):
        return
    await message.answer("Не удалось определить сумму.\nНапишите расход в формате: капот 200", reply_markup=await _message_menu(message))
