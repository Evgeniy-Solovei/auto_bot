# Generated manually for the project MVP.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Название")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создана")),
            ],
            options={
                "verbose_name": "Категория расхода",
                "verbose_name_plural": "Категории расходов",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="TelegramUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("telegram_id", models.BigIntegerField(unique=True, verbose_name="Telegram ID")),
                ("username", models.CharField(blank=True, max_length=150, verbose_name="Username")),
                ("full_name", models.CharField(blank=True, max_length=255, verbose_name="Имя")),
                (
                    "role",
                    models.CharField(
                        choices=[("employee", "Сотрудник"), ("owner", "Владелец"), ("admin", "Администратор")],
                        default="employee",
                        max_length=20,
                        verbose_name="Роль",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлен")),
            ],
            options={
                "verbose_name": "Пользователь Telegram",
                "verbose_name_plural": "Пользователи Telegram",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Car",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255, verbose_name="Название / описание")),
                ("make_model", models.CharField(blank=True, max_length=255, verbose_name="Марка и модель")),
                ("vin", models.CharField(blank=True, max_length=32, verbose_name="VIN")),
                (
                    "status",
                    models.CharField(
                        choices=[("in_work", "В работе"), ("completed", "Завершен"), ("archived", "Архив")],
                        default="in_work",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                ("description", models.TextField(blank=True, verbose_name="Комментарий")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлен")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="Дата завершения")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cars",
                        to="core.telegramuser",
                        verbose_name="Добавил",
                    ),
                ),
            ],
            options={
                "verbose_name": "Автомобиль / заказ",
                "verbose_name_plural": "Автомобили / заказы",
                "ordering": ["status", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Expense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Сумма")),
                ("description", models.CharField(max_length=255, verbose_name="Описание")),
                ("comment", models.TextField(blank=True, verbose_name="Комментарий")),
                ("receipt_photo_file_id", models.CharField(blank=True, max_length=255, verbose_name="Telegram file_id фото чека")),
                ("spent_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Дата расхода")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлен")),
                (
                    "car",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="expenses", to="core.car", verbose_name="Автомобиль"),
                ),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="expenses",
                        to="core.expensecategory",
                        verbose_name="Категория",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="expenses",
                        to="core.telegramuser",
                        verbose_name="Сотрудник",
                    ),
                ),
            ],
            options={
                "verbose_name": "Расход",
                "verbose_name_plural": "Расходы",
                "ordering": ["-spent_at", "-created_at"],
            },
        ),
        migrations.AddIndex(model_name="car", index=models.Index(fields=["status", "-created_at"], name="core_car_status_554294_idx")),
        migrations.AddIndex(model_name="car", index=models.Index(fields=["vin"], name="core_car_vin_bf8a75_idx")),
        migrations.AddIndex(model_name="expense", index=models.Index(fields=["car", "-spent_at"], name="core_expens_car_id_6076ef_idx")),
        migrations.AddIndex(model_name="expense", index=models.Index(fields=["category"], name="core_expens_categor_2ec09b_idx")),
        migrations.AddIndex(model_name="expense", index=models.Index(fields=["employee"], name="core_expens_employe_70da07_idx")),
    ]
