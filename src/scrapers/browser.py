import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from src.core.config import ScraperSettings
from src.utils.urls import same_path

SKIPPED_RESOURCES = {"image", "media", "font"}


class ScraperError(RuntimeError):
    pass


class Browser:
    """A headless Chromium session for reading public pages"""

    def __init__(self, settings: ScraperSettings, locale: str = "en-US"):
        self.settings = settings
        self.locale = locale
        self.visited = False

    def __enter__(self) -> "Browser":
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(headless=self.settings.headless)
        except PlaywrightError as e:
            self.playwright.stop()
            raise ScraperError(
                "Chromium is not installed. Run: uv run playwright install chromium"
            ) from e
        context = self.browser.new_context(
            locale=self.locale, viewport={"width": 1280, "height": 900}
        )
        context.route("**/*", self._route)
        self.page = context.new_page()
        self.page.set_default_timeout(self.settings.timeout_s * 1000)
        return self

    def __exit__(self, *exc) -> None:
        self.browser.close()
        self.playwright.stop()

    def open(
        self, url: str, expect: str | None = None, expect_timeout_s: float = 15
    ) -> dict | None:
        """Load a page. With `expect`, return the JSON of the first response whose URL contains
        it, or None if the page never makes that request or redirects to another path."""
        if self.visited:
            time.sleep(self.settings.delay_s)
        self.visited = True
        matched = []

        def on_response(response) -> None:
            if expect and expect in response.url:
                matched.append(response)

        self.page.on("response", on_response)
        data = None
        try:
            self.page.goto(url, wait_until="domcontentloaded")
            redirected = not same_path(self.page.url, url)
            deadline = time.monotonic() + expect_timeout_s
            while expect and not matched and not redirected and time.monotonic() < deadline:
                self.page.wait_for_timeout(100)
            data = matched[0].json() if matched else None
        except (PlaywrightError, ValueError):
            pass
        finally:
            self.page.remove_listener("response", on_response)
        if self.page.title() == "Access Denied":
            raise ScraperError(f"Blocked while loading {url}. Try again later or use Apify.")
        return data

    def wait_for(self, selector: str, timeout_s: float = 8) -> bool:
        try:
            self.page.wait_for_selector(selector, state="attached", timeout=timeout_s * 1000)
            return True
        except PlaywrightError:
            return False

    def wait_for_any(
        self, selector: str | None = None, texts: tuple[str, ...] = (), timeout_s: float = 8
    ) -> bool:
        """Wait until `selector` exists or the page text contains one of `texts`, whichever
        comes first, so a known failure page ends the wait early."""
        try:
            self.page.wait_for_function(
                "([sel, texts]) => (sel && document.querySelector(sel)) || "
                "texts.some(t => document.body && document.body.innerText.includes(t))",
                arg=[selector, list(texts)],
                timeout=timeout_s * 1000,
                polling=100,
            )
            return True
        except PlaywrightError:
            return False

    def meta(self) -> dict[str, str]:
        return self.page.eval_on_selector_all(
            "meta[property^='og:'], meta[name='description']",
            "els => Object.fromEntries(els.map(e => "
            "[e.getAttribute('property') || e.getAttribute('name'), e.content]))",
        )

    @staticmethod
    def _route(route) -> None:
        if route.request.resource_type in SKIPPED_RESOURCES:
            route.abort()
        else:
            route.continue_()
