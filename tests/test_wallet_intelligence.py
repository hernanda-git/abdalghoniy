from decimal import Decimal
from abdalghoniy.wallet_score import WalletMetrics, eligible_wallet, score_wallet
from abdalghoniy.wallet_consensus import WalletEvent, consensus
from abdalghoniy.copyability import CopyabilityObservation, copyable


def test_wallet_quality_rejects_small_or_concentrated_track_records():
    good=WalletMetrics('0x1',90,120,Decimal('120'),Decimal('1.4'),Decimal('0.08'),Decimal('0.55'),Decimal('0.10'))
    bad=WalletMetrics('0x2',20,200,Decimal('50'),Decimal('1.1'),Decimal('0.50'),Decimal('0.55'),Decimal('0.80'))
    assert eligible_wallet(good)
    assert not eligible_wallet(bad)
    assert score_wallet(good)>0


def test_consensus_requires_three_independent_eligible_wallets():
    events=[WalletEvent(str(i),'0x'+str(i),'BTCUSDT','long',1000+i,100,True) for i in range(3)]
    assert consensus(events, min_wallets=3, window_ms=1000).side=='long'
    assert consensus(events[:2], min_wallets=3, window_ms=1000) is None


def test_copyability_rejects_latency_and_price_chase():
    assert copyable(CopyabilityObservation(1000,1700,1800,100,101,102,10,0.5), max_delay_ms=500, max_atr_move=0.4) is False
    assert copyable(CopyabilityObservation(1000,1100,1200,100,100.1,100.2,10,0.1), max_delay_ms=500, max_atr_move=0.4)
