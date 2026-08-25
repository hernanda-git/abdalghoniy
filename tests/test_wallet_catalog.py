from decimal import Decimal
from abdalghoniy.wallets import PublicWalletCatalog


def test_public_wallet_catalog_round_trips_only_metrics(tmp_path):
    p=tmp_path/'wallets.jsonl'
    p.write_text('{"address":"0x1","venue":"hyperliquid","observed_at_ms":1,"metrics":{"age_days":90,"closed_trades":100,"net_pnl":"10","profit_factor":"1.3","max_drawdown":"0.1","win_rate":"0.5","top_trade_share":"0.1"}}\n')
    c=PublicWalletCatalog.from_jsonl(p)
    assert len(c.eligible()) == 1
    out=tmp_path/'out.jsonl'; c.export(out)
    assert '0x1' in out.read_text()
