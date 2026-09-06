from discount import discounted_total


def test_discount_is_numeric():
    assert isinstance(discounted_total(100, 5), float)
