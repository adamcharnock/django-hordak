from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction as db_transaction
from django.http import Http404
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import CreateView, ListView, DeleteView

from hordak.forms import SimpleTransactionForm, TransactionForm, LegFormSet
from hordak.forms.transactions import CurrencyTradeForm
from hordak.models import StatementLine, Leg, Transaction


class TransactionCreateView(LoginRequiredMixin, CreateView):
    """ View for creation of simple transactions.

    This functionality is provided by :class:`hordak.models.Account.transfer_to()`,
    see the method's documentation for additional details.

    Examples:

        .. code-block:: python

            urlpatterns = [
                ...
                url(r'^transactions/create/$', TransactionCreateView.as_view(), name='transactions_create'),
            ]
    """

    form_class = SimpleTransactionForm
    success_url = reverse_lazy("hordak:accounts_list")
    template_name = "hordak/transactions/transaction_create.html"


class CurrencyTradeView(LoginRequiredMixin, CreateView):
    form_class = CurrencyTradeForm
    success_url = reverse_lazy("hordak:accounts_list")
    template_name = "hordak/transactions/currency_trade.html"

    def get_form_kwargs(self):
        kwargs = super(CurrencyTradeView, self).get_form_kwargs()
        kwargs.pop("instance")
        return kwargs


class TransactionsListView(LoginRequiredMixin, ListView):
    """View for listing transactions

    """

    model = Transaction
    template_name = "hordak/transactions/transaction_list.html"
    context_object_name = "transactions"
    ordering = ["-date", "-pk"]


class LegsListView(LoginRequiredMixin, ListView):
    """View for listing legs

    """

    model = Leg
    template_name = "hordak/transactions/leg_list.html"
    context_object_name = "legs"
    ordering = ["-transaction__date", "-transaction__pk", "-pk"]


class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    slug_url_kwarg = "uuid"
    slug_field = "uuid"
    template_name = "hordak/transactions/transaction_delete.html"
    context_object_name = "transaction"
    success_url = reverse_lazy("hordak:accounts_list")


class TransactionsReconcileView(LoginRequiredMixin, ListView):
    """ Handle rendering and processing in the reconciliation view

    Note that this only extends ListView, and we implement the form
    processing functionality manually.

    Examples:

        .. code-block:: python

            urlpatterns = [
                ...
                url(r'^transactions/reconcile/$', TransactionsReconcileView.as_view(), name='transactions_reconcile'),
            ]
    """

    template_name = "hordak/transactions/reconcile.html"
    model = StatementLine
    paginate_by = 50
    context_object_name = "statement_lines"
    ordering = ["-date", "-pk"]
    success_url = reverse_lazy("hordak:accounts_list")

    def get_uuid(self):
        return self.request.POST.get("reconcile") or self.request.GET.get("reconcile")

    def get_object(self, queryset=None):
        # Get any Statement Line instance that was specified
        if queryset is None:
            queryset = self.get_queryset()

        uuid = self.get_uuid()
        if not uuid:
            return None

        queryset = queryset.filter(uuid=uuid, transaction=None)
        try:
            obj = queryset.get()
        except queryset.model.DoesNotExist:
            raise Http404("No unreconciled statement line found for {}".format(uuid))

        return obj

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(TransactionsReconcileView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Make sure the ListView gets setup
        self.get(self.request, *self.args, **self.kwargs)

        # Check form validity
        transaction_form = self.get_transaction_form()
        leg_formset = self.get_leg_formset()

        if transaction_form.is_valid() and leg_formset.is_valid():
            return self.form_valid(transaction_form, leg_formset)
        else:
            return self.form_invalid(transaction_form, leg_formset)

    def form_valid(self, transaction_form, leg_formset):

        with db_transaction.atomic():
            # Save the transaction
            transaction_form.instance.date = self.object.date
            transaction = transaction_form.save()

            # Create the inbound transaction leg
            bank_account = self.object.statement_import.bank_account
            amount = self.object.amount * -1
            Leg.objects.create(
                transaction=transaction,
                account=bank_account,
                amount=amount,
                # Note that bank accounts can only have one currency
                amount_currency=bank_account.currencies[0],
            )

            # We need to create a new leg formset in order to pass in the
            # transaction we just created (required as the new legs must
            # be associated with the new transaction)
            leg_formset = self.get_leg_formset(instance=transaction)
            assert leg_formset.is_valid()
            leg_formset.save()

            # Now point the statement line to the new transaction
            self.object.transaction = transaction
            self.object.save()

        self.object = None
        return self.render_to_response(self.get_context_data())

    def form_invalid(self, transaction_form, leg_formset):
        return self.render_to_response(
            self.get_context_data(transaction_form=transaction_form, leg_formset=leg_formset)
        )

    def get_context_data(self, **kwargs):
        # If a Statement Line has been selected for reconciliation,
        # then add the forms to the context
        if self.object:
            kwargs.update(
                transaction_form=self.get_transaction_form(),
                leg_formset=self.get_leg_formset(),
                reconcile_line=self.object,
            )
        return super(TransactionsReconcileView, self).get_context_data(**kwargs)

    def get_transaction_form(self):
        return TransactionForm(
            data=self.request.POST or None, initial=dict(description=self.object.description)
        )

    def get_leg_formset(self, **kwargs):
        return LegFormSet(data=self.request.POST or None, statement_line=self.object, **kwargs)


class UnreconcileView(LoginRequiredMixin, View):
    def post(self, request, uuid):
        statement_line = get_object_or_404(StatementLine, uuid=uuid)
        statement_line.transaction.delete()
        return HttpResponseRedirect(reverse("hordak:transactions_reconcile"))
