def discounted_total(subtotal: float, loyalty_years: int) -> float:
    if loyalty_years >= 5:
        return subtotal * 0.80
    if loyalty_years >= 1:
        return subtotal * 0.95
    return subtotal
