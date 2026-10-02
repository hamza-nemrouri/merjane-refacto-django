from datetime import date

from ...repositories.product_repository import pr
from ..product_rules import ExpirableProductRule, SeasonalProductRule, announce_delay, rule_for
from .notification_service import ns


class ProductService:
    def handle(self, product, today=None):
        rule_for(product.type, pr, ns, today or date.today()).apply(product)

    # The original API. Kept for existing callers, and it delegates to the rules.
    def notify_delay(self, lead_time, product):
        product.lead_time = lead_time
        announce_delay(pr, ns, product)

    def handle_seasonal_product(self, product, today=None):
        SeasonalProductRule(pr, ns, today or date.today()).handle_out_of_stock(product)

    def handle_expired_product(self, product, today=None):
        ExpirableProductRule(pr, ns, today or date.today()).handle_unsellable(product)


ps = ProductService()
