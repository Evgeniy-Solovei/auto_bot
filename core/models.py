from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone


class TelegramUser(models.Model):
    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Сотрудник"
        MANAGER = "manager", "Руководитель"
        ADMIN = "admin", "Администратор"

    telegram_id = models.BigIntegerField("Telegram ID", unique=True)
    username = models.CharField("Username", max_length=150, blank=True)
    full_name = models.CharField("Имя", max_length=255, blank=True)
    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлен", auto_now=True)

    class Meta:
        verbose_name = "Пользователь Telegram"
        verbose_name_plural = "Пользователи Telegram"
        ordering = ["-created_at"]

    @property
    def is_manager(self) -> bool:
        return self.role in {self.Role.MANAGER, self.Role.ADMIN}

    def __str__(self) -> str:
        return self.full_name or self.username or str(self.telegram_id)


class ExpenseCategory(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Категория расхода"
        verbose_name_plural = "Категории расходов"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Car(models.Model):
    class Status(models.TextChoices):
        IN_WORK = "in_work", "В работе"
        COMPLETED = "completed", "Завершен"
        ARCHIVED = "archived", "Архив"

    class RepairStage(models.TextChoices):
        ACCEPTED = "accepted", "Принят в работу"
        DEFECT = "defect", "Дефектовка с фото"
        WAITING_PARTS = "waiting_parts", "Ожидание деталей"
        BODY_WORK = "body_work", "Кузовные работы"
        PAINT_ASSEMBLY = "paint_assembly", "Подготовка/покраска/сборка"
        READY = "ready", "Готов к выдаче"
        DONE = "done", "Завершен"

    title = models.CharField("Название / описание", max_length=255)
    brand = models.CharField("Марка", max_length=120, blank=True)
    model = models.CharField("Модель", max_length=120, blank=True)
    make_model = models.CharField("Марка и модель", max_length=255, blank=True)
    vin_or_plate = models.CharField("VIN / госномер", max_length=64, blank=True)
    vin = models.CharField("VIN", max_length=64, blank=True)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.IN_WORK)
    repair_stage = models.CharField("Этап ремонта", max_length=32, choices=RepairStage.choices, default=RepairStage.ACCEPTED)
    description = models.TextField("Комментарий", blank=True)
    car_photo_file_id = models.CharField("Telegram file_id фото авто", max_length=255, blank=True)
    car_photo = models.ImageField("Фото авто", upload_to="cars/", blank=True)
    created_by = models.ForeignKey(
        TelegramUser,
        verbose_name="Добавил",
        related_name="cars",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлен", auto_now=True)
    completed_at = models.DateTimeField("Дата завершения", null=True, blank=True)
    archived_at = models.DateTimeField("Дата архивации", null=True, blank=True)

    class Meta:
        verbose_name = "Автомобиль / заказ"
        verbose_name_plural = "Автомобили / заказы"
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["vin"]),
        ]

    def __str__(self) -> str:
        if self.vehicle_label:
            return f"{self.title} ({self.vehicle_label})"
        return self.title

    @property
    def vehicle_label(self) -> str:
        if self.brand or self.model:
            return " ".join(part for part in [self.brand, self.model] if part)
        return self.make_model

    @property
    def total_expenses(self) -> Decimal:
        return self.expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    def apply_status_dates(self) -> None:
        now = timezone.now()
        if self.status == self.Status.COMPLETED and not self.completed_at:
            self.completed_at = now
        if self.status != self.Status.COMPLETED:
            self.completed_at = None
        if self.status == self.Status.ARCHIVED and not self.archived_at:
            self.archived_at = now
        if self.status != self.Status.ARCHIVED:
            self.archived_at = None

    def mark_completed(self) -> None:
        self.status = self.Status.COMPLETED
        self.apply_status_dates()


class DefectPhoto(models.Model):
    car = models.ForeignKey(Car, verbose_name="Автомобиль", related_name="defect_photos", on_delete=models.CASCADE)
    photo_file_id = models.CharField("Telegram file_id фото дефектовки", max_length=255, blank=True)
    image = models.ImageField("Фото дефектовки", upload_to="defect_photos/", blank=True)
    comment = models.TextField("Комментарий", blank=True)
    created_by = models.ForeignKey(
        TelegramUser,
        verbose_name="Добавил",
        related_name="defect_photos",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Фото дефектовки"
        verbose_name_plural = "Фото дефектовки"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["car", "-created_at"])]

    def __str__(self) -> str:
        return f"Фото дефектовки #{self.id} - {self.car}"


class Expense(models.Model):
    car = models.ForeignKey(Car, verbose_name="Автомобиль", related_name="expenses", on_delete=models.CASCADE)
    amount = models.DecimalField("Сумма", max_digits=12, decimal_places=2)
    currency = models.CharField("Валюта", max_length=8, default="BYN")
    description = models.CharField("Описание", max_length=255)
    category = models.ForeignKey(
        ExpenseCategory,
        verbose_name="Категория",
        related_name="expenses",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    employee = models.ForeignKey(
        TelegramUser,
        verbose_name="Сотрудник",
        related_name="expenses",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        TelegramUser,
        verbose_name="Изменил",
        related_name="updated_expenses",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    comment = models.TextField("Комментарий", blank=True)
    receipt_photo_file_id = models.CharField("Telegram file_id фото чека", max_length=255, blank=True)
    receipt_photo = models.ImageField("Фото расхода / чека", upload_to="expense_receipts/", blank=True)
    spent_at = models.DateTimeField("Дата расхода", default=timezone.now)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлен", auto_now=True)

    class Meta:
        verbose_name = "Расход"
        verbose_name_plural = "Расходы"
        ordering = ["-spent_at", "-created_at"]
        indexes = [
            models.Index(fields=["car", "-spent_at"]),
            models.Index(fields=["category"]),
            models.Index(fields=["employee"]),
        ]

    def __str__(self) -> str:
        return f"{self.description} - {self.amount} {self.currency}"
