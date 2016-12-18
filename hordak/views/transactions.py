from django.urls import reverse
from django.views.generic import CreateView
from hordak.forms import SimpleTransactionForm


class CreateTransactionView(CreateView):
    form_class = SimpleTransactionForm
