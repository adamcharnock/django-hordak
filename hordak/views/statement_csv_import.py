from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, UpdateView, DetailView

from hordak.forms.statement_csv_import import (
    TransactionCsvImportForm,
    TransactionCsvImportColumnFormSet,
)
from hordak.models import TransactionCsvImport
from hordak.resources import StatementLineResource


class CreateImportView(LoginRequiredMixin, CreateView):
    model = TransactionCsvImport
    form_class = TransactionCsvImportForm
    template_name = "hordak/statement_import/import_create.html"

    def get_success_url(self):
        return reverse("hordak:import_setup", args=[self.object.uuid])


class SetupImportView(LoginRequiredMixin, UpdateView):
    """View for setting up of the import process

    This involves mapping columns to import fields, and collecting
    the date format
    """

    context_object_name = "transaction_import"
    slug_url_kwarg = "uuid"
    slug_field = "uuid"
    model = TransactionCsvImport
    fields = ("date_format",)
    template_name = "hordak/statement_import/import_setup.html"

    def get_context_data(self, **kwargs):
        context = super(SetupImportView, self).get_context_data(**kwargs)
        context["formset"] = TransactionCsvImportColumnFormSet(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form_class()(request.POST, request.FILES, instance=self.object)
        formset = TransactionCsvImportColumnFormSet(request.POST, instance=self.object)

        if form.is_valid() and formset.is_valid():
            return self.form_valid(form, formset)
        else:
            return self.form_invalid(form, formset)

    def form_valid(self, form, formset):
        self.object = form.save()
        formset.instance = self.object
        formset.save()
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, formset):
        return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def get_success_url(self):
        return reverse("hordak:import_dry_run", args=[self.object.uuid])


class AbstractImportView(LoginRequiredMixin, DetailView):
    context_object_name = "transaction_import"
    slug_url_kwarg = "uuid"
    slug_field = "uuid"
    model = TransactionCsvImport
    dry_run = True

    def get(self, request, **kwargs):
        return super(AbstractImportView, self).get(request, **kwargs)

    def post(self, request, **kwargs):
        transaction_import = self.get_object()
        resource = StatementLineResource(
            date_format=transaction_import.date_format,
            statement_import=transaction_import.hordak_import,
        )

        self.result = resource.import_data(
            dataset=transaction_import.get_dataset(),
            dry_run=self.dry_run,
            use_transactions=True,
            collect_failed_rows=True,
        )
        return self.get(request, **kwargs)

    def get_context_data(self, **kwargs):
        return super(AbstractImportView, self).get_context_data(
            result=getattr(self, "result", None), **kwargs
        )


class DryRunImportView(AbstractImportView):
    template_name = "hordak/statement_import/import_dry_run.html"
    dry_run = True


class ExecuteImportView(AbstractImportView):
    template_name = "hordak/statement_import/import_execute.html"
    dry_run = False
