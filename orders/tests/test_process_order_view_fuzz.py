# orders/tests/test_process_order_view_fuzz.py

import random
import unittest
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from orders.entities.order import Order
from orders.entities.product import Product

TODAY = date.today()
SEED = 20261002
TYPES = ("NORMAL", "SEASONAL", "EXPIRABLE", "WHATEVER")


def random_product(rng, index):
    def maybe_date():
        return None if rng.random() < 0.25 else TODAY + timedelta(days=rng.randint(-400, 400))

    return Product(
        name="p%d" % index,
        type=rng.choice(TYPES),
        available=rng.randint(-5, 20),
        lead_time=rng.randint(0, 400),
        expiry_date=maybe_date(),
        season_start_date=maybe_date(),
        season_end_date=maybe_date(),
    )


class EndpointFuzzTests(TestCase):
    """Random orders through the real URL, checked against the stored rows."""

    def post(self, order_id):
        return self.client.post(
            reverse('process_order', args=[order_id]), content_type='application/json'
        )

    def test_random_orders_are_processed_without_corrupting_stock(self):
        rng = random.Random(SEED)
        for case in range(25):
            with self.subTest(case=case):
                products = [random_product(rng, i) for i in range(rng.randint(1, 6))]
                for product in products:
                    product.save()
                before = {p.pk: p.available for p in products}
                order = Order.objects.create()
                order.products.set(products)

                response = self.post(order.id)

                self.assertEqual(200, response.status_code)
                self.assertEqual({'id': order.id}, response.json())
                for product in products:
                    stored = Product.objects.get(pk=product.pk)
                    self.assertIn(
                        stored.available,
                        (before[product.pk], before[product.pk] - 1, 0),
                    )

    def test_an_order_id_that_does_not_exist_is_always_a_404(self):
        rng = random.Random(SEED + 1)
        for _ in range(20):
            response = self.post(rng.randint(900000, 999999))

            self.assertEqual(404, response.status_code)


if __name__ == '__main__':
    unittest.main()
