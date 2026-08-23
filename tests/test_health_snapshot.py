from abdalghoniy.dashboard import health_snapshot


def test_health_snapshot_reports_storage_memory_and_database_inventory():
    result = health_snapshot()
    assert result["project"]["bytes"] > 0
    assert result["process"]["rss_bytes"] > 0
    assert isinstance(result["databases"], list)
    assert result["safety"]["live_orders_enabled"] is False
