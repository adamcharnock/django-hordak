from django.urls import path

from hordak.views import accounts, statement_csv_import, transactions


app_name = "hordak"

urlpatterns = [
    path(
        "transactions/create/",
        transactions.TransactionCreateView.as_view(),
        name="transactions_create",
    ),
    path(
        "transactions/<str:uuid>/delete/",
        transactions.TransactionDeleteView.as_view(),
        name="transactions_delete",
    ),
    path(
        "transactions/currency/",
        transactions.CurrencyTradeView.as_view(),
        name="currency_trade",
    ),
    path(
        "transactions/reconcile/",
        transactions.TransactionsReconcileView.as_view(),
        name="transactions_reconcile",
    ),
    path(
        "transactions/list/",
        transactions.TransactionsListView.as_view(),
        name="transactions_list",
    ),
    path("transactions/legs/", transactions.LegsListView.as_view(), name="legs_list"),
    path(
        "statement-line/<str:uuid>/unreconcile/",
        transactions.UnreconcileView.as_view(),
        name="transactions_unreconcile",
    ),
    path("", accounts.AccountListView.as_view(), name="accounts_list"),
    path(
        "accounts/create/", accounts.AccountCreateView.as_view(), name="accounts_create"
    ),
    path(
        "accounts/update/<str:uuid>/",
        accounts.AccountUpdateView.as_view(),
        name="accounts_update",
    ),
    path(
        "accounts/<str:uuid>/",
        accounts.AccountTransactionsView.as_view(),
        name="accounts_transactions",
    ),
    path(
        "import/", statement_csv_import.CreateImportView.as_view(), name="import_create"
    ),
    path(
        "import/<str:uuid>/setup/",
        statement_csv_import.SetupImportView.as_view(),
        name="import_setup",
    ),
    path(
        "import/<str:uuid>/dry-run/",
        statement_csv_import.DryRunImportView.as_view(),
        name="import_dry_run",
    ),
    path(
        "import/<str:uuid>/run/",
        statement_csv_import.ExecuteImportView.as_view(),
        name="import_execute",
    ),
]
