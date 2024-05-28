import string
from typing import List

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

    def _to_list(self, value: str) -> List[int]:
        # "0A" -> (0, 10)
        return [self.chars.index(v) for v in value]

    def _to_str(self, value: List[int]) -> str:
        # (0, 10) -> "0A"
        return "".join([self.chars[i] for i in value])

    def __next__(self):
        # Increment the right-most value
        self.current[-1] += 1
        # Now go through each value and carry over values that exceed the number base.
        # We iterate from right to left, carrying over as we go.
        for i, _ in reversed(list(enumerate(self.current))):
            if self.current[i] >= self.base:
                if i == 0:
                    # The left-most value is now too big,
                    # so we have exhausted this sequence.
                    # Stop iterating
                    raise StopIteration()

                # Otherwise, do the cary-over. Set this value to 0,
                # and add one to the value left of us
                self.current[i] = 0
                self.current[i - 1] += 1

        return self._to_str(self.current)

    def __iter__(self):
        self.reset_iterator()
        return self


def get_next_account_code(account_code: str, alpha=False):
    """Get the next account code in sequence"""
    try:
        return next(AccountCodeGenerator(start_at=account_code, alpha=alpha))
    except StopIteration:
        raise NoMoreAccountCodesAvailableInSequence()
