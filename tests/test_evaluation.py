from decimal import Decimal
from abdalghoniy.evaluation import deflated_sharpe, random_control, walk_forward


def test_walk_forward_has_future_separation_and_random_control_is_reproducible():
    vals=[Decimal(i) for i in range(30)]
    folds=walk_forward(vals,folds=3)
    assert folds and all(f['train_end']<=f['test_end'] for f in folds)
    assert random_control(vals)==random_control(vals)
    assert deflated_sharpe(vals, trials=10)['status']=='computed'
