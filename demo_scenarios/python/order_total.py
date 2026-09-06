"""Demo 01: basic Python correctness and boundary-condition review."""


def discounted_total(prices: list[float], discount_percent: float) -> float:
    subtotal = sum(prices)
    discount = subtotal * discount_percent
    return round(subtotal - discount, 2)

