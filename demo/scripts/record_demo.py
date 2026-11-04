"""Record 1080p Playwright scene videos against the local ReverseX UI."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
RAW = DEMO / "raw"
AUDIO = DEMO / "audio"
BASE = "http://127.0.0.1:5173"
JOB = "8307f8d9aa304926b57f91de7171bc9a"
VIEWPORT = {"width": 1920, "height": 1080}


def load_timeline() -> dict:
    return json.loads((AUDIO / "timeline.json").read_text(encoding="utf-8"))


def hold(page: Page, seconds: float) -> None:
    end = time.time() + max(seconds, 1.0)
    while time.time() < end:
        remaining = end - time.time()
        page.wait_for_timeout(int(min(remaining, 0.75) * 1000))


def click_nav(page: Page, label: str) -> None:
    page.get_by_role("button", name=label, exact=True).first.click(timeout=20000)


def open_completed_job(page: Page, tab: str = "progress") -> None:
    """Deep-link the verified job and wait until workspace content is present."""
    page.goto(f"{BASE}/?job={JOB}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    # Deep link opens Results; wait for either report content or saved list, then ensure job opens.
    page.wait_for_timeout(1200)
    # If reports empty, open from Saved investigations
    not_ready = page.get_by_text("Investigation results are not ready yet", exact=False)
    if not_ready.count() and not_ready.first.is_visible():
        open_btn = page.locator("button", has_text="Open").first
        open_btn.click(timeout=15000)
        page.wait_for_timeout(1500)
    # Prefer waiting for Guided Demo / Completed markers
    page.wait_for_timeout(800)
    for text in ("Guided Demo", "Completed", "taskboard", "Simple Report", "100%"):
        loc = page.get_by_text(text, exact=False).first
        try:
            if loc.count():
                page.wait_for_timeout(400)
                break
        except Exception:
            pass
    if tab == "progress":
        page.get_by_role("button", name="Progress").first.click()
        page.wait_for_timeout(700)
        page.get_by_text("Guided Demo", exact=False).first.wait_for(state="visible", timeout=20000)
    elif tab == "reports":
        page.get_by_role("button", name="Results", exact=True).first.click()
        page.wait_for_timeout(700)
        # Ensure Simple Report is visible (retry Open if needed)
        for _ in range(3):
            if page.get_by_text("Simple Report", exact=False).count():
                break
            if page.get_by_text("Investigation results are not ready yet", exact=False).count():
                page.locator("button", has_text="Open").first.click()
                page.wait_for_timeout(1500)
            else:
                page.wait_for_timeout(800)
        page.get_by_text("Simple Report", exact=False).first.wait_for(state="visible", timeout=20000)


def record_scene(browser, scene_id: str, duration: float, action) -> Path:
    out_dir = RAW / scene_id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    context = browser.new_context(
        viewport=VIEWPORT,
        record_video_dir=str(out_dir),
        record_video_size=VIEWPORT,
        device_scale_factor=1,
    )
    page = context.new_page()
    page.set_default_timeout(25000)
    t0 = time.time()
    action(page)
    elapsed = time.time() - t0
    if elapsed < duration + 0.8:
        hold(page, duration + 0.8 - elapsed)
    context.close()
    videos = list(out_dir.glob("*.webm"))
    if not videos:
        raise RuntimeError(f"No video recorded for {scene_id}")
    dest = RAW / f"{scene_id}.webm"
    if dest.exists():
        dest.unlink()
    shutil.move(str(videos[0]), str(dest))
    shutil.rmtree(out_dir, ignore_errors=True)
    print(f"recorded {scene_id}: {dest.name} (requested {duration:.1f}s, action {elapsed:.1f}s)")
    return dest


def scene_intro(page: Page) -> None:
    page.goto(BASE + "/", wait_until="networkidle")
    page.get_by_text("Understand software", exact=False).first.wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(1000)
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(1800)
    page.evaluate("window.scrollTo({top: 260, behavior: 'smooth'})")
    page.wait_for_timeout(2000)
    page.evaluate("window.scrollTo({top: 520, behavior: 'smooth'})")
    page.wait_for_timeout(2000)
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(1500)


def scene_investigation(page: Page) -> None:
    page.goto(BASE + "/", wait_until="networkidle")
    click_nav(page, "New Investigation")
    page.get_by_text("TaskBoard", exact=True).first.wait_for(state="visible", timeout=20000)
    page.get_by_text("TaskBoard", exact=True).first.click()
    page.wait_for_timeout(800)
    guided = page.get_by_text("Guided Demo", exact=False).first
    if guided.count():
        guided.click()
    page.wait_for_timeout(1000)
    page.evaluate("window.scrollTo({top: 360, behavior: 'smooth'})")
    page.wait_for_timeout(1600)
    # Open verified completed job — do not launch
    open_completed_job(page, tab="progress")
    page.wait_for_timeout(1000)
    page.get_by_text("Reconstructing", exact=False).first.scroll_into_view_if_needed()
    page.wait_for_timeout(1500)
    page.evaluate("window.scrollTo({top: 200, behavior: 'smooth'})")
    page.wait_for_timeout(1500)
    page.evaluate("window.scrollTo({top: 420, behavior: 'smooth'})")
    page.wait_for_timeout(1500)


def scene_reconstruction(page: Page) -> None:
    open_completed_job(page, tab="progress")
    page.wait_for_timeout(800)
    for label in ("Reconstructing", "Reused", "Testing", "Completed"):
        loc = page.get_by_text(label, exact=False).first
        try:
            if loc.count():
                loc.scroll_into_view_if_needed(timeout=5000)
                page.wait_for_timeout(1100)
        except Exception:
            pass
    page.evaluate("window.scrollTo({top: 180, behavior: 'smooth'})")
    page.wait_for_timeout(1400)
    page.evaluate("window.scrollTo({top: 400, behavior: 'smooth'})")
    page.wait_for_timeout(1600)
    page.evaluate("window.scrollTo({top: 620, behavior: 'smooth'})")
    page.wait_for_timeout(1600)


def scene_validation(page: Page) -> None:
    open_completed_job(page, tab="reports")
    page.get_by_role("button", name="Simple Report").first.click()
    page.wait_for_timeout(900)
    # Wait for match metrics
    page.get_by_text("100%", exact=False).first.wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(1200)
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(1400)
    page.evaluate("window.scrollTo({top: 280, behavior: 'smooth'})")
    page.wait_for_timeout(1600)
    page.evaluate("window.scrollTo({top: 520, behavior: 'smooth'})")
    page.wait_for_timeout(1600)


def scene_reports(page: Page) -> None:
    open_completed_job(page, tab="reports")
    page.get_by_role("button", name="Simple Report").first.click()
    page.wait_for_timeout(1000)
    page.get_by_text("Simple Report", exact=False).first.wait_for(state="visible")
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(1400)
    page.evaluate("window.scrollTo({top: 360, behavior: 'smooth'})")
    page.wait_for_timeout(1800)
    page.evaluate("window.scrollTo({top: 680, behavior: 'smooth'})")
    page.wait_for_timeout(1600)
    page.get_by_role("button", name="Developer Report").first.click()
    page.wait_for_timeout(1200)
    page.get_by_text("Developer Report", exact=False).first.wait_for(state="visible")
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(1400)
    page.evaluate("window.scrollTo({top: 360, behavior: 'smooth'})")
    page.wait_for_timeout(1800)
    page.evaluate("window.scrollTo({top: 700, behavior: 'smooth'})")
    page.wait_for_timeout(1400)


def scene_repair(page: Page) -> None:
    open_completed_job(page, tab="progress")
    page.get_by_role("button", name="Controlled Repair Example").first.click()
    page.get_by_text("Controlled Repair Example", exact=True).first.wait_for(state="visible", timeout=20000)
    page.wait_for_timeout(1200)
    # Wait for metrics
    for label in ("60%", "100%", "Initial", "Final", "fault", "CONTROLLED"):
        loc = page.get_by_text(label, exact=False).first
        try:
            if loc.count():
                loc.scroll_into_view_if_needed(timeout=4000)
                page.wait_for_timeout(700)
        except Exception:
            pass
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(1400)
    page.evaluate("window.scrollTo({top: 260, behavior: 'smooth'})")
    page.wait_for_timeout(1800)
    page.evaluate("window.scrollTo({top: 520, behavior: 'smooth'})")
    page.wait_for_timeout(1800)


def scene_conclusion(page: Page) -> None:
    page.goto(BASE + "/", wait_until="networkidle")
    page.get_by_text("Understand software", exact=False).first.wait_for(state="visible", timeout=20000)
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(2000)
    # Hero brand line is uppercase "ReverseX Engineer"
    page.get_by_text("Verify results", exact=False).first.wait_for(state="visible")
    page.wait_for_timeout(1500)


ACTIONS = {
    "01_intro": scene_intro,
    "02_investigation": scene_investigation,
    "03_reconstruction": scene_reconstruction,
    "04_validation": scene_validation,
    "05_reports": scene_reports,
    "06_repair": scene_repair,
    "07_conclusion": scene_conclusion,
}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    timeline = load_timeline()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for scene in timeline["scenes"]:
                sid = scene["id"]
                dur = float(scene["duration"])
                record_scene(browser, sid, dur, ACTIONS[sid])
        finally:
            browser.close()
    print("All scenes recorded.")


if __name__ == "__main__":
    main()
