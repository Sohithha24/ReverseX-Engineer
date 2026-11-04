"""Evaluator-controlled IT-Tools compatibility probe (NOT Muse).

Does not call Meta. Does not write Muse prompts. Screenshots + observations only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'audit-evidence-it-tools'
ORIGIN = 'http://127.0.0.1:8010'


def safe_like_elements(page) -> list[dict]:
    """Approximate ReverseX SafeBrowser element discovery."""
    locator = page.locator('button, input, textarea, select')
    count = min(locator.count(), 40)
    elements = []
    for idx in range(count):
        item = locator.nth(idx)
        if not item.is_visible():
            continue
        kind = item.evaluate('(el) => el.tagName.toLowerCase()')
        label = (
            item.get_attribute('aria-label')
            or item.get_attribute('placeholder')
            or (item.inner_text() if kind == 'button' else None)
            or item.get_attribute('name')
            or ''
        )
        elements.append({'kind': kind, 'label': (label or '').strip()[:120]})
    return elements


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {
        'origin': ORIGIN,
        'role': 'evaluator_compatibility_probe',
        'muse_called': False,
        'pages': [],
        'console_errors': [],
        'page_errors': [],
        'findings': [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=False)
        page = context.new_page()
        page.on('console', lambda msg: report['console_errors'].append(msg.text) if msg.type == 'error' else None)
        page.on('pageerror', lambda err: report['page_errors'].append(str(err)))

        # Home
        page.goto(ORIGIN + '/', wait_until='domcontentloaded', timeout=20_000)
        page.wait_for_timeout(1500)
        home_text = page.locator('body').inner_text()[:2500]
        home_els = safe_like_elements(page)
        page.screenshot(path=str(OUT / '01-home.png'), full_page=True)
        link_count = page.locator('a').count()
        report['pages'].append(
            {
                'url': page.url,
                'title': page.title(),
                'visible_text_excerpt': re.sub(r'\s+', ' ', home_text).strip()[:500],
                'safe_browser_like_controls': home_els,
                'anchor_count': link_count,
            }
        )

        # Search / locate Base64 without assuming Muse can do this
        search = page.locator('input[type="search"], input[placeholder*="Search" i], input[aria-label*="Search" i]')
        base64_candidates = []
        if search.count():
            search.first.fill('base64')
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / '02-search-base64.png'), full_page=True)
            # Collect visible links mentioning base64
            for i in range(min(page.locator('a').count(), 80)):
                a = page.locator('a').nth(i)
                try:
                    if not a.is_visible():
                        continue
                    text = (a.inner_text() or '').strip()
                    href = a.get_attribute('href') or ''
                    if re.search(r'base64', text + ' ' + href, re.I):
                        base64_candidates.append({'text': text[:120], 'href': href})
                except Exception:
                    continue
        else:
            report['findings'].append('No obvious search input found on home for SafeBrowser-style discovery.')

        report['base64_link_candidates'] = base64_candidates

        # Try common IT-Tools route if present in candidates or known path pattern from hrefs only
        reached = False
        tried_urls = []
        candidate_paths = []
        for c in base64_candidates:
            href = c.get('href') or ''
            if href.startswith('/'):
                candidate_paths.append(ORIGIN + href)
            elif href.startswith(ORIGIN):
                candidate_paths.append(href)
        # Also try clicking first matching link (evaluator only)
        if base64_candidates:
            first = base64_candidates[0]
            href = first.get('href') or ''
            if href:
                target = ORIGIN + href if href.startswith('/') else href
                tried_urls.append(target)
                page.goto(target, wait_until='domcontentloaded', timeout=20_000)
                page.wait_for_timeout(1200)
                reached = True

        if not reached:
            # Fallback probe of plausible tool routes without claiming Muse would know them
            for path in (
                '/base64-string-converter',
                '/#/base64-string-converter',
                '/tools/base64-string-converter',
            ):
                url = ORIGIN + path
                tried_urls.append(url)
                resp = page.goto(url, wait_until='domcontentloaded', timeout=20_000)
                page.wait_for_timeout(1000)
                text = page.locator('body').inner_text()[:1500]
                if re.search(r'base64', text, re.I) and page.locator('textarea, input').count() > 0:
                    reached = True
                    break

        feature_page = {
            'reached': reached,
            'tried_urls': tried_urls,
            'final_url': page.url if reached else None,
            'title': page.title() if reached else None,
        }
        if reached:
            page.screenshot(path=str(OUT / '03-base64-feature.png'), full_page=True)
            text = page.locator('body').inner_text()[:2500]
            els = safe_like_elements(page)
            feature_page['visible_text_excerpt'] = re.sub(r'\s+', ' ', text).strip()[:700]
            feature_page['safe_browser_like_controls'] = els
            # Light interaction: fill first textarea if present (evaluator only)
            areas = page.locator('textarea')
            if areas.count():
                areas.first.fill('Hello ReverseX')
                page.wait_for_timeout(500)
                after = page.locator('body').inner_text()[:2500]
                feature_page['after_fill_excerpt'] = re.sub(r'\s+', ' ', after).strip()[:700]
                feature_page['output_changed'] = after != text
                page.screenshot(path=str(OUT / '04-base64-after-fill.png'), full_page=True)
            report['pages'].append(feature_page)
        else:
            report['pages'].append(feature_page)

        # SafeBrowser capability gap notes
        report['reversex_action_surface'] = {
            'supported_actions': ['observe', 'click', 'fill', 'reload', 'stop'],
            'discoverable_controls': ['button', 'input', 'textarea', 'select'],
            'not_clickable_by_safe_browser': ['a (anchor/router links)', 'div role=button unless button tag', 'contenteditable'],
        }
        home_has_nav_links = link_count > 0
        home_has_buttons_for_tools = any(
            re.search(r'base64', e.get('label') or '', re.I) for e in home_els
        )
        report['findings'].append(
            'Home exposes many anchor links; SafeBrowser cannot click <a> tags.'
            if home_has_nav_links
            else 'Home link surface unclear.'
        )
        report['findings'].append(
            'Home SafeBrowser-like controls include a Base64-labeled button/input.'
            if home_has_buttons_for_tools
            else 'Home SafeBrowser-like controls do not expose an obvious Base64 button; navigation likely requires links or search+link.'
        )
        if reached:
            report['findings'].append(
                f'Evaluator reached Base64 UI at {feature_page.get("final_url")}.'
            )
        else:
            report['findings'].append('Evaluator could not confirm Base64 feature page.')

        browser.close()

    out_json = OUT / 'compatibility_probe.json'
    out_json.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'wrote': str(out_json), 'reached': reached, 'findings': report['findings']}, indent=2))
    return 0 if reached else 2


if __name__ == '__main__':
    sys.exit(main())
