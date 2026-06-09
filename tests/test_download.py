"""SSRF-guard tests for the universal downloader (no network needed)."""
from __future__ import annotations

from cliper.utils.download import is_allowed_url


def test_blocks_non_http_schemes():
    assert not is_allowed_url("file:///etc/passwd")
    assert not is_allowed_url("ftp://example.com/x")
    assert not is_allowed_url("not a url")


def test_blocks_localhost_and_private_ips():
    for u in ("http://localhost:8000/", "http://127.0.0.1/", "http://10.0.0.5/",
              "http://192.168.1.1/", "http://169.254.1.1/"):
        assert not is_allowed_url(u), u


def test_allows_public():
    assert is_allowed_url("http://8.8.8.8/video")     # literal public IP — no DNS needed
    assert is_allowed_url("https://youtu.be/abc123")  # public host (or unresolvable → allowed)
