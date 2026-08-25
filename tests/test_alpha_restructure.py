from decimal import Decimal
from abdalghoniy.regime import classify_regime
from abdalghoniy.arbitration import Proposal, arbitrate


def test_regime_and_arbitration_require_agreement_and_cost_edge():
    assert classify_regime(Decimal('1.2'), Decimal('0.2'), Decimal('0.1')) == 'trend_up'
    p=Proposal('long',Decimal('50'),Decimal('0.8'),'wallet_consensus',True,True,True,1000)
    assert arbitrate([p], min_edge_bps=Decimal('30')) == p
    assert arbitrate([Proposal('long',Decimal('10'),Decimal('0.8'),'wallet_consensus',True,True,True,1000)], min_edge_bps=Decimal('30')) is None
