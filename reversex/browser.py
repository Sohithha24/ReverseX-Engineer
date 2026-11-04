"""Small scoped browser executor. MVP: only an explicitly configured local fixture."""
from __future__ import annotations

import os
import re
from urllib.parse import urljoin, urlsplit
from playwright.sync_api import sync_playwright
from reversex.contracts import (
    Action,
    ControlValueChange,
    Decision,
    PageSnapshot,
    VisibleElement,
)
from reversex.targets import ALLOWED_LOCAL_PORTS

# Observation limits (generic — not application-specific).
MAX_VISIBLE_ELEMENTS = 48
MAX_VALUE_CHARS = 200
MAX_LABEL_CHARS = 120
MAX_VISIBLE_TEXT_CHARS = 2000

_SENSITIVE_INPUT_TYPES = frozenset({'password', 'hidden', 'file'})
_SENSITIVE_NAME_RE = re.compile(
    r'(password|passwd|secret|token|api[_-]?key|authorization|auth|session|cookie|csrf|'
    r'credit|cardnum|card_number|cvv|cvc|ssn|private[_-]?key)',
    re.I,
)
_SENSITIVE_VALUE_RE = re.compile(
    r'(?i)(Bearer\s+[A-Za-z0-9._\-+=/]{12,}|sk-[A-Za-z0-9]{16,}|'
    r'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})'
)


def validate_target(url: str, allowed_origin: str) -> None:
    """Enforce origin equality, local-only host, allowlisted ports, and no credentials.

    Investigation entry still requires ORIGIN_ALLOWLIST via resolve_authorized_application.
    This helper also permits the reconstruction preview port (:8002) when that origin is
    the explicitly approved origin for a validation session.
    """
    parsed, approved = urlsplit(url), urlsplit(allowed_origin)
    if parsed.scheme != 'http' or approved.scheme != 'http':
        raise ValueError('MVP only permits HTTP on an explicitly approved local origin')
    if parsed.hostname != '127.0.0.1' or approved.hostname != '127.0.0.1':
        raise ValueError('MVP only permits 127.0.0.1 (no DNS aliases or alternate hosts)')
    if parsed.username or parsed.password or approved.username or approved.password:
        raise ValueError('Credential-bearing URLs are not allowlisted')
    if parsed.port is None or approved.port is None:
        raise ValueError('Explicit ports are required')
    if parsed.port not in ALLOWED_LOCAL_PORTS or approved.port not in ALLOWED_LOCAL_PORTS:
        raise ValueError('Target port is not allowlisted')
    if parsed.port != approved.port:
        raise ValueError('Target origin is not allowlisted for this investigation')
    if parsed.fragment:
        raise ValueError('URL fragments are not accepted')


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + '…'


def looks_sensitive_identifier(*parts: str | None) -> bool:
    blob = ' '.join(p for p in parts if p)
    return bool(blob and _SENSITIVE_NAME_RE.search(blob))


def redact_if_sensitive_value(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    if _SENSITIVE_VALUE_RE.search(value):
        return '[REDACTED]', True
    return value, False


def diff_control_values(
    before: PageSnapshot | dict | None,
    after: PageSnapshot | dict | None,
) -> list[ControlValueChange]:
    """Detect observable control field changes between two snapshots."""

    def as_dict(snap: PageSnapshot | dict | None) -> dict:
        if snap is None:
            return {}
        if isinstance(snap, PageSnapshot):
            return snap.model_dump()
        return snap

    before_els = (as_dict(before).get('elements') or [])
    after_els = (as_dict(after).get('elements') or [])

    def key(el: dict) -> tuple[str, str, str]:
        return (
            str(el.get('kind') or ''),
            str(el.get('label') or ''),
            str(el.get('placeholder') or el.get('input_type') or ''),
        )

    before_by_key: dict[tuple[str, str, str], dict] = {}
    for el in before_els:
        before_by_key[key(el)] = el

    changes: list[ControlValueChange] = []
    for el in after_els:
        prev = before_by_key.get(key(el))
        if not prev:
            continue
        for field in ('value', 'checked', 'selected', 'disabled', 'readonly'):
            b = prev.get(field)
            a = el.get(field)
            if b is None and a is None:
                continue
            if str(b) != str(a):
                if prev.get('value_redacted') or el.get('value_redacted'):
                    b_out, a_out = '[REDACTED]' if b is not None else None, '[REDACTED]' if a is not None else None
                else:
                    b_out = None if b is None else _truncate(str(b), MAX_VALUE_CHARS)
                    a_out = None if a is None else _truncate(str(a), MAX_VALUE_CHARS)
                changes.append(
                    ControlValueChange(
                        element_id_after=el.get('element_id'),
                        kind=str(el.get('kind') or ''),
                        label=_truncate(str(el.get('label') or ''), MAX_LABEL_CHARS) or '',
                        field=field,
                        before=b_out,
                        after=a_out,
                    )
                )
        if len(changes) >= 24:
            break
    return changes


class SafeBrowser:
    def __init__(self, allowed_origin: str):
        validate_target(allowed_origin, allowed_origin)
        self.allowed_origin = allowed_origin.rstrip('/')
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._snapshot_id = 0
        self._element_map = {}
        self._closed = False
        self._last_snapshot: PageSnapshot | None = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        options = {'headless': True}
        executable = os.getenv('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
        if executable:
            options['executable_path'] = executable
        try:
            self._browser = self._playwright.chromium.launch(**options)
            self._context = self._browser.new_context(accept_downloads=False, service_workers='block')
            self._context.set_default_timeout(10_000)
            self._context.route('**/*', self._route_request)
            self._page = self._context.new_page()
            self._page.on('popup', lambda popup: popup.close())
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        self._element_map.clear()
        for closer in (
            lambda: self._context.close() if self._context else None,
            lambda: self._browser.close() if self._browser else None,
            lambda: self._playwright.stop() if self._playwright else None,
        ):
            try:
                closer()
            except Exception:
                pass
        self._context = None
        self._browser = None
        self._playwright = None
        self._closed = True

    def _route_request(self, route):
        url = route.request.url
        try:
            validate_target(url, self.allowed_origin)
            route.continue_()
        except (ValueError, TypeError):
            route.abort('blockedbyclient')

    def goto(self, url: str) -> PageSnapshot:
        validate_target(url, self.allowed_origin)
        self._page.goto(url, wait_until='domcontentloaded', timeout=10_000)
        return self.snapshot()

    def _resolve_href(self, href: str | None) -> str | None:
        if not href:
            return None
        href = href.strip()
        if not href or href.startswith(('#', 'javascript:', 'data:', 'mailto:', 'tel:')):
            return None
        absolute = urljoin(self._page.url, href)
        return absolute

    def _observe_element(self, item, kind: str, eid: str) -> VisibleElement:
        aria = item.get_attribute('aria-label') or ''
        placeholder = item.get_attribute('placeholder') or ''
        name = item.get_attribute('name') or ''
        el_id_attr = item.get_attribute('id') or ''
        role = item.get_attribute('role') or kind
        disabled = bool(item.is_disabled()) if hasattr(item, 'is_disabled') else False
        try:
            disabled = disabled or item.evaluate(
                '(el) => Boolean(el.disabled || el.getAttribute("aria-disabled") === "true")'
            )
        except Exception:
            pass

        readonly = False
        input_type = None
        checked = None
        selected = None
        href = None
        value = None
        value_redacted = False

        if kind == 'button':
            label = aria or placeholder or (item.inner_text() or '') or name
        elif kind == 'a':
            label = aria or (item.inner_text() or '') or name or (item.get_attribute('title') or '')
            href = self._resolve_href(item.get_attribute('href'))
        elif kind == 'select':
            label = aria or name or el_id_attr or placeholder
            try:
                selected = item.input_value()
            except Exception:
                selected = None
            selected = _truncate(selected, MAX_VALUE_CHARS)
        else:
            # input / textarea
            input_type = (item.get_attribute('type') or ('text' if kind == 'textarea' else 'text')).lower()
            label = aria or placeholder or name or el_id_attr
            try:
                readonly = bool(
                    item.evaluate(
                        '(el) => Boolean(el.readOnly || el.getAttribute("aria-readonly") === "true")'
                    )
                )
            except Exception:
                readonly = False
            if input_type in ('checkbox', 'radio'):
                try:
                    checked = bool(item.is_checked())
                except Exception:
                    checked = None
            elif input_type in _SENSITIVE_INPUT_TYPES or looks_sensitive_identifier(
                aria, placeholder, name, el_id_attr, label
            ):
                value = None
                value_redacted = True
            else:
                try:
                    raw = item.input_value()
                except Exception:
                    raw = None
                raw, redacted = redact_if_sensitive_value(raw)
                value_redacted = redacted
                value = _truncate(raw, MAX_VALUE_CHARS)

        if kind == 'select' and looks_sensitive_identifier(aria, name, el_id_attr, label):
            selected = '[REDACTED]'
            value_redacted = True

        return VisibleElement(
            element_id=eid,
            kind=kind,
            label=(label or '').strip()[:MAX_LABEL_CHARS],
            value=value,
            placeholder=_truncate(placeholder or None, MAX_LABEL_CHARS),
            role=_truncate(role, 40),
            input_type=input_type,
            disabled=bool(disabled),
            readonly=bool(readonly),
            checked=checked,
            selected=selected,
            href=_truncate(href, 240) if href else None,
            value_redacted=value_redacted,
        )

    def snapshot(self, *, previous: PageSnapshot | None = None) -> PageSnapshot:
        self._element_map.clear()
        self._snapshot_id += 1
        elements: list[VisibleElement] = []
        # Prefer form controls over anchors so dense nav sidebars cannot starve observations.
        form_locator = self._page.locator('button, input, textarea, select')
        link_locator = self._page.locator('a[href]')
        form_count = form_locator.count()
        link_budget = max(0, MAX_VISIBLE_ELEMENTS - min(form_count, MAX_VISIBLE_ELEMENTS))
        scanned = 0

        def _add(item, kind: str, seq: int) -> None:
            nonlocal scanned
            try:
                if not item.is_visible():
                    return
            except Exception:
                return
            eid = f's{self._snapshot_id}_e{seq}'
            observed = self._observe_element(item, kind, eid)
            if kind == 'a':
                if not observed.href:
                    return
                try:
                    validate_target(observed.href, self.allowed_origin)
                except (ValueError, TypeError):
                    return
            self._element_map[eid] = (item, kind)
            elements.append(observed)
            scanned += 1

        for idx in range(min(form_count, MAX_VISIBLE_ELEMENTS)):
            item = form_locator.nth(idx)
            kind = item.evaluate('(el) => el.tagName.toLowerCase()')
            _add(item, kind, scanned)
            if len(elements) >= MAX_VISIBLE_ELEMENTS:
                break

        if len(elements) < MAX_VISIBLE_ELEMENTS and link_budget:
            for idx in range(min(link_locator.count(), link_budget * 3)):
                if len(elements) >= MAX_VISIBLE_ELEMENTS:
                    break
                item = link_locator.nth(idx)
                _add(item, 'a', scanned)

        visible_text = self._page.locator('body').inner_text(timeout=10_000)[:MAX_VISIBLE_TEXT_CHARS]
        snap = PageSnapshot(
            snapshot_id=self._snapshot_id,
            url=self._page.url,
            title=self._page.title(),
            visible_text=visible_text,
            elements=elements,
            control_changes=[],
        )
        prior = previous if previous is not None else self._last_snapshot
        if prior is not None:
            snap.control_changes = diff_control_values(prior, snap)
        self._last_snapshot = snap
        return snap

    def act(self, proposed: Decision) -> PageSnapshot | None:
        if self._closed:
            raise RuntimeError('browser is closed')
        if proposed.action == Action.STOP:
            self._element_map.clear()
            return None
        if proposed.action == Action.OBSERVE:
            return self.snapshot(previous=self._last_snapshot)
        if proposed.action == Action.RELOAD:
            self._element_map.clear()
            self._page.reload(wait_until='domcontentloaded', timeout=10_000)
            validate_target(self._page.url, self.allowed_origin)
            return self.snapshot()
        if proposed.element_id not in self._element_map:
            raise ValueError('Missing or expired snapshot element_id')
        item, kind = self._element_map[proposed.element_id]
        prior = self._last_snapshot
        self._element_map.clear()
        if proposed.action == Action.CLICK:
            if kind == 'button':
                item.click(timeout=10_000)
            elif kind == 'a':
                href = self._resolve_href(item.get_attribute('href'))
                if not href:
                    raise ValueError('Link has no navigable href under the safety policy')
                validate_target(href, self.allowed_origin)
                item.click(timeout=10_000)
                self._page.wait_for_load_state('domcontentloaded', timeout=10_000)
                validate_target(self._page.url, self.allowed_origin)
            elif kind == 'input':
                input_type = (item.get_attribute('type') or 'text').lower()
                if input_type in ('submit', 'button', 'checkbox', 'radio'):
                    item.click(timeout=10_000)
                else:
                    raise ValueError('Only visible buttons, links, or checkbox/radio/submit inputs are clickable')
            else:
                raise ValueError('Only a visible button, link, or toggle-like input is clickable')
        elif proposed.action == Action.FILL:
            if kind not in ('input', 'textarea'):
                raise ValueError('Only visible text inputs are fillable in Phase 1a')
            input_type = (item.get_attribute('type') or 'text').lower() if kind == 'input' else 'text'
            if input_type in ('submit', 'button', 'checkbox', 'radio', 'file', 'hidden', 'password'):
                raise ValueError('This input type is not fillable under the safety policy')
            if looks_sensitive_identifier(
                item.get_attribute('aria-label'),
                item.get_attribute('placeholder'),
                item.get_attribute('name'),
                item.get_attribute('id'),
            ):
                raise ValueError('Refusing to fill a control that appears credential-related')
            item.fill(proposed.value, timeout=10_000)
        else:
            raise ValueError('Unsupported action')
        validate_target(self._page.url, self.allowed_origin)
        # Brief settle for reactive UIs without application-specific waits.
        try:
            self._page.wait_for_timeout(150)
        except Exception:
            pass
        return self.snapshot(previous=prior)

    def screenshot(self, path: str):
        self._page.screenshot(path=path, full_page=True, timeout=10_000)
