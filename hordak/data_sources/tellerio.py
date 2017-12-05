from uuid import UUID

import requests
from django.db import transaction

from hordak.models.core import StatementImport, StatementLine


@transaction.atomic()
def do_import(token, account_uuid, bank_account):
    """Import data from teller.io

    Returns the created StatementImport
    """
    data = requests.get(
        url='https://api.teller.io/accounts/{}/transactions'.format(account_uuid),
        headers={'Authorization': 'Bearer {}'.format(token)}
    ).json()

    statement_import = StatementImport.objects.create(
        source='teller.io',
        extra={'account_uuid': account_uuid},
        bank_account=bank_account,
    )

    for line_data in data:
        uuid = UUID(hex=line_data['id'])
        if StatementLine.objects.filter(uuid=uuid):
            continue

        description = ', '.join(filter(bool, [line_data['counterparty'], line_data['description']]))

        StatementLine.objects.create(
            uuid=uuid,
            date=line_data['date'],
            statement_import=statement_import,
            amount=line_data['amount'],
            description=description,
            source_data=line_data,
        )
