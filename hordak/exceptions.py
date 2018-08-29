class HordakError(Exception):
    """Abstract exception type for all Hordak errors"""

    pass


class AccountingError(HordakError):
    """Abstract exception type for errors specifically related to accounting"""

    pass


class AccountTypeOnChildNode(HordakError):
    """Raised when trying to set a type on a child account

    The type of a child account is always inferred from its root account
    """

    pass


class ZeroAmountError(HordakError):
    """Raised when a zero amount is found on a transaction leg

    Transaction leg amounts must be none zero.
    """

    pass


class AccountingEquationViolationError(AccountingError):
    """Raised if - upon checking - the accounting equation is found to be violated.

    The accounting equation is:

    0 = Liabilities + Equity + Income - Expenses - Assets

    """

    pass


class LossyCalculationError(HordakError):
    """Raised to prevent a lossy or imprecise calculation from occurring.

    Typically this may happen when trying to multiply/divide a monetary value
    by a float.
    """

    pass


class BalanceComparisonError(HordakError):
    """Raised when comparing a balance to an invalid value

    A balance must be compared against another balance or a Money instance
    """

    pass


class TradingAccountRequiredError(HordakError):
    """Raised when trying to perform a currency exchange via an account other than a 'trading' account"""

    pass


class InvalidFeeCurrency(HordakError):
    """Raised when fee currency does not match source currency"""

    pass


class CannotSimplifyError(HordakError):
    """Used internally by Currency class"""

    pass
