from decimal import Decimal
import random
from statistics import mean, pstdev


def walk_forward(values, *, train_fraction=Decimal('0.5'), test_fraction=Decimal('0.3'), folds=3):
    vals=list(values); n=len(vals)
    train_n=max(1,int(n*train_fraction)); test_n=max(1,int(n*test_fraction)); out=[]
    for i in range(folds):
        train_end=train_n+i*test_n; test_end=min(n,train_end+test_n)
        if test_end<=train_end or train_end>n: break
        out.append({'train': vals[max(0,train_end-train_n):train_end], 'test': vals[train_end:test_end], 'train_end':train_end, 'test_end':test_end})
    return out


def random_control(values, *, seed=17):
    rng=random.Random(seed); return [v if rng.random()>=0.5 else -v for v in [Decimal(str(x)) for x in values]]


def deflated_sharpe(values, trials: int):
    vals=[float(x) for x in values]
    if len(vals)<2 or trials<1: return {'status':'insufficient_evidence','value':None,'trials':trials}
    sd=pstdev(vals)
    raw=mean(vals)/sd if sd else 0.0
    penalty=(2.0*__import__('math').log(max(1,trials)))**0.5
    value=raw-penalty
    return {'status':'computed','raw_sharpe':raw,'penalty':penalty,'deflated_sharpe':value,'trials':trials}
