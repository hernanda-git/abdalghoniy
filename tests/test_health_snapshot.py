from abdalghoniy.dashboard import health_snapshot, public_health_snapshot


def test_health_snapshot_reports_storage_memory_and_database_inventory():
    result = health_snapshot()
    assert result["project"]["bytes"] > 0
    assert result["process"]["rss_bytes"] > 0
    assert isinstance(result["databases"], list)
    assert result["safety"]["live_orders_enabled"] is False


def test_public_health_snapshot_does_not_expose_host_identity_or_process_details():
    result = public_health_snapshot()
    assert result == {"status": "ok", "mode": "paper", "data_plane": "rest"}
    assert "project" not in result
    assert "process" not in result
    assert "host" not in result
    assert "disk" not in result
