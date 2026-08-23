from decimal import Decimal

from abdalghoniy.ledger import DurableLedger


def test_ledger_persists_trade_and_equity_across_instances(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    ledger = DurableLedger(path)
    ledger.record_trade({"symbol": "BTCUSDT", "direction": "long", "entry": "100", "exit": "102", "quantity": "1", "gross": "2", "fees": "0.1", "funding": "0.01", "net": "1.89"})
    ledger.record_equity(Decimal("101.89"), Decimal("0.01"))
    ledger.close()

    reopened = DurableLedger(path)
    assert len(reopened.trades()) == 1
    assert reopened.trades()[0]["net"] == "1.89"
    assert reopened.latest_equity()["equity"] == "101.89"
    assert reopened.latest_equity()["drawdown"] == "0.01"
    reopened.close()
