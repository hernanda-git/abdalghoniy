from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class WalletMetrics:
    address: str
    age_days: int
    closed_trades: int
    net_pnl: Decimal
    profit_factor: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    top_trade_share: Decimal


def eligible_wallet(metrics: WalletMetrics) -> bool:
    return bool(metrics.address and metrics.age_days >= 90 and metrics.closed_trades >= 100 and metrics.net_pnl > 0 and metrics.profit_factor >= Decimal('1.25') and metrics.max_drawdown <= Decimal('0.25') and Decimal('0.35') <= metrics.win_rate <= Decimal('0.80') and metrics.top_trade_share <= Decimal('0.20'))


def score_wallet(metrics: WalletMetrics) -> Decimal:
    if not eligible_wallet(metrics):
        return Decimal('0')
    score = (metrics.profit_factor * Decimal('40')) + (metrics.win_rate * Decimal('20')) + ((Decimal('1') - metrics.max_drawdown) * Decimal('20')) + min(Decimal(metrics.closed_trades), Decimal('500')) / Decimal('500') * Decimal('20')
    return score.quantize(Decimal('0.01'))
