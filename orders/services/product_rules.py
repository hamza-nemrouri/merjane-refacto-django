from datetime import timedelta

NORMAL = "NORMAL"
SEASONAL = "SEASONAL"
EXPIRABLE = "EXPIRABLE"


def is_in_season(product, today):
    """Inside the window, both bounds present. A missing bound is no window."""
    if product.season_start_date is None or product.season_end_date is None:
        return False
    return product.season_start_date < today < product.season_end_date


def is_expired(product, today):
    """Expired on the expiry date and after it. No date means it never expires."""
    return product.expiry_date is not None and product.expiry_date <= today


def delay_overruns_season(product, today):
    """A missing season end means no limit, so this cannot overrun."""
    if product.season_end_date is None:
        return False
    return today + timedelta(days=product.lead_time) > product.season_end_date


def season_not_started(product, today):
    return product.season_start_date is not None and product.season_start_date > today


def announce_delay(products, notifier, product):
    products.save(product)
    notifier.send_delay_notification(product.lead_time, product.name)


class ProductRule:
    """One product, one rule. Subclasses decide; the shared actions live here."""

    def __init__(self, products, notifier, today):
        self.products = products
        self.notifier = notifier
        self.today = today

    def apply(self, product):
        raise NotImplementedError

    def sell(self, product):
        product.available -= 1
        self.products.save(product)

    def announce_delay(self, product):
        announce_delay(self.products, self.notifier, product)


class NormalProductRule(ProductRule):
    """Sell if in stock. Otherwise announce the delay, if there is one."""

    def apply(self, product):
        if product.available > 0:
            self.sell(product)
        elif product.lead_time > 0:
            self.announce_delay(product)


class SeasonalProductRule(ProductRule):
    """Sell inside the season. Otherwise the season decides the message."""

    def apply(self, product):
        if product.available > 0 and is_in_season(product, self.today):
            self.sell(product)
            return
        self.handle_out_of_stock(product)

    def handle_out_of_stock(self, product):
        # An overrun empties the stock, a season that has not started does not.
        # Kept as the original behaved, not as it should.
        if delay_overruns_season(product, self.today):
            self.notifier.send_out_of_stock_notification(product.name)
            product.available = 0
            self.products.save(product)
        elif season_not_started(product, self.today):
            self.notifier.send_out_of_stock_notification(product.name)
            self.products.save(product)
        else:
            self.announce_delay(product)


class ExpirableProductRule(ProductRule):
    """Sell while unexpired. Otherwise empty the stock and say it expired."""

    def apply(self, product):
        if product.available > 0 and not is_expired(product, self.today):
            self.sell(product)
            return
        self.handle_unsellable(product)

    def handle_unsellable(self, product):
        # Also reached when the product is out of stock but not expired, which is
        # why an expiry message can go out for a fresh product. Original behaviour.
        product.available = 0
        self.products.save(product)
        self.notifier.send_expiry_notification(product.name)


class UnknownProductRule(ProductRule):
    """An unknown type takes no action, as the original if/elif chain did."""

    def apply(self, product):
        pass


RULES = {
    NORMAL: NormalProductRule,
    SEASONAL: SeasonalProductRule,
    EXPIRABLE: ExpirableProductRule,
}


def rule_for(product_type, products, notifier, today):
    return RULES.get(product_type, UnknownProductRule)(products, notifier, today)
