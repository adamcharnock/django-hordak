from django.conf.urls import url, include

from hordak.views import accounts, statement_csv_import
from hordak.views import transactions

app_name = "hordak"

urlpatterns = [
    url(
        r"^transactions/create/$",
        transactions.TransactionCreateView.as_view(),
        name="transactions_create",
    ),
    url(
        r"^transactions/(?P<uuid>.+)/delete/$",
        transactions.TransactionDeleteView.as_view(),
        name="transactions_delete",
    ),
    url(
        r"^transactions/currency/$", transactions.CurrencyTradeView.as_view(), name="currency_trade"
    ),
    url(
        r"^transactions/reconcile/$",
        transactions.TransactionsReconcileView.as_view(),
        name="transactions_reconcile",
    ),
    url(
        r"^transactions/list/$",
        transactions.TransactionsListView.as_view(),
        name="transactions_list",
    ),
    url(r"^transactions/legs/$", transactions.LegsListView.as_view(), name="legs_list"),
    url(
        r"^statement-line/(?P<uuid>.+)/unreconcile/$",
        transactions.UnreconcileView.as_view(),
        name="transactions_unreconcile",
    ),
    url(r"^$", accounts.AccountListView.as_view(), name="accounts_list"),
    url(r"^accounts/create/$", accounts.AccountCreateView.as_view(), name="accounts_create"),
    url(
        r"^accounts/update/(?P<uuid>.+)/$",
        accounts.AccountUpdateView.as_view(),
        name="accounts_update",
    ),
    url(
        r"^accounts/(?P<uuid>.+)/$",
        accounts.AccountTransactionsView.as_view(),
        name="accounts_transactions",
    ),
    url(r"^import/$", statement_csv_import.CreateImportView.as_view(), name="import_create"),
    url(
        r"^import/(?P<uuid>.*)/setup/$",
        statement_csv_import.SetupImportView.as_view(),
        name="import_setup",
    ),
    url(
        r"^import/(?P<uuid>.*)/dry-run/$",
        statement_csv_import.DryRunImportView.as_view(),
        name="import_dry_run",
    ),
    url(
        r"^import/(?P<uuid>.*)/run/$",
        statement_csv_import.ExecuteImportView.as_view(),
        name="import_execute",
    ),
]

# Also add in the authentication views that we need to login/logout etc
urlpatterns += [url(r"^auth/", include("django.contrib.auth.urls"))]
