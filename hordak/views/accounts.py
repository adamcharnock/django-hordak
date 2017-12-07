from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls.base import reverse_lazy
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView

from hordak.models import Account, Leg
from hordak.forms import accounts as account_forms


class AccountListView(LoginRequiredMixin, ListView):
    """View for listing accounts

    Examples:

        .. code-block:: python

            urlpatterns = [
                ...
                url(r'^accounts/$', AccountListView.as_view(), name='accounts_list'),
            ]

    """
    model = Account
    template_name = 'hordak/accounts/account_list.html'
    context_object_name = 'accounts'


class AccountCreateView(LoginRequiredMixin, CreateView):
    """View for creating accounts

    Examples:

        .. code-block:: python

            urlpatterns = [
                ...
                url(r'^accounts/create/$', AccountCreateView.as_view(success_url=reverse_lazy('accounts_list')), name='accounts_create'),
            ]

    """
    form_class = account_forms.AccountForm
    template_name = 'hordak/accounts/account_create.html'
    success_url = reverse_lazy('hordak:accounts_list')


class AccountUpdateView(LoginRequiredMixin, UpdateView):
    """View for updating accounts

    Note that :class:`hordak.forms.AccountForm` prevents updating of the ``currency``
    and ``type`` fields. Also note that this view expects to receive the Account's
    ``uuid`` field in the URL (see example below).

    Examples:

        .. code-block:: python

            urlpatterns = [
                ...
                url(r'^accounts/update/(?P<uuid>.+)/$', AccountUpdateView.as_view(success_url=reverse_lazy('accounts_list')), name='accounts_update'),
            ]

    """
    model = Account
    form_class = account_forms.AccountForm
    template_name = 'hordak/accounts/account_update.html'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    context_object_name = 'account'
    success_url = reverse_lazy('hordak:accounts_list')


class AccountTransactionsView(LoginRequiredMixin, SingleObjectMixin, ListView):
    template_name = 'hordak/accounts/account_transactions.html'
    model = Leg
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(AccountTransactionsView, self).get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = Account.objects.all()
        return super(AccountTransactionsView, self).get_object(queryset)

    def get_context_object_name(self, obj):
        return 'legs' if hasattr(obj, '__iter__') else 'account'

    def get_queryset(self):
        queryset = super(AccountTransactionsView, self).get_queryset()
        queryset = Leg.objects.filter(account=self.object).order_by('-transaction__date', '-pk').select_related('transaction')
        return queryset
