
class AccountTypeOnLeafNode(Exception):
    """Raised when trying to set a type on a child account

    The type of a child account is always inferred from its root account
    """
    pass
