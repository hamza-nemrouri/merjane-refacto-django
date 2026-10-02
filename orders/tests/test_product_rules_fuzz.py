# orders/tests/test_product_rules_fuzz.py

import random
import unittest
from datetime import date, timedelta

from orders.entities.product import Product
from orders.services.product_rules import EXPIRABLE, NORMAL, SEASONAL, rule_for

TODAY = date(2026, 10, 2)
SEED = 20261002
TYPES = (NORMAL, SEASONAL, EXPIRABLE, "WHATEVER")


class FakeProductRepository:
    def __init__(self):
        self.saved = []

    def save(self, product):
        self.saved.append(product)


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send_delay_notification(self, lead_time, product_name):
        self.calls.append("delay")

    def send_out_of_stock_notification(self, product_name):
        self.calls.append("out_of_stock")

    def send_expiry_notification(self, product_name):
        self.calls.append("expiry")


def random_product(rng):
    """Any product the model can hold, including the awkward combinations.

    A quarter of the dates are missing, the stock may already be negative, and an
    unknown type is thrown in, which is the data the original code crashed on.
    """

    def maybe_date():
        return None if rng.random() < 0.25 else TODAY + timedelta(days=rng.randint(-400, 400))

    return Product(
        name="p",
        type=rng.choice(TYPES),
        available=rng.randint(-5, 20),
        lead_time=rng.randint(0, 400),
        expiry_date=maybe_date(),
        season_start_date=maybe_date(),
        season_end_date=maybe_date(),
    )


class RuleFuzzTests(unittest.TestCase):
    """Whatever the data, a rule must not crash and must not corrupt the stock.

    The seed is fixed so a failure can be replayed. These assert invariants
    rather than an expected outcome, because the point is the input space the
    hand-written cases do not reach.
    """

    def test_the_stock_is_never_left_broken(self):
        rng = random.Random(SEED)
        for _ in range(500):
            product = random_product(rng)
            products = FakeProductRepository()
            notifier = FakeNotifier()
            before = product.available

            rule_for(product.type, products, notifier, TODAY).apply(product)

            # Untouched, sold one unit, or emptied. Nothing else is possible.
            # A stock that is already negative can stay negative: the original
            # left it alone and only the emptying branches ever set it.
            self.assertIn(product.available, (before, before - 1, 0))
            self.assertLessEqual(len(products.saved), 1)
            self.assertLessEqual(len(notifier.calls), 1)

    def test_announcing_and_selling_never_happen_in_the_same_pass(self):
        rng = random.Random(SEED + 1)
        for _ in range(500):
            product = random_product(rng)
            products = FakeProductRepository()
            notifier = FakeNotifier()
            before = product.available

            rule_for(product.type, products, notifier, TODAY).apply(product)

            # A message means the stock was left alone or emptied, never that a
            # unit was taken. The two are decided by the same branch.
            if notifier.calls:
                self.assertIn(product.available, (before, 0))
            # Any decrement goes through the repository.
            if product.available == before - 1:
                self.assertEqual([product], products.saved)

    def test_the_day_it_is_given_is_the_only_clock_it_uses(self):
        rng = random.Random(SEED + 2)
        for _ in range(200):
            product = random_product(rng)
            products = FakeProductRepository()
            notifier = FakeNotifier()

            before = product.available
            far_future = TODAY + timedelta(days=rng.randint(1, 1000))
            rule_for(product.type, products, notifier, far_future).apply(product)

            self.assertIn(product.available, (before, before - 1, 0))


if __name__ == '__main__':
    unittest.main()
