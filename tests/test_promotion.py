import pytest
from abdalghoniy.promotion import PromotionEvidence, PromotionRegistry


def test_unproven_strategy_cannot_be_promoted(tmp_path):
    e=PromotionEvidence('x','d','c','g',0,0,0,0,False)
    with pytest.raises(ValueError): PromotionRegistry(tmp_path/'p.json').save(e)


def test_promotion_requires_positive_oos_and_control_uplift(tmp_path):
    e=PromotionEvidence('x','d','c','g',100,1,0.1,0.2,True)
    r=PromotionRegistry(tmp_path/'p.json'); r.save(e)
    assert r.load()==e
