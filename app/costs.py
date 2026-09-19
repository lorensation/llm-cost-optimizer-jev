from decimal import Decimal, ROUND_HALF_UP


MICRO_USD = Decimal("1000000")


def usd_to_microusd(value: int | float | str | Decimal) -> int:
    return int((Decimal(str(value)) * MICRO_USD).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def estimate_cost_microusd(input_tokens: int, output_tokens: int, input_rate: int, output_rate: int) -> int:
    numerator = input_tokens * input_rate + output_tokens * output_rate
    return (numerator + 999_999) // 1_000_000
