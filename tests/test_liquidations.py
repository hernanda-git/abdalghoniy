from abdalghoniy.liquidations import PublicLiquidationHeatmapClient


def test_liquidation_heatmap_is_explicitly_unavailable_without_reliable_demo_stream():
    result = PublicLiquidationHeatmapClient().fetch("BTCUSDT")

    assert result.status == "unavailable"
    assert result.source == "none"
    assert result.levels == ()
    assert result.error == "no_reliable_public_susdt_futures_liquidation_stream"
    assert result.freshness_ms is None


def test_liquidation_client_never_calls_transport_or_estimates_values():
    calls = []

    def transport(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("liquidation client must not invent or query an unsupported stream")

    result = PublicLiquidationHeatmapClient(transport=transport).fetch("BTCUSDT")

    assert calls == []
    assert result.levels == ()
    assert result.total_notional is None
