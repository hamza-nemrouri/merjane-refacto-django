# orders/tests/test_product_rules.py

import unittest
from datetime import date, timedelta

from orders.entities.product import Product
from orders.services.product_rules import (
    EXPIRABLE,
    NORMAL,
    SEASONAL,
    ProductRule,
    is_expired,
    is_in_season,
    rule_for,
)

TODAY = date(2026, 10, 2)


class FakeProductRepository:
    def __init__(self):
        self.saved = []

    def save(self, product):
        self.saved.append(product)


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send_delay_notification(self, lead_time, product_name):
        self.calls.append(("delay", lead_time, product_name))

    def send_out_of_stock_notification(self, product_name):
        self.calls.append(("out_of_stock", product_name))

    def send_expiry_notification(self, product_name):
        self.calls.append(("expiry", product_name))


class RuleTestCase(unittest.TestCase):
    def setUp(self):
        self.products = FakeProductRepository()
        self.notifier = FakeNotifier()

    def apply(self, product):
        rule_for(product.type, self.products, self.notifier, TODAY).apply(product)


class NormalProductTests(RuleTestCase):
    def test_in_stock_is_sold(self):
        p = Product(name="USB Cable", type=NORMAL, available=3, lead_time=30)

        self.apply(p)

        self.assertEqual(2, p.available)
        self.assertEqual([p], self.products.saved)
        self.assertEqual([], self.notifier.calls)

    def test_out_of_stock_announces_the_delay(self):
        p = Product(name="USB Cable", type=NORMAL, available=0, lead_time=15)

        self.apply(p)

        self.assertEqual([("delay", 15, "USB Cable")], self.notifier.calls)

    def test_out_of_stock_with_no_lead_time_says_nothing(self):
        p = Product(name="USB Dongle", type=NORMAL, available=0, lead_time=0)

        self.apply(p)

        self.assertEqual(0, p.available)
        self.assertEqual([], self.notifier.calls)
        self.assertEqual([], self.products.saved)


class SeasonalProductTests(RuleTestCase):
    def seasonal(self, available, start_after=-2, end_after=58, lead_time=30):
        return Product(
            name="Watermelon",
            type=SEASONAL,
            available=available,
            lead_time=lead_time,
            season_start_date=TODAY + timedelta(days=start_after),
            season_end_date=TODAY + timedelta(days=end_after),
        )

    def test_in_season_and_in_stock_is_sold(self):
        p = self.seasonal(available=4)

        self.apply(p)

        self.assertEqual(3, p.available)
        self.assertEqual([], self.notifier.calls)

    def test_in_season_but_out_of_stock_announces_the_delay(self):
        p = self.seasonal(available=0)

        self.apply(p)

        self.assertEqual(0, p.available)
        self.assertEqual([("delay", 30, "Watermelon")], self.notifier.calls)

    def test_before_the_season_is_announced_without_touching_stock(self):
        p = self.seasonal(available=5, start_after=180, end_after=240)

        self.apply(p)

        self.assertEqual(5, p.available)
        self.assertEqual([("out_of_stock", "Watermelon")], self.notifier.calls)

    def test_a_delay_overrunning_the_season_empties_the_stock(self):
        p = self.seasonal(available=5, start_after=-60, end_after=-2)

        self.apply(p)

        self.assertEqual(0, p.available)
        self.assertEqual([("out_of_stock", "Watermelon")], self.notifier.calls)

    def test_missing_season_dates_fall_back_to_a_delay(self):
        p = Product(name="Watermelon", type=SEASONAL, available=5, lead_time=30)

        self.apply(p)

        self.assertEqual(5, p.available)
        self.assertEqual([("delay", 30, "Watermelon")], self.notifier.calls)


class ExpirableProductTests(RuleTestCase):
    def expirable(self, available, expires_in):
        expiry = TODAY + timedelta(days=expires_in) if expires_in is not None else None
        return Product(
            name="Butter", type=EXPIRABLE, available=available, lead_time=30, expiry_date=expiry
        )

    def test_unexpired_and_in_stock_is_sold(self):
        p = self.expirable(available=6, expires_in=26)

        self.apply(p)

        self.assertEqual(5, p.available)
        self.assertEqual([], self.notifier.calls)

    def test_expired_is_emptied_and_announced(self):
        p = self.expirable(available=90, expires_in=-2)

        self.apply(p)

        self.assertEqual(0, p.available)
        self.assertEqual([("expiry", "Butter")], self.notifier.calls)

    def test_expiring_today_counts_as_expired(self):
        p = self.expirable(available=90, expires_in=0)

        self.apply(p)

        self.assertEqual([("expiry", "Butter")], self.notifier.calls)

    def test_unexpired_but_out_of_stock_is_announced_as_expired(self):
        p = self.expirable(available=0, expires_in=26)

        self.apply(p)

        self.assertEqual([("expiry", "Butter")], self.notifier.calls)

    def test_no_expiry_date_never_expires(self):
        p = self.expirable(available=2, expires_in=None)

        self.apply(p)

        self.assertEqual(1, p.available)
        self.assertEqual([], self.notifier.calls)


class UnknownTypeTests(RuleTestCase):
    def test_an_unknown_type_is_ignored(self):
        p = Product(name="Mystery", type="WHATEVER", available=5, lead_time=10)

        self.apply(p)

        self.assertEqual(5, p.available)
        self.assertEqual([], self.notifier.calls)
        self.assertEqual([], self.products.saved)

    def test_the_base_rule_must_be_subclassed(self):
        rule = ProductRule(products=self.products, notifier=self.notifier, today=TODAY)

        with self.assertRaises(NotImplementedError):
            rule.apply(Product(name="Mystery", type=NORMAL, available=1))


class PredicateTests(unittest.TestCase):
    def test_the_season_window_excludes_its_bounds(self):
        p = Product(
            name="Watermelon",
            type=SEASONAL,
            season_start_date=TODAY - timedelta(days=10),
            season_end_date=TODAY + timedelta(days=10),
        )

        self.assertTrue(is_in_season(p, TODAY))
        self.assertFalse(is_in_season(p, p.season_start_date))
        self.assertFalse(is_in_season(p, p.season_end_date))

    def test_missing_dates_are_not_in_season_and_not_expired(self):
        p = Product(name="Watermelon", type=SEASONAL)

        self.assertFalse(is_in_season(p, TODAY))
        self.assertFalse(is_expired(p, TODAY))


if __name__ == '__main__':
    unittest.main()
