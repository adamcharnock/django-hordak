from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView

from hordak.models import Account
from hordak.forms import accounts as account_forms


class AccountListView(ListView):
    model = Account
    template_name = 'hordak/accounts/account_list.html'
    context_object_name = 'accounts'


class AccountCreateView(CreateView):
    form_class = account_forms.AccountForm
    template_name = 'hordak/accounts/account_create.html'


class AccountUpdateView(UpdateView):
    model = Account
    form_class = account_forms.AccountForm
    template_name = 'hordak/accounts/account_update.html'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    context_object_name = 'account'


