# orders/tests/test_product_service.py

import unittest
from datetime import date, timedelta
from unittest.mock import patch

from orders.entities.product import Product
from orders.services.implementations.product_service import ProductService
from orders.services.product_rules import EXPIRABLE, NORMAL, SEASONAL

TODAY = date.today()
PATCH_PR = 'orders.services.implementations.product_service.pr'
PATCH_NS = 'orders.services.implementations.product_service.ns'


class NamedMethodTests(unittest.TestCase):
    @patch(PATCH_NS)
    @patch(PATCH_PR)
    def test_notify_delay_saves_and_announces(self, mock_pr, mock_ns):
        p = Product(name="USB Cable", type=NORMAL, available=0, lead_time=15)

        ProductService().notify_delay(15, p)

        self.assertEqual(15, p.lead_time)
        mock_pr.save.assert_called_once_with(p)
        mock_ns.send_delay_notification.assert_called_once_with(15, "USB Cable")

    @patch(PATCH_NS)
    @patch(PATCH_PR)
    def test_handle_seasonal_product_announces_an_overrun(self, mock_pr, mock_ns):
        p = Product(
            name="Watermelon",
            type=SEASONAL,
            available=0,
            lead_time=90,
            season_start_date=TODAY - timedelta(days=60),
            season_end_date=TODAY + timedelta(days=10),
        )

        ProductService().handle_seasonal_product(p)

        self.assertEqual(0, p.available)
        mock_ns.send_out_of_stock_notification.assert_called_once_with("Watermelon")

    @patch(PATCH_NS)
    @patch(PATCH_PR)
    def test_handle_expired_product_empties_the_stock(self, mock_pr, mock_ns):
        p = Product(
            name="Milk",
            type=EXPIRABLE,
            available=90,
            lead_time=6,
            expiry_date=TODAY - timedelta(days=2),
        )

        ProductService().handle_expired_product(p)

        self.assertEqual(0, p.available)
        mock_ns.send_expiry_notification.assert_called_once_with("Milk")


class HandleTests(unittest.TestCase):
    @patch(PATCH_NS)
    @patch(PATCH_PR)
    def test_handle_sells_a_sellable_product_of_every_known_type(self, mock_pr, mock_ns):
        for type_name in (NORMAL, SEASONAL, EXPIRABLE):
            with self.subTest(type_name):
                mock_pr.reset_mock()
                p = Product(
                    name="Thing",
                    type=type_name,
                    available=5,
                    lead_time=30,
                    season_start_date=TODAY - timedelta(days=1),
                    season_end_date=TODAY + timedelta(days=1),
                    expiry_date=TODAY + timedelta(days=10),
                )

                ProductService().handle(p, today=TODAY)

                self.assertEqual(4, p.available)
                mock_pr.save.assert_called_once_with(p)

    @patch(PATCH_NS)
    @patch(PATCH_PR)
    def test_handle_uses_the_day_it_is_given(self, mock_pr, mock_ns):
        p = Product(
            name="Butter",
            type=EXPIRABLE,
            available=10,
            lead_time=30,
            expiry_date=TODAY + timedelta(days=1),
        )

        ProductService().handle(p, today=TODAY + timedelta(days=5))

        self.assertEqual(0, p.available)
        mock_ns.send_expiry_notification.assert_called_once_with("Butter")

    @patch(PATCH_NS)
    @patch(PATCH_PR)
    def test_handle_ignores_a_type_it_does_not_know(self, mock_pr, mock_ns):
        p = Product(name="Mystery", type="WHATEVER", available=5, lead_time=10)

        ProductService().handle(p, today=TODAY)

        self.assertEqual(5, p.available)
        mock_pr.save.assert_not_called()
        self.assertEqual([], mock_ns.method_calls)


if __name__ == '__main__':
    unittest.main()
