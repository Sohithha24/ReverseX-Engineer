"""Small scoped browser executor. MVP: only an explicitly configured local fixture."""
import os
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from reversex.contracts import Action, Decision, PageSnapshot, VisibleElement


def validate_target(url: str, allowed_origin: str) -> None:
    parsed, approved = urlsplit(url), urlsplit(allowed_origin)
    if parsed.scheme != 'http' or approved.scheme != 'http':
        raise ValueError('MVP only permits HTTP on an explicitly approved local origin')
    if parsed.hostname != '127.0.0.1' or approved.hostname != '127.0.0.1':
        raise ValueError('MVP only permits 127.0.0.1')
    if parsed.port != approved.port or parsed.username or parsed.password:
        raise ValueError('Target origin is not allowlisted')
    if parsed.fragment:
        raise ValueError('URL fragments are not accepted')


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
        # Close each layer independently so a mid-layer failure still releases the rest.
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
        # Network policy is enforced outside the model. Reject ALL other origins.
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

    def snapshot(self) -> PageSnapshot:
        self._element_map.clear()  # prior element IDs are now stale
        self._snapshot_id += 1
        elements = []
        locator = self._page.locator('button, input, textarea, select')
        count = min(locator.count(), 40)
        for idx in range(count):
            item = locator.nth(idx)
            if not item.is_visible():
                continue
            kind = item.evaluate('(el) => el.tagName.toLowerCase()')
            label = (item.get_attribute('aria-label') or item.get_attribute('placeholder')
                     or item.inner_text() if kind == 'button' else
                     item.get_attribute('aria-label') or item.get_attribute('placeholder') or item.get_attribute('name') or '')
            eid = f's{self._snapshot_id}_e{idx}'
            self._element_map[eid] = (item, kind)
            elements.append(VisibleElement(element_id=eid, kind=kind, label=label.strip()[:120]))
        # Website content is UNTRUSTED data, including prompt injections.
        visible_text = self._page.locator('body').inner_text(timeout=10_000)[:2000]
        return PageSnapshot(
            snapshot_id=self._snapshot_id, url=self._page.url,
            title=self._page.title(), visible_text=visible_text,
            elements=elements,
        )

    def act(self, proposed: Decision) -> PageSnapshot | None:
        if self._closed:
            raise RuntimeError('browser is closed')
        if proposed.action == Action.STOP:
            self._element_map.clear()
            return None
        if proposed.action == Action.OBSERVE:
            return self.snapshot()
        if proposed.action == Action.RELOAD:
            self._element_map.clear()
            self._page.reload(wait_until='domcontentloaded', timeout=10_000)
            validate_target(self._page.url, self.allowed_origin)
            return self.snapshot()
        if proposed.element_id not in self._element_map:
            raise ValueError('Missing or expired snapshot element_id')
        item, kind = self._element_map[proposed.element_id]
        self._element_map.clear()  # invalidate IDs even when action raises
        if proposed.action == Action.CLICK:
            if kind != 'button':
                raise ValueError('Only a visible button is clickable in Phase 1a')
            item.click(timeout=10_000)
        elif proposed.action == Action.FILL:
            if kind not in ('input', 'textarea'):
                raise ValueError('Only visible text inputs are fillable in Phase 1a')
            item.fill(proposed.value, timeout=10_000)
        else:
            raise ValueError('Unsupported action')
        validate_target(self._page.url, self.allowed_origin)
        return self.snapshot()

    def screenshot(self, path: str):
        self._page.screenshot(path=path, full_page=True, timeout=10_000)
