"""yt-dlp-backed downloader — fetch any video from any link, safely.

Used by the auto pipeline (ingest) and the manual Studio. Because the tool downloads arbitrary
user-pasted links, `is_allowed_url` guards against SSRF / local-file / internal-network targets.
yt-dlp breaks as sites change — keep it current: `pip install -U yt-dlp`.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urlparse


class DownloadError(RuntimeError):
    """Raised on a disallowed URL or a yt-dlp failure."""


def is_allowed_url(url: str) -> bool:
    """SSRF guard: only http(s); block localhost and private/loopback/link-local IPs.

    Optional `CLIPER_URL_ALLOWLIST` (comma-separated domains) restricts further. Unresolvable
    hosts are allowed (yt-dlp will fail anyway); the goal is to block known-internal targets.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()

    allowlist = [d.strip().lower() for d in os.environ.get("CLIPER_URL_ALLOWLIST", "").split(",")
                 if d.strip()]
    if allowlist and not any(host == d or host.endswith("." + d) for d in allowlist):
        return False
    if host == "localhost":
        return False
    try:
        for res in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(res[4][0])
            if getattr(ip, "ipv4_mapped", None):
                ip = ip.ipv4_mapped            # unwrap ::ffff:127.0.0.1 before classifying
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except (socket.gaierror, ValueError):
        pass  # unresolvable → let yt-dlp try
    return True


def _cookie_opts() -> dict:
    """Optional auth for sites that gate downloads (YouTube bot-check, age/region locks).

    Set CLIPER_COOKIES_FROM_BROWSER=chrome|firefox|safari|edge to reuse your logged-in browser
    session, or CLIPER_COOKIES_FILE=/path/to/cookies.txt for an exported cookie jar.
    """
    out: dict = {}
    browser = os.environ.get("CLIPER_COOKIES_FROM_BROWSER", "").strip()
    if browser:
        out["cookiesfrombrowser"] = (browser,)
    cookie_file = os.environ.get("CLIPER_COOKIES_FILE", "").strip()
    if cookie_file:
        out["cookiefile"] = cookie_file
    return out


def _opts(extra: dict) -> dict:
    return {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 20,
            "retries": 3, "fragment_retries": 3, **_cookie_opts(), **extra}


def probe(url: str) -> dict:
    """Fast metadata (id/title/duration) without downloading."""
    import yt_dlp
    if not is_allowed_url(url):
        raise DownloadError(f"URL not allowed: {url}")
    try:
        with yt_dlp.YoutubeDL(_opts({"skip_download": True})) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001 — surface any extractor error uniformly
        raise DownloadError(f"probe failed: {exc}") from exc
    return {"id": info.get("id", ""), "title": info.get("title", ""),
            "duration": float(info.get("duration") or 0.0), "ext": info.get("ext", "mp4")}


def download(url: str, dest_dir, on_progress=None) -> Path:
    """Download `url` into `dest_dir` as <=1080p mp4. Returns the saved file path."""
    import yt_dlp
    if not is_allowed_url(url):
        raise DownloadError(f"URL not allowed: {url}")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    def hook(d):
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            on_progress((d.get("downloaded_bytes") or 0) / total if total else 0.0)

    opts = _opts({
        # progressively looser: best ≤1080 video+audio → best ≤1080 muxed → best anything
        "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "progress_hooks": [hook],
        "max_filesize": 3 * 1024 ** 3,         # 3 GB hard stop (resource-abuse guard)
        "match_filter": yt_dlp.utils.match_filter_func("!is_live"),  # refuse livestreams
    })
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:  # noqa: BLE001
        raise DownloadError(f"download failed: {exc}") from exc

    vid = info.get("id", "")
    path = dest_dir / f"{vid}.mp4"
    if not path.exists():
        cands = sorted(dest_dir.glob(f"{vid}.*"))
        if not cands:
            raise DownloadError(f"download produced no file for {url}")
        path = cands[0]
    return path
