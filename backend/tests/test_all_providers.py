from app.services.job_feed import all_enabled_providers


def test_all_enabled_providers_includes_core_sources():
    names = all_enabled_providers()
    assert "github_joblist" in names
    assert "early_batch" in names
    assert "job_aggregator" in names
