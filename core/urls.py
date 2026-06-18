from django.urls import path

from core.api import (
    CarDetailView,
    CarListCreateView,
    CarPhotoListView,
    CategoryListView,
    DefectPhotoListCreateView,
    ExpenseBulkCreateView,
    ExpenseDetailView,
    ExpenseListCreateView,
    ExpensePhotoListView,
    ReportExportView,
    ReportSummaryView,
    TelegramUserAccessView,
    TelegramUserView,
)


urlpatterns = [
    path("telegram-users/", TelegramUserView.as_view(), name="api-telegram-users"),
    path("telegram-users/access/", TelegramUserAccessView.as_view(), name="api-telegram-user-access"),
    path("categories/", CategoryListView.as_view(), name="api-categories"),
    path("cars/", CarListCreateView.as_view(), name="api-cars"),
    path("cars/<int:pk>/", CarDetailView.as_view(), name="api-car-detail"),
    path("car-photos/", CarPhotoListView.as_view(), name="api-car-photos"),
    path("defect-photos/", DefectPhotoListCreateView.as_view(), name="api-defect-photos"),
    path("expenses/", ExpenseListCreateView.as_view(), name="api-expenses"),
    path("expenses/bulk/", ExpenseBulkCreateView.as_view(), name="api-expenses-bulk"),
    path("expenses/<int:pk>/", ExpenseDetailView.as_view(), name="api-expense-detail"),
    path("expense-photos/", ExpensePhotoListView.as_view(), name="api-expense-photos"),
    path("reports/summary/", ReportSummaryView.as_view(), name="api-report-summary"),
    path("reports/export/", ReportExportView.as_view(), name="api-report-export"),
]
