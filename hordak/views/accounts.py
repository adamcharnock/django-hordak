from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView

from hordak.models import Account
from hordak.forms import accounts as account_forms


class AccountListView(ListView):
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


class AccountCreateView(CreateView):
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


class AccountUpdateView(UpdateView):
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


