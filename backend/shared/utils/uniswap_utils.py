from decimal import Decimal, getcontext

getcontext().prec = 50

Q96 = Decimal(2 ** 96)


def tick_to_sqrt_price(tick: int) -> Decimal:
    return Decimal(1.0001) ** (Decimal(tick) / 2)


def calculate_amounts(position):
    liquidity = Decimal(position["liquidity"])
    if liquidity == 0:
        return Decimal(0), Decimal(0)

    tick_lower = int(position["tickLower"]["tickIdx"])
    tick_upper = int(position["tickUpper"]["tickIdx"])

    sqrt_lower = tick_to_sqrt_price(tick_lower)
    sqrt_upper = tick_to_sqrt_price(tick_upper)

    sqrt_price = Decimal(position["pool"]["sqrtPrice"]) / Q96

    if sqrt_price <= sqrt_lower:
        amount0 = liquidity * (sqrt_upper - sqrt_lower) / (sqrt_lower * sqrt_upper)
        amount1 = Decimal(0)

    elif sqrt_price >= sqrt_upper:
        amount0 = Decimal(0)
        amount1 = liquidity * (sqrt_upper - sqrt_lower)

    else:
        amount0 = liquidity * (sqrt_upper - sqrt_price) / (sqrt_price * sqrt_upper)
        amount1 = liquidity * (sqrt_price - sqrt_lower)

    return amount0, amount1
