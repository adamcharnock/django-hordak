import string

from hordak.exceptions import NoMoreAccountCodesAvailableInSequence


class AccountCodeGenerator:
    """Generate the next account codes in sequence"""

    def __init__(self, start_at: str, alpha=False):
        """Generate account codes in sequence starting at start_at

        Account codes will be generated with the length of the `start_at` string.
        For example, when `start_at="00"`, this generator will generate account
        codes up to `99` (or `ZZ` when `alpha=True`).

        Set `alpha` to `True` to include the characters A-Z when generating account codes.
        The progression will be in the form: 18, 19, 1A, 1B
        """
        self.chars = string.digits
        if alpha:
            self.chars += string.ascii_uppercase

        self.start_at = start_at.upper()
        self.base = len(self.chars)
        self.reset_iterator()

    def reset_iterator(self):
        self.current = self._to_list(self.start_at)

    def _to_list(self, value: str) -> list[int]:
        return [self.chars.index(v) for v in value]

    def _to_str(self, value: list[int]) -> str:
        return "".join([self.chars[i] for i in value])

    def __next__(self):
        self.current[-1] += 1
        for i, _ in reversed(list(enumerate(self.current))):
            if self.current[i] >= self.base:
                if i == 0:
                    raise StopIteration()
                self.current[i] = 0
                self.current[i - 1] += 1

        return self._to_str(self.current)

    def __iter__(self):
        self.reset_iterator()
        return self


def get_next_account_code(account_code: str, alpha=False):
    try:
        return next(AccountCodeGenerator(start_at=account_code, alpha=alpha))
    except StopIteration:
        raise NoMoreAccountCodesAvailableInSequence()
