from uuid import UUID
import datetime

import requests
from django.db import transaction

from hordak.models.core import StatementImport, StatementLine


@transaction.atomic()
def do_import(token, account_uuid, bank_account, since=None):
    """Import data from teller.io

    Returns the created StatementImport
    """
    response = requests.get(
        url='https://api.teller.io/accounts/{}/transactions'.format(account_uuid),
        headers={'Authorization': 'Bearer {}'.format(token)}
    )
    response.raise_for_status()
    data = response.json()

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
        date = datetime.date(*map(int, line_data['date'].split('-')))

        if not since or date >= since:
            StatementLine.objects.create(
                uuid=uuid,
                date=line_data['date'],
                statement_import=statement_import,
                amount=line_data['amount'],
                type=line_data['type'],
                description=description,
                source_data=line_data,
            )
