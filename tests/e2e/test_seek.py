"""Permanent real-UI seek regression test (the bug regressed twice because the assertion was
dropped). Exercises the actual click + drag-scrub path through Studio.seek → the <video> element.

Opt-in: skips unless Playwright + system Chrome + a built frontend (dist) + a sample video are all
present. Run with the frontend built (`npm run build`):  pytest tests/e2e -q
"""
from __future__ import annotations

import re
import socket
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "cliper" / "web" / "frontend" / "dist" / "index.html"
# Real source videos only — exclude rendered clip outputs like "<id>_03.mp4" (a few seconds long).
SAMPLES = [p for p in sorted((ROOT / "work").rglob("*.mp4")) if not re.search(r"_\d\d\.mp4$", p.name)]

playwright = pytest.importorskip("playwright.sync_api")

pytestmark = pytest.mark.skipif(
    not DIST.exists() or not SAMPLES,
    reason="needs a built frontend (npm run build) and a sample video under work/",
)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def server():
    port = _free_port()
    proc = subprocess.Popen(
        ["python", "-m", "cliper.cli", "ui", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        import urllib.request
        for _ in range(40):
            try:
                urllib.request.urlopen(base, timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_timeline_click_and_drag_seek(server):
    from playwright.sync_api import sync_playwright

    sample = str(min(SAMPLES, key=lambda p: p.stat().st_size))  # shortest real source
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            pytest.skip("system Chrome not available")
        pg = b.new_page(viewport={"width": 1680, "height": 1000})
        pg.goto(server, wait_until="networkidle")
        pg.set_input_files("input[type=file]", sample)
        pg.wait_for_function("()=>{const v=document.querySelector('video');return v&&v.duration>5}", timeout=120000)
        dur = pg.evaluate("()=>document.querySelector('video').duration")
        box = pg.query_selector("div.cursor-text").bounding_box()
        cy = box["y"] + box["height"] / 2

        # real CLICK at 50%
        pg.mouse.click(box["x"] + box["width"] * 0.5, cy)
        pg.wait_for_timeout(700)
        click = pg.evaluate("()=>document.querySelector('video').currentTime")

        # real DRAG-SCRUB 20% -> 80%
        pg.mouse.move(box["x"] + box["width"] * 0.2, cy)
        pg.mouse.down()
        for f in (0.4, 0.6, 0.8):
            pg.mouse.move(box["x"] + box["width"] * f, cy)
            pg.wait_for_timeout(100)
        pg.mouse.up()
        pg.wait_for_timeout(700)
        drag = pg.evaluate("()=>document.querySelector('video').currentTime")
        pg.wait_for_timeout(900)
        hold = pg.evaluate("()=>document.querySelector('video').currentTime")
        b.close()

    assert abs(click - dur * 0.5) < dur * 0.06, f"click seek failed: {click} vs {dur*0.5}"
    assert abs(drag - dur * 0.8) < dur * 0.06, f"drag-scrub failed: {drag} vs {dur*0.8}"
    assert abs(hold - drag) < 6, f"seek did not hold (snapped back): {hold} vs {drag}"
