from datetime import date

from ..repositories.order_repository import or_
from .implementations.product_service import ps


class OrderNotFound(Exception):
    def __init__(self, order_id):
        super().__init__("Order %s not found" % order_id)
        self.order_id = order_id


class ProcessOrderUseCase:
    def __init__(self, orders=None, policy=None):
        self._orders = orders
        self._policy = policy

    def execute(self, order_id):
        """Decrement every product against one day, and return the order id."""
        order = (self._orders or or_).find_by_id(order_id).first()
        if order is None:
            raise OrderNotFound(order_id)

        today = date.today()
        policy = self._policy or ps
        for product in order.get_items():
            policy.handle(product, today)

        return order.get_id()
