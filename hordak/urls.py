from django.conf.urls import url, include

from hordak.views import accounts, statement_import
from hordak.views import transactions

app_name = 'hordak'

urlpatterns = [
    url(r'^transactions/create/$', transactions.TransactionCreateView.as_view(), name='transactions_create'),
    url(r'^transactions/currency/$', transactions.CurrencyTradeView.as_view(), name='currency_trade'),
    url(r'^transactions/reconcile/$', transactions.TransactionsReconcileView.as_view(), name='transactions_reconcile'),
    url(r'^$', accounts.AccountListView.as_view(), name='accounts_list'),
    url(r'^accounts/create/$', accounts.AccountCreateView.as_view(), name='accounts_create'),
    url(r'^accounts/update/(?P<uuid>.+)/$', accounts.AccountUpdateView.as_view(), name='accounts_update'),
    url(r'^accounts/(?P<uuid>.+)/$', accounts.AccountTransactionsView.as_view(), name='accounts_transactions'),

    url(r'^import/$', statement_import.CreateImportView.as_view(), name='import_create'),
    url(r'^import/(?P<uuid>.*)/setup/$', statement_import.SetupImportView.as_view(), name='import_setup'),
    url(r'^import/(?P<uuid>.*)/dry-run/$', statement_import.DryRunImportView.as_view(), name='import_dry_run'),
    url(r'^import/(?P<uuid>.*)/run/$', statement_import.ExecuteImportView.as_view(), name='import_execute'),


]

# Also add in the authentication views that we need to login/logout etc
urlpatterns += [url(r'^auth/', include('django.contrib.auth.urls'))]
