from unittest import TestCase

from hordak.exceptions import NoMoreAccountCodesAvailableInSequence
from hordak.utilities.account_codes import AccountCodeGenerator, get_next_account_code


class AccountCodesTestCase(TestCase):
    def test_account_code_generator_simple(self):
        generator = AccountCodeGenerator(start_at="7")
        self.assertEqual(list(generator), ["8", "9"])

    def test_account_code_generator_alpha(self):
        generator = AccountCodeGenerator(
            start_at="X",
            alpha=True,
        )
        self.assertEqual(list(generator), ["Y", "Z"])

    def test_account_code_generator_full_run(self):
        generator = AccountCodeGenerator(
            start_at="00",
            alpha=True,
        )
        results = list(generator)
        self.assertEqual(len(results), 36**2 - 1)
        self.assertEqual(results[0], "01")
        self.assertEqual(results[-1], "ZZ")

    def test_get_next_account_code_simple(self):
        self.assertEqual(get_next_account_code("84"), "85")

    def test_get_next_account_code_alpha(self):
        self.assertEqual(get_next_account_code("9Z", alpha=True), "A0")

    def test_get_next_account_code_end_of_sequence(self):
        with self.assertRaises(NoMoreAccountCodesAvailableInSequence):
            get_next_account_code("99")
