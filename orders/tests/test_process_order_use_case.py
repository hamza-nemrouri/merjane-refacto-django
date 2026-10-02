# orders/tests/test_process_order_use_case.py

import unittest

from orders.services.process_order import OrderNotFound, ProcessOrderUseCase


class FakeQuerySet:
    """The real repository hands back a queryset, which is why .first() is called."""

    def __init__(self, order):
        self._order = order

    def first(self):
        return self._order


class FakeOrderRepository:
    def __init__(self, order=None):
        self.order = order
        self.requested = []

    def find_by_id(self, order_id):
        self.requested.append(order_id)
        return FakeQuerySet(self.order)


class FakeOrder:
    def __init__(self, order_id, products):
        self.id = order_id
        self._products = products

    def get_items(self):
        return list(self._products)

    def get_id(self):
        return self.id


class FakePolicy:
    """Stands in for the stock policy and records what it was handed."""

    def __init__(self):
        self.handled = []
        self.days = []

    def handle(self, product, today=None):
        self.handled.append(product)
        self.days.append(today)


class ProcessOrderUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.products = ["usb cable", "butter", "watermelon"]
        self.order = FakeOrder(7, self.products)
        self.orders = FakeOrderRepository(self.order)
        self.policy = FakePolicy()
        self.use_case = ProcessOrderUseCase(orders=self.orders, policy=self.policy)

    def test_every_product_in_the_order_is_handled_once(self):
        order_id = self.use_case.execute(7)

        self.assertEqual(7, order_id)
        self.assertEqual(self.products, self.policy.handled)

    def test_the_same_day_is_used_for_the_whole_order(self):
        self.use_case.execute(7)

        self.assertEqual(3, len(self.policy.days))
        self.assertEqual(1, len(set(self.policy.days)))

    def test_a_missing_order_is_reported_rather_than_crashing(self):
        self.orders.order = None

        with self.assertRaises(OrderNotFound) as caught:
            self.use_case.execute(404)

        self.assertEqual(404, caught.exception.order_id)
        self.assertEqual([404], self.orders.requested)
        self.assertEqual([], self.policy.handled)

    def test_an_empty_order_is_still_a_success(self):
        self.orders.order = FakeOrder(7, [])

        order_id = self.use_case.execute(7)

        self.assertEqual(7, order_id)
        self.assertEqual([], self.policy.handled)


if __name__ == '__main__':
    unittest.main()
