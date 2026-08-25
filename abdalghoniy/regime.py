from decimal import Decimal


def classify_regime(trend_score: Decimal, volatility_percentile: Decimal, funding_abs: Decimal) -> str:
    if funding_abs > Decimal('100'):
        return 'unsafe'
    if volatility_percentile >= Decimal('0.9'):
        return 'volatility_expansion'
    if volatility_percentile <= Decimal('0.1'):
        return 'volatility_compression'
    if trend_score >= Decimal('0.5'):
        return 'trend_up'
    if trend_score <= Decimal('-0.5'):
        return 'trend_down'
    return 'range'
