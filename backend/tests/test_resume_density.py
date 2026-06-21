from app.services.resume_density import (
    DENSE_THRESHOLD,
    IDEAL_MIN,
    SPARSE_THRESHOLD,
    assess_density,
    count_chars,
)


def test_count_chars_strips():
    assert count_chars("  abc  ") == 3


def test_sparse_status():
    md = "x" * (SPARSE_THRESHOLD - 1)
    d = assess_density(md)
    assert d["status"] == "sparse"


def test_ok_status():
    md = "x" * IDEAL_MIN
    d = assess_density(md)
    assert d["status"] in ("ok", "light")


def test_dense_status():
    md = "x" * (DENSE_THRESHOLD + 1)
    d = assess_density(md)
    assert d["status"] == "dense"
