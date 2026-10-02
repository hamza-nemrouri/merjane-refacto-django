# orders/tests/test_process_order_view.py

from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from orders.entities.order import Order
from orders.entities.product import Product
from orders.services.product_rules import EXPIRABLE, NORMAL, SEASONAL

IN_SEASON = {
    "season_start_date": date.today() - timedelta(days=2),
    "season_end_date": date.today() + timedelta(days=58),
}


class ProcessOrderEndpointTests(TestCase):
    def post(self, order_id):
        return self.client.post(
            reverse('process_order', args=[order_id]), content_type='application/json'
        )

    def stored(self, product):
        return Product.objects.get(pk=product.pk).available

    def make(self, order, **fields):
        product = Product.objects.create(**fields)
        order.products.add(product)
        return product

    def test_a_normal_product_in_stock_loses_one_unit(self):
        order = Order.objects.create()
        cable = self.make(order, name="USB Cable", type=NORMAL, available=15, lead_time=30)

        response = self.post(order.id)

        self.assertEqual(200, response.status_code)
        self.assertEqual({'id': order.id}, response.json())
        self.assertEqual(14, self.stored(cable))

    def test_an_out_of_stock_normal_product_stays_at_zero(self):
        order = Order.objects.create()
        dongle = self.make(order, name="USB Dongle", type=NORMAL, available=0, lead_time=30)

        response = self.post(order.id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, self.stored(dongle))

    def test_a_seasonal_product_in_season_loses_one_unit(self):
        order = Order.objects.create()
        melon = self.make(
            order, name="Watermelon", type=SEASONAL, available=15, lead_time=30, **IN_SEASON
        )

        response = self.post(order.id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(14, self.stored(melon))

    def test_a_seasonal_product_before_its_season_keeps_its_stock(self):
        order = Order.objects.create()
        grapes = self.make(
            order,
            name="Grapes",
            type=SEASONAL,
            available=15,
            lead_time=30,
            season_start_date=date.today() + timedelta(days=180),
            season_end_date=date.today() + timedelta(days=240),
        )

        response = self.post(order.id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(15, self.stored(grapes))

    def test_a_seasonal_product_whose_delay_overruns_the_season_is_emptied(self):
        order = Order.objects.create()
        grapes = self.make(
            order,
            name="Grapes",
            type=SEASONAL,
            available=5,
            lead_time=30,
            season_start_date=date.today() - timedelta(days=60),
            season_end_date=date.today() - timedelta(days=2),
        )

        response = self.post(order.id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, self.stored(grapes))

    def test_an_expired_product_is_emptied(self):
        order = Order.objects.create()
        milk = self.make(
            order,
            name="Milk",
            type=EXPIRABLE,
            available=90,
            lead_time=6,
            expiry_date=date.today() - timedelta(days=2),
        )

        response = self.post(order.id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, self.stored(milk))

    def test_an_unexpired_product_loses_one_unit(self):
        order = Order.objects.create()
        butter = self.make(
            order,
            name="Butter",
            type=EXPIRABLE,
            available=15,
            lead_time=30,
            expiry_date=date.today() + timedelta(days=26),
        )

        response = self.post(order.id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(14, self.stored(butter))

    def test_an_order_can_mix_types(self):
        order = Order.objects.create()
        cable = self.make(order, name="USB Cable", type=NORMAL, available=15, lead_time=30)
        butter = self.make(
            order,
            name="Butter",
            type=EXPIRABLE,
            available=15,
            lead_time=30,
            expiry_date=date.today() + timedelta(days=26),
        )
        milk = self.make(
            order,
            name="Milk",
            type=EXPIRABLE,
            available=90,
            lead_time=6,
            expiry_date=date.today() - timedelta(days=2),
        )

        response = self.post(order.id)

        self.assertEqual(200, response.status_code)
        self.assertEqual(14, self.stored(cable))
        self.assertEqual(14, self.stored(butter))
        self.assertEqual(0, self.stored(milk))

    def test_processing_the_same_order_twice_takes_two_units(self):
        # Nothing marks an order as processed, so a second call decrements again.
        # Kept as the original behaved, but it wants a decision, not a refactor.
        order = Order.objects.create()
        cable = self.make(order, name="USB Cable", type=NORMAL, available=15, lead_time=30)

        self.post(order.id)
        self.post(order.id)

        self.assertEqual(13, self.stored(cable))

    def test_an_unknown_order_is_not_found(self):
        response = self.post(999999)

        self.assertEqual(404, response.status_code)
        self.assertEqual({'error': 'order not found'}, response.json())

    def test_the_endpoint_does_not_answer_to_get(self):
        order = Order.objects.create()

        response = self.client.get(reverse('process_order', args=[order.id]))

        self.assertEqual(405, response.status_code)
