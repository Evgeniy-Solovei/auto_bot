import json
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from bot_app.keyboards import (
    ADD_CAR,
    ADD_EXPENSE,
    ACTIVE_ORDERS,
    LIST_CARS,
    back_to_photos_inline,
    car_actions_inline,
    car_photos_menu_inline,
    cars_page_inline,
    employee_menu,
    expenses_inline,
    manager_menu,
    repair_stages_inline,
)
from bot_app.handlers import _expenses_customer_text, parse_car_title_brand_model, parse_expense_items
from core.management.commands.seed_categories import DEFAULT_CATEGORIES
from core.models import Car, CarPhoto, DefectPhoto, Expense, ExpenseCategory, ExpensePhoto, TelegramUser


class SmokeFailure(Exception):
    pass


class Command(BaseCommand):
    LONG_FILE_ID = "AgACAgIAAxkBAA" + ("X" * 700)
    help = "Run a full smoke test for users, permissions, orders, expenses, defect photos, statuses and menus."

    def add_arguments(self, parser):
        parser.add_argument("--keep-data", action="store_true", help="Do not delete smoke-test data after the run.")

    def handle(self, *args, **options):
        self.keep_data = options["keep_data"]
        self.client = Client()
        self.headers = {}
        if settings.INTERNAL_API_KEY:
            self.headers["HTTP_X_API_KEY"] = settings.INTERNAL_API_KEY

        self.created_car_ids = []
        self.created_user_ids = []
        self.created_expense_ids = []
        self.created_defect_photo_ids = []

        try:
            self._run()
        except SmokeFailure as exc:
            self._cleanup()
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            self._cleanup()
            raise
        else:
            if not self.keep_data:
                self._cleanup()
            self.stdout.write(self.style.SUCCESS("FULL SMOKE TEST PASSED"))

    def _run(self):
        self._check_menus()
        self._check_cars_page_keyboard()
        self._check_car_title_parser()
        self._seed_categories()
        manager = self._create_user(910000001, "manager", "Smoke Manager", TelegramUser.Role.MANAGER)
        employee = self._create_user(910000002, "employee", "Smoke Employee", TelegramUser.Role.EMPLOYEE)
        inactive = self._create_user(910000003, "inactive", "Smoke Inactive", TelegramUser.Role.EMPLOYEE, is_active=False)

        self._check_access(manager.telegram_id, allowed=True, role=TelegramUser.Role.MANAGER)
        self._check_access(employee.telegram_id, allowed=True, role=TelegramUser.Role.EMPLOYEE)
        self._check_access(inactive.telegram_id, allowed=False, role=TelegramUser.Role.EMPLOYEE)
        self._check_access(919999999, allowed=False, role=None)

        car = self._create_car(manager.telegram_id)
        self._patch_car(car["id"])
        self._create_defect_photo(car["id"], employee.telegram_id)

        expense_byn = self._create_expense(car["id"], employee.telegram_id, "Покраска бампера", "650.00", "BYN", "Работа")
        expense_usd = self._create_expense(car["id"], manager.telegram_id, "Дверь", "500.00", "USD", "Детали")
        self._patch_expense(expense_byn["id"], manager.telegram_id)

        self._check_car_lists(car["id"])
        self._check_expenses(car["id"], employee.telegram_id)
        self._check_summary(car["id"])
        quick_expense = self._check_quick_expense(car["id"], employee.telegram_id)
        self._delete_expense(quick_expense["id"])
        self._check_status_restriction(car["id"], employee.telegram_id)
        self._delete_expense(expense_usd["id"])

    def _api(self, method, path, payload=None, expected=200, query=None):
        data = json.dumps(payload or {}) if payload is not None else None
        response = getattr(self.client, method)(
            path,
            data=data,
            query_params=query,
            content_type="application/json",
            **self.headers,
        )
        if response.status_code != expected:
            raise SmokeFailure(f"{method.upper()} {path}: expected {expected}, got {response.status_code}: {response.content[:500]!r}")
        if response.content:
            return response.json()
        return None

    def _check_menus(self):
        manager_texts = {button.text for row in manager_menu().keyboard for button in row}
        employee_texts = {button.text for row in employee_menu().keyboard for button in row}
        self._assert(ADD_CAR in manager_texts, "Manager menu has add order")
        self._assert(LIST_CARS in manager_texts, "Manager menu has order list")
        self._assert(ADD_EXPENSE in manager_texts, "Manager menu has add expense")
        self._assert(ADD_CAR not in employee_texts, "Employee menu does not have add order")
        self._assert(ACTIVE_ORDERS in employee_texts, "Employee menu has active orders")
        car_buttons = [button.text for row in car_actions_inline({"id": 1, "status": "in_work"}).inline_keyboard for button in row]
        self._assert(car_buttons.count("📸 Фото") == 1, "Car card has one photo button")
        self._assert(car_buttons.count("➕ Фото дефектовки") == 1, "Car card has separate add defect photo button")
        photo_menu_buttons = [button.text for row in car_photos_menu_inline(1).inline_keyboard for button in row]
        self._assert("➕ Добавить фото дефектовки" not in photo_menu_buttons, "Photo menu has no add defect button")
        self._assert("↩️ Назад к заказу" in photo_menu_buttons, "Photo menu has back to car button")
        photo_back_buttons = [button.text for row in back_to_photos_inline(1).inline_keyboard for button in row]
        self._assert("↩️ Назад к фото" in photo_back_buttons, "Photo view has back to photos button")
        stage_buttons = [button.text for row in repair_stages_inline(1).inline_keyboard for button in row]
        self._assert("↩️ Назад к заказу" in stage_buttons, "Stage menu has back to car button")
        expense_buttons = [button.text for row in expenses_inline([{"id": 10, "car_id": 1}]).inline_keyboard for button in row]
        self._assert("📋 Скопировать расходы" in expense_buttons, "Expenses buttons have copy button")
        self._assert("↩️ Назад к заказу" in expense_buttons, "Expenses buttons have back to car button")
        self._assert(not any("Фото расхода" in button for button in expense_buttons), "Expenses list has no expense photo buttons")
        customer_text = _expenses_customer_text([
            {"amount": "650.00", "currency": "BYN", "description": "дверь передняя левая", "category": "Работа", "employee": "fast_wheels", "created_at": "2026-06-15"},
            {"amount": "650.00", "currency": "BYN", "description": "дверь задняя левая", "category": "Работа", "employee": "fast_wheels", "created_at": "2026-06-15"},
        ])
        self._assert(customer_text == "Расходы:\n650.00 BYN - дверь передняя левая\n650.00 BYN - дверь задняя левая", "Customer expenses copy text is clean")

    def _check_cars_page_keyboard(self):
        cars = [
            {"id": idx, "title": f"Заказ {idx}", "make_model": "Toyota Prius", "status_display": "В работе"}
            for idx in range(1, 26)
        ]
        keyboard = cars_page_inline(cars, status_value="all", page=0)
        rows = keyboard.inline_keyboard
        car_buttons = [row[0] for row in rows[:-1]]
        nav_buttons = rows[-1]
        self._assert(len(car_buttons) == 10, "Cars page shows 10 order buttons")
        self._assert(any("Вперёд" in button.text for button in nav_buttons), "Cars page has next button")
        self._assert(not car_buttons[0].text.startswith("🟢"), "Cars page buttons have no green icon")

    def _check_car_title_parser(self):
        comma = parse_car_title_brand_model("Вова, Toyota, Prius")
        dot = parse_car_title_brand_model("Вова. Toyota. Prius")
        self._assert(comma == ("Вова", "Toyota", "Prius"), "Car title comma parser works")
        self._assert(dot == ("Вова", "Toyota", "Prius"), "Car title dot parser works")

    def _seed_categories(self):
        ExpenseCategory.objects.exclude(name__in=DEFAULT_CATEGORIES).update(is_active=False)
        for name in DEFAULT_CATEGORIES:
            ExpenseCategory.objects.update_or_create(name=name, defaults={"is_active": True})
        active = set(ExpenseCategory.objects.filter(is_active=True).values_list("name", flat=True))
        self._assert(active == set(DEFAULT_CATEGORIES), f"Active categories are exactly {DEFAULT_CATEGORIES}")

    def _create_user(self, telegram_id, username, full_name, role, is_active=True):
        TelegramUser.objects.filter(telegram_id=telegram_id).delete()
        user = TelegramUser.objects.create(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            role=role,
            is_active=is_active,
        )
        self.created_user_ids.append(user.id)
        return user

    def _check_access(self, telegram_id, allowed, role):
        data = self._api("get", "/api/telegram-users/access/", expected=200, query={"telegram_id": telegram_id})
        self._assert(data["allowed"] is allowed, f"Access allowed={allowed} for {telegram_id}")
        if role:
            self._assert(data["role"] == role, f"Role {role} for {telegram_id}")

    def _create_car(self, manager_tg_id):
        data = self._api(
            "post",
            "/api/cars/",
            {
                "title": "SMOKE Audi Q3 кузовной ремонт",
                "brand": "Audi",
                "model": "Q3",
                "vin_or_plate": "SMOKE-001",
                "description": "Дефектовка: капот, крыло правое, фара правая, бампер.",
                "car_photo_file_id": self.LONG_FILE_ID,
                "vin_photo_file_id": self.LONG_FILE_ID + "vin",
                "vin_photo_path": "vin_photos/smoke-vin.jpg",
                "photos": [
                    {"file_id": self.LONG_FILE_ID + "1", "image_path": "cars/smoke-1.jpg"},
                    {"file_id": self.LONG_FILE_ID + "2", "image_path": "cars/smoke-2.jpg"},
                    {"file_id": self.LONG_FILE_ID + "3", "image_path": "cars/smoke-3.jpg"},
                ],
                "created_by_telegram_id": manager_tg_id,
            },
            expected=201,
        )
        self.created_car_ids.append(data["id"])
        self._assert(data["status"] == Car.Status.IN_WORK, "New car status is in work")
        self._assert(data["repair_stage"] == Car.RepairStage.ACCEPTED, "New car repair stage is accepted")
        self._assert(data["car_photo_file_id"] == self.LONG_FILE_ID + "1", "Car photo saved")
        self._assert(data["vin_photo_file_id"] == self.LONG_FILE_ID + "vin", "VIN photo saved")
        self._assert(CarPhoto.objects.filter(car_id=data["id"]).count() == 3, "All car photos saved")
        car_photos = self._api("get", "/api/car-photos/", expected=200, query={"car_id": data["id"]})
        self._assert(len(car_photos) == 3, "Car photos API returns all photos")
        return data

    def _patch_car(self, car_id):
        data = self._api("patch", f"/api/cars/{car_id}/", {"repair_stage": Car.RepairStage.DEFECT}, expected=200)
        self._assert(data["repair_stage"] == Car.RepairStage.DEFECT, "Car stage changed to defect")
        data = self._api("patch", f"/api/cars/{car_id}/", {"repair_stage": Car.RepairStage.PAINT_ASSEMBLY}, expected=200)
        self._assert(data["repair_stage"] == Car.RepairStage.PAINT_ASSEMBLY, "Car stage changed to paint/assembly")

    def _create_defect_photo(self, car_id, employee_tg_id):
        data = self._api(
            "post",
            "/api/defect-photos/",
            {
                "car_id": car_id,
                "photo_file_id": self.LONG_FILE_ID,
                "comment": "Фото оригинального номера детали",
                "created_by_telegram_id": employee_tg_id,
            },
            expected=201,
        )
        self.created_defect_photo_ids.append(data["id"])
        self._assert(data["photo_file_id"] == self.LONG_FILE_ID, "Defect photo saved")
        photos = self._api("get", "/api/defect-photos/", expected=200, query={"car_id": car_id})
        self._assert(len(photos) == 1, "Defect photo list returns one photo")

    def _create_expense(self, car_id, tg_id, description, amount, currency, category_name):
        category = ExpenseCategory.objects.get(name=category_name, is_active=True)
        data = self._api(
            "post",
            "/api/expenses/",
            {
                "car_id": car_id,
                "amount": amount,
                "currency": currency,
                "category_id": category.id,
                "description": description,
                "comment": "Smoke expense",
                "receipt_photo_file_id": self.LONG_FILE_ID,
                "photos": [
                    {"file_id": self.LONG_FILE_ID + "a", "image_path": "expense_receipts/smoke-a.jpg"},
                    {"file_id": self.LONG_FILE_ID + "b", "image_path": "expense_receipts/smoke-b.jpg"},
                    {"file_id": self.LONG_FILE_ID + "c", "image_path": "expense_receipts/smoke-c.jpg"},
                ],
                "employee_telegram_id": tg_id,
            },
            expected=201,
        )
        self.created_expense_ids.append(data["id"])
        self._assert(data["currency"] == currency, f"Expense currency {currency} saved")
        self._assert(ExpensePhoto.objects.filter(expense_id=data["id"]).count() == 3, "All expense attachments saved")
        expense_photos = self._api("get", "/api/expense-photos/", expected=200, query={"expense_id": data["id"]})
        self._assert(len(expense_photos) == 3, "Expense attachments API returns all files")
        return data

    def _patch_expense(self, expense_id, manager_tg_id):
        data = self._api(
            "patch",
            f"/api/expenses/{expense_id}/",
            {"amount": "700.00", "comment": "Smoke edited", "updated_by_telegram_id": manager_tg_id},
            expected=200,
        )
        self._assert(Decimal(str(data["amount"])) == Decimal("700.00"), "Expense amount edited")
        self._assert(data["updated_by"] == "Smoke Manager", "Expense updated_by saved")

    def _check_car_lists(self, car_id):
        all_cars = self._api("get", "/api/cars/", expected=200)
        active_cars = self._api("get", "/api/cars/", expected=200, query={"status": Car.Status.IN_WORK})
        self._assert(any(car["id"] == car_id for car in all_cars), "Car is in all cars")
        self._assert(any(car["id"] == car_id for car in active_cars), "Car is in active cars")
        car = self._api("get", f"/api/cars/{car_id}/", expected=200)
        totals = car["total_expenses_by_currency"]
        self._assert(Decimal(str(totals["BYN"])) == Decimal("700.00"), "BYN total is correct")
        self._assert(Decimal(str(totals["USD"])) == Decimal("500.00"), "USD total is correct")

    def _check_expenses(self, car_id, employee_tg_id):
        expenses = self._api("get", "/api/expenses/", expected=200, query={"car_id": car_id})
        self._assert(len(expenses) == 2, "Two expenses returned for car")
        own = self._api("get", "/api/expenses/", expected=200, query={"employee_telegram_id": employee_tg_id})
        self._assert(any(expense["car_id"] == car_id for expense in own), "Employee own expenses returned")

    def _check_summary(self, car_id):
        rows = self._api("get", "/api/reports/summary/", expected=200)
        row = next((item for item in rows if item["car_id"] == car_id), None)
        self._assert(row is not None, "Summary contains smoke car")
        self._assert("BYN" in row["total_expenses_by_currency"], "Summary has BYN total")
        self._assert("USD" in row["total_expenses_by_currency"], "Summary has USD total")

    def _check_quick_expense(self, car_id, employee_tg_id):
        single = parse_expense_items("замена колодок 200")
        self._assert(len(single) == 1, "Single quick expense text is parsed")
        self._assert(single[0]["description"] == "замена колодок", "Quick expense description parsed")
        self._assert(single[0]["amount"] == "200", "Quick expense amount parsed")
        reversed_single = parse_expense_items("70 яндекс")
        self._assert(reversed_single == [{"description": "яндекс", "amount": "70"}], "Reverse quick expense text is parsed")

        batch = parse_expense_items("Покраска крыла 450, покраска бампера 800, покраска внутрянки 450")
        self._assert(len(batch) == 3, "Batch quick expense text is parsed")
        self._assert(sum(Decimal(item["amount"]) for item in batch) == Decimal("1700"), "Batch quick expense total parsed")
        split_amount_batch = parse_expense_items("Покраска бампера переднего 750, 600\nпокраска заднего бампера")
        self._assert(
            split_amount_batch == [
                {"description": "Покраска бампера переднего", "amount": "750"},
                {"description": "покраска заднего бампера", "amount": "600"},
            ],
            "Batch quick expense parses comma amount before next description",
        )

        bulk_data = self._api(
            "post",
            "/api/expenses/bulk/",
            {
                "car_id": car_id,
                "items": batch,
                "currency": "BYN",
                "category_name": "Работа",
                "employee_telegram_id": employee_tg_id,
            },
            expected=201,
        )
        self.created_expense_ids.extend(item["id"] for item in bulk_data)
        self._assert(len(bulk_data) == 3, "Batch quick expenses saved transactionally")
        self._assert(sum(Decimal(str(item["amount"])) for item in bulk_data) == Decimal("1700.00"), "Batch quick expenses amount saved")

        data = self._api(
            "post",
            "/api/expenses/",
            {
                "car_id": car_id,
                "amount": single[0]["amount"],
                "currency": "BYN",
                "category_name": "Работа",
                "description": single[0]["description"],
                "employee_telegram_id": employee_tg_id,
            },
            expected=201,
        )
        self.created_expense_ids.append(data["id"])
        self._assert(data["description"] == "замена колодок", "Quick expense saved")
        self._assert(Decimal(str(data["amount"])) == Decimal("200"), "Quick expense amount saved")
        return data

    def _check_status_restriction(self, car_id, employee_tg_id):
        data = self._api("patch", f"/api/cars/{car_id}/", {"status": Car.Status.COMPLETED}, expected=200)
        self._assert(data["status"] == Car.Status.COMPLETED, "Car completed")
        self._api(
            "post",
            "/api/expenses/",
            {
                "car_id": car_id,
                "amount": "1.00",
                "currency": "BYN",
                "category_name": "Прочее",
                "description": "Should be rejected",
                "employee_telegram_id": employee_tg_id,
            },
            expected=400,
        )
        active = self._api("get", "/api/cars/", expected=200, query={"status": Car.Status.IN_WORK})
        self._assert(not any(car["id"] == car_id for car in active), "Completed car is not active")

    def _delete_expense(self, expense_id):
        self._api("delete", f"/api/expenses/{expense_id}/", expected=204)
        self.created_expense_ids = [item for item in self.created_expense_ids if item != expense_id]
        self._assert(not Expense.objects.filter(id=expense_id).exists(), "Expense deleted")

    def _assert(self, condition, message):
        if not condition:
            raise SmokeFailure(message)
        self.stdout.write(self.style.SUCCESS(f"OK: {message}"))

    def _cleanup(self):
        if self.keep_data:
            return
        CarPhoto.objects.filter(car_id__in=self.created_car_ids).delete()
        ExpensePhoto.objects.filter(expense_id__in=self.created_expense_ids).delete()
        DefectPhoto.objects.filter(id__in=self.created_defect_photo_ids).delete()
        Expense.objects.filter(id__in=self.created_expense_ids).delete()
        Car.objects.filter(id__in=self.created_car_ids).delete()
        TelegramUser.objects.filter(id__in=self.created_user_ids).delete()
