from django.conf.urls import url

from hordak.views import accounts
from hordak.views import transactions

app_name = 'hordak'

urlpatterns = [
    url(r'^transactions/create/$', transactions.TransactionCreateView.as_view(), name='transactions_create'),
    url(r'^transactions/reconcile/$', transactions.TransactionsReconcileView.as_view(), name='transactions_reconcile'),
    url(r'^$', accounts.AccountListView.as_view(), name='accounts_list'),
    url(r'^accounts/create/$', accounts.AccountCreateView.as_view(), name='accounts_create'),
    url(r'^accounts/update/(?P<uuid>.+)/$', accounts.AccountUpdateView.as_view(), name='accounts_update'),
    url(r'^accounts/(?P<uuid>.+)/$', accounts.AccountTransactionsView.as_view(), name='accounts_transactions'),
]
