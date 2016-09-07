
class HordakError(Exception):
    """Abstract exception type"""
    pass


class AccountingError(HordakError):
    """Abstract exception type"""
    pass


class AccountTypeOnChildNode(HordakError):
    """Raised when trying to set a type on a child account

    The type of a child account is always inferred from its root account
    """
    pass


class ZeroAmountError(HordakError):
    """Raised when a zero amount is found on a transaction leg"""
    pass


class AccountingEquationViolationError(AccountingError):
    """Raised if - upon checking - the accounting equation is found to be violated.

    The accounting equation is:

    0 = Liabilities + Equity + Income - Expenses - Assets

    """
    pass
