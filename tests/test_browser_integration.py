import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import pytest
from reversex.browser import SafeBrowser
from reversex.contracts import Decision

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def target_app():
    # Integration test serves only the fixture; skips if port is unavailable.
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', 8001)) == 0:
            pytest.skip('Port 8001 is already occupied: run integration test in a free environment')
    process = subprocess.Popen(
        [sys.executable, '-m', 'http.server', '8001', '--bind', '127.0.0.1', '--directory', str(ROOT / 'sample_app')],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1', 8001)) == 0:
                    break
            time.sleep(.1)
        else:
            pytest.skip('Local HTTP fixture did not start')
        yield 'http://127.0.0.1:8001'
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_browser_snapshot_stale_ids_and_task_persistence(target_app, monkeypatch):
    executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
    if not executable:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            if not Path(playwright.chromium.executable_path).exists():
                pytest.skip('Playwright Chromium not installed: run python -m playwright install chromium')
    with SafeBrowser(target_app) as browser:
        initial = browser.goto(target_app)
        assert any(e.label == 'Add task' for e in initial.elements)
        input_id = next(e.element_id for e in initial.elements if e.kind == 'input')
        after_fill = browser.act(Decision(action='fill', element_id=input_id, value='ReverseX test', reason='test'))
        with pytest.raises(ValueError, match='expired'):
            browser.act(Decision(action='fill', element_id=input_id, value='stale', reason='test'))
        btn_id = next(e.element_id for e in after_fill.elements if e.kind == 'button')
        after_click = browser.act(Decision(action='click', element_id=btn_id, reason='test'))
        assert 'ReverseX test' in after_click.visible_text
        refreshed = browser.act(Decision(action='reload', reason='test persistence'))
        assert 'ReverseX test' in refreshed.visible_text
