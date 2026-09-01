"""SICAU v2 service: Playwright-driven WebVPN login + jiaowu DOM nav + parse → DSL.

Per request: open a fresh `BrowserContext` (isolated storage/cookies), navigate
the CAS WebVPN login, OCR the captcha, click through jiaowu menu to the
timetable iframe, and parse the inner HTML using `parse_timetable_iframe_html`.
DSL conversion reuses `sicau_timetable.scraper.to_dsl`.
"""
import base64
import logging
from datetime import datetime

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from ..sicau_timetable.service import (
    FetchError,
    LoginError,
    _decode_sicau_bytes,
)
from ..sicau_timetable.scraper import to_dsl
from .browser import PlaywrightHolder
from .captcha_ocr import read_captcha
from .scraper import parse_timetable_iframe_html

logger = logging.getLogger(__name__)


# CAS WebVPN login entry — the `service` param targets the VPN auth flow.
VPN_LOGIN_URL = (
    "https://webvpn.sicau.edu.cn/https/77726476706e69737468656265737421"
    "f1e25594692361537f1dc7a99c406d36ef/wui/#/?appid=aea49a21-6b26-4e8f-bcfc"
    "-80e3de591c93&service=https%3A%2F%2Fwebvpn.sicau.edu.cn%2Flogin%3Fcas_login%3Dtrue"
)

# jiaowu's hex-encoded VPN host (教务处 card on the WebVPN home).
VPN_JIAOWU_HOST_HEX = "77726476706e69737468656265737421fafe409330252643770b88b9d65027203418e0"

# Locator hints — Chinese text reconstructed via String.fromCharCode in JS so we
# don't depend on file-encoding for these literals at call time.
_PWD_TAB_CLICK = "document.getElementById('tab-1-tab').click()"
_LOCATE_CAPTCHA_IMG = "#tab-1 img[src^='data:image/png;base64,']"


async def fetch_timetable_dsl_v2(
    browser_holder: PlaywrightHolder,
    user_id: str,
    password: str,
    semester: str,
    *,
    headless: bool = True,
    browser_timeout_ms: int = 60_000,
    captcha_max_retries: int = 30,
) -> dict:
    """Full stateless pipeline: WebVPN login → jiaowu nav → DSL.

    `captcha_max_retries` defaults to 30 because ddddocr's accuracy on this
    school's captcha style (~50% on 4-char reads) means we need many attempts
    to expect at least one correct OCR.
    """
    browser = browser_holder.browser
    if browser is None:
        raise FetchError("Playwright browser 未启动")

    async with await browser.new_context() as ctx:
        page = await ctx.new_page()
        page.set_default_timeout(browser_timeout_ms)

        await _login(page, user_id, password, captcha_max_retries=captcha_max_retries)
        jiaowu_page = await _open_jiaowu(ctx, page)
        await _navigate_to_timetable(jiaowu_page, semester)
        html = await _extract_timetable_html(jiaowu_page)

    text = html
    if "课程名称" not in text:
        try:
            text = html.encode("latin-1").decode("gbk")
        except (UnicodeDecodeError, UnicodeEncodeError):
            text = html

    courses = parse_timetable_iframe_html(text)
    dsl = to_dsl(courses)
    return {
        "user_id": user_id,
        "semester": semester,
        "dsl": dsl,
        "course_count": len(courses),
        "generated_at": datetime.now().astimezone(),
    }


# ---------- internals ----------


async def _login(
    page: Page, user_id: str, password: str, *, captcha_max_retries: int
) -> None:
    """Drive the WebVPN CAS login.

    Race-avoidance (the observed failure mode: after a rejected submit Vue
    fires refresh XHR #1, our own click fired XHR #2, and we OCR'd the image
    from #1 while the server already bound the uuid to #2 — every submit then
    reads as 验证码错误). Rules:
      - Never click the captcha img on the normal path. After a failed submit
        Vue refreshes automatically; we just wait for the NEW src and require
        it to be STABLE (unchanged ≥600ms) before reading — stability means
        the displayed image and Vue's uuid ref are aligned.
      - Only click when the previous round never submitted (invalid-length
        OCR) — Vue doesn't refresh in that case.
      - Fail fast on non-captcha errors (wrong password etc.) via the toast.
    """
    await page.goto(VPN_LOGIN_URL, wait_until="domcontentloaded")
    await page.evaluate(_PWD_TAB_CLICK)
    await page.wait_for_selector("#tab-1:not(.hidden)", timeout=10_000)
    await page.wait_for_selector(_LOCATE_CAPTCHA_IMG, timeout=10_000)

    submitted_src = ""   # captcha src our last submit was bound to
    need_click = False   # force refresh only when the last round didn't submit
    last_err: Exception | None = None

    for attempt in range(1, captcha_max_retries + 1):
        if _manual_captcha is not None:
            captcha_text = _manual_captcha
            logger.info("using manual captcha override: %r", captcha_text)
        else:
            src = await _stable_captcha_src(
                page, exclude=submitted_src, click=need_click
            )
            if src is None:
                last_err = LoginError(f"captcha 读取失败 (attempt {attempt}/{captcha_max_retries})")
                need_click = True
                continue
            captcha_text = await _ocr_captcha_src(page, src, attempt)

        if captcha_text is None:
            last_err = LoginError(f"captcha 读取失败 (attempt {attempt}/{captcha_max_retries})")
            need_click = True  # nothing submitted → Vue won't refresh → force it
            continue

        need_click = False
        await _submit_login(page, user_id, password, captcha_text)
        if "wui/" not in page.url:
            logger.info("login succeeded on attempt %d (text=%r)", attempt, captcha_text)
            return

        toast = await _read_error_toast(page)
        logger.info("login rejected on attempt %d (text=%r) toast=%r",
                    attempt, captcha_text, toast)
        if toast and "验证码" not in toast:
            raise LoginError(toast)  # 密码错误等 — 重试无意义
        last_err = LoginError(
            toast or f"验证码识别失败 (attempt {attempt}/{captcha_max_retries})"
        )
    raise last_err or LoginError("登录失败")


# Optional override for debugging the navigation flow without solving the
# captcha via OCR. Set with `set_manual_captcha("1234")` from a CLI tool.
_manual_captcha: str | None = None


def set_manual_captcha(value: str | None) -> None:
    """Force the next login attempt to use this 4-char captcha text."""
    global _manual_captcha
    _manual_captcha = value


async def _get_captcha_src(page: Page) -> str | None:
    """Current captcha data-URL from the DOM, or None."""
    return await page.evaluate(
        """() => {
            const imgs = document.querySelectorAll('#tab-1 img');
            for (const im of imgs) {
                if (im.src.startsWith('data:image/png;base64,')) return im.src;
            }
            return null;
        }"""
    )


async def _stable_captcha_src(
    page: Page, *, exclude: str, click: bool, timeout_s: float = 15.0
) -> str | None:
    """Wait for a captcha src != `exclude` that stays unchanged ≥600ms.

    Stability is the sync signal: Vue sets img.src and its uuid ref together
    from one API response, so a src that stops changing means image ↔ uuid
    are aligned. Returns the stable src or None on timeout.
    """
    import time

    if click:
        try:
            await page.locator(_LOCATE_CAPTCHA_IMG).first.click()
        except Exception:
            pass

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        src = await _get_captcha_src(page)
        if src and src != exclude:
            await page.wait_for_timeout(600)  # stability window
            if await _get_captcha_src(page) == src:
                return src
        await page.wait_for_timeout(200)
    return None


async def _ocr_captcha_src(
    page: Page, src: str, attempt_num: int
) -> str | None:
    """Decode + OCR one captcha src. Returns None for non-4-digit reads."""
    png_bytes = base64.b64decode(src.split(",", 1)[1])
    try:
        import os
        debug_dir = "D:/code/a_js/proj/rt/sicau_v2_debug"
        os.makedirs(debug_dir, exist_ok=True)
        with open(f"{debug_dir}/c_{attempt_num:03d}.png", "wb") as f:
            f.write(png_bytes)
    except Exception:
        pass
    text = read_captcha(png_bytes)
    logger.info("captcha attempt=%d text=%r len=%d", attempt_num, text, len(text))
    # Digits-only captcha: letters mean misread — discard, don't submit.
    if len(text) != 4 or not text.isdigit():
        return None
    return text


async def _read_error_toast(page: Page) -> str | None:
    """Read the el-message error toast text, if visible."""
    try:
        toast = page.locator(".el-message").last
        await toast.wait_for(state="visible", timeout=3_000)
        return (await toast.inner_text()).strip()
    except PlaywrightTimeout:
        return None
    except Exception:
        return None


async def _submit_login(page: Page, user_id: str, password: str, captcha_text: str) -> None:
    """Fill the form and click 登录. Vue reads uuid from its own Y.value ref."""
    await page.evaluate(
        """({u, p, c}) => {
            const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            const inputs = document.querySelectorAll('#tab-1 input');
            set.call(inputs[0], u); inputs[0].dispatchEvent(new Event('input', {bubbles:true}));
            set.call(inputs[1], p); inputs[1].dispatchEvent(new Event('input', {bubbles:true}));
            set.call(inputs[2], c); inputs[2].dispatchEvent(new Event('input', {bubbles:true}));
        }""",
        {"u": user_id, "p": password, "c": captcha_text},
    )
    await page.locator("#tab-1 button[type=submit]").click()
    # Wait for either redirect or for Vue to show error (caption doesn't change
    # until the next captcha refresh fires).
    await page.wait_for_timeout(2_500)


async def _open_jiaowu(ctx, page: Page) -> Page:
    """Navigate to the jiaowu management system via the WebVPN search box.

    The home page URL bar structure (from the live DOM):
      .portal-search-input-wrap
        ├─ .portal-search__dropdown  → el-select (http/https)
        ├─ input.portal-search__input (placeholder 输入网址直接访问内网或图书馆资源)
        └─ .portal-search__button    → paper-plane jump button
    Set protocol to https, enter the jiaowu URL, click jump.
    """
    await page.wait_for_selector(".portal-search-input-wrap", timeout=15_000)

    # 1. Open the protocol dropdown and pick https.
    await page.locator(".portal-search__dropdown .el-input__inner").click()
    await page.locator(".el-select-dropdown__item", has_text="https").first.click()

    # 2. Fill the URL input (Vue-friendly native setter).
    await page.evaluate(
        """() => {
            const input = document.querySelector('.portal-search__input');
            const set = Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype, 'value').set;
            set.call(input, 'https://jiaowu.sicau.edu.cn');
            input.dispatchEvent(new Event('input', {bubbles: true}));
        }"""
    )
    await page.wait_for_timeout(200)

    # 3. Click the jump (paper-plane) button.
    await page.locator(".portal-search__button").click()
    logger.info("search-box jump clicked")

    # 4. Poll: the jump lands on the jiaowu welcome page (web/web/web/index.asp).
    #    That page's 或统一身份认证登录 button is type=submit inside a form —
    #    clicking it triggers empty-form validation which swallows the
    #    navigation. Its onclick is just `location.replace('caslogin.asp')`,
    #    so navigate directly to the CAS login endpoint instead.
    vpn_jiaowu_base = (
        "https://webvpn.sicau.edu.cn/https/" + VPN_JIAOWU_HOST_HEX
    )
    cas_login_url = f"{vpn_jiaowu_base}/jiaoshi/aspsso/caslogin.asp"

    jiaowu_page = None
    for _ in range(100):  # up to 50s
        for p in list(ctx.pages):
            if "index1.asp" in p.url:
                jiaowu_page = p
                break
        if jiaowu_page is not None:
            break
        for p in list(ctx.pages):
            if "web/web/web/index.asp" in p.url:
                try:
                    await p.goto(cas_login_url, timeout=15_000)
                    logger.info("navigated to caslogin.asp")
                except Exception as e:
                    logger.warning("caslogin goto failed: %r", e)
        await page.wait_for_timeout(500)

    if jiaowu_page is None:
        raise FetchError(
            f"教务系统 tab 未打开 (pages={[p.url for p in ctx.pages]})"
        )
    await jiaowu_page.wait_for_load_state("domcontentloaded")
    return jiaowu_page


async def _navigate_to_timetable(page: Page, semester: str) -> None:
    """学生-课业信息 → 网上选(退)课 → <semester> → 选课情况(课表).

    The menu pages live inside iframes whose `src` attribute does NOT update
    when the frame navigates internally — so every step polls frames by their
    CONTENT instead of waiting on src selectors.
    """
    await page.wait_for_selector("dt", timeout=15_000)
    await page.locator("dt").filter(has_text="课业信息").first.click()
    await page.wait_for_timeout(300)
    await page.locator("a").filter(has_text="网上选(退)课").first.click()

    if not await _click_link_in_any_frame(page, semester):
        raise FetchError(f"学期链接未找到: {semester}")
    if not await _click_link_in_any_frame(page, "选课情况(课表)"):
        raise FetchError("选课情况(课表) 链接未找到")


async def _click_link_in_any_frame(
    page: Page, text: str, timeout_ms: int = 20_000
) -> bool:
    """Find a visible <a> with `text` in any (sub)frame and click it."""
    import time

    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for f in page.frames:
            if f == page.main_frame:
                continue
            try:
                loc = f.locator("a").filter(has_text=text).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click()
                    logger.info("clicked %r in frame %s", text, f.url[:80])
                    await page.wait_for_timeout(500)
                    return True
            except Exception:
                continue  # frame detached mid-check — try next
        await page.wait_for_timeout(300)
    return False


async def _extract_timetable_html(page: Page) -> str:
    """Find the frame containing the timetable detail table and return its HTML."""
    import time

    deadline = time.monotonic() + 25.0
    while time.monotonic() < deadline:
        for f in page.frames:
            if f == page.main_frame:
                continue
            try:
                content = await f.content()
                if "课程名称" in content and "上课时间" in content:
                    logger.info("timetable frame found: %s", f.url[:80])
                    return content
            except Exception:
                continue
        await page.wait_for_timeout(300)
    raise FetchError("课表 frame 未找到（无 课程名称 表头）")