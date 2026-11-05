"""
automation/console.py
كل خطوات Google Cloud Console — سريع + تصوير كل خطوة/تغيير صفحة
"""
import asyncio
from urllib.parse import urlparse
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("Console")


class CloudConsole:
    def __init__(self, context, sender=None, user_tag=None):
        self.context = context
        self.sender = sender            # async def sender(img_bytes, label)
        self.user_tag = user_tag or "@user"
        self._last_url = ""
        self._shot_count = 0
        self._shot_lock = asyncio.Lock()

    # ═══════════════════════════════════════
    # أدوات التصوير
    # ═══════════════════════════════════════

    @staticmethod
    def _short_url(url: str) -> str:
        try:
            p = urlparse(url or "")
            return f"{p.netloc}{p.path[:48]}"
        except Exception:
            return (url or "")[:70]

    async def _shot(self, page, label=""):
        """تصوير + إرسال بالخلفية (لا يُبطئ الأتمتة)"""
        if not self.sender:
            return
        try:
            img = await page.screenshot(type="jpeg", quality=65, full_page=False)
        except Exception as e:
            log.debug(f"_shot capture: {e}")
            return
        self._shot_count += 1
        try:
            asyncio.create_task(self._send(img, label or f"shot-{self._shot_count}"))
        except Exception:
            pass

    async def _send(self, img_bytes, label):
        try:
            await self.sender(img_bytes, label)
        except Exception as e:
            log.debug(f"_send: {e}")

    async def _check_nav(self, page, tag=""):
        """إذا تغيّر URL → صورة تلقائية"""
        try:
            url = page.url or ""
        except Exception:
            return
        if not url or url == self._last_url:
            return
        self._last_url = url
        await self._shot(page, f"🌐 {tag} → {self._short_url(url)}")

    # ═══════════════════════════════════════
    # STEP 1: TOS الأولى
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: Welcome / TOS")
        await self._check_nav(page, "step1")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(400)
        await self._shot(page, "1️⃣ بداية الصفحة")

        try:
            is_tos = await page.evaluate("""
                () => {
                    const url = window.location.href.toLowerCase();
                    if (url.includes('workspacetermsofservice') || url.includes('speedbump')) return true;
                    const text = (document.body.innerText || '').toLowerCase();
                    if (text.includes('welcome to your new account')) return true;
                    for (const el of document.querySelectorAll('button, [role="button"]')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t.includes('i understand')) return true;
                    }
                    return false;
                }
            """)
        except Exception:
            return

        if not is_tos:
            log.info("ℹ️ ماشي TOS")
            return

        await self._shot(page, "1️⃣ TOS مكتشف")

        try:
            target = await page.evaluate("""
                () => {
                    const kws = ['i understand', 'agree and continue', 'accept'];
                    for (const el of document.querySelectorAll('button, a, [role="button"], input[type="submit"]')) {
                        if (el.offsetParent === null || el.disabled) continue;
                        const t = (el.innerText || el.value || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t.includes(kw)) {
                                const r = el.getBoundingClientRect();
                                return {
                                    text: (el.innerText || el.value || '').trim(),
                                    x: Math.round(r.x + r.width / 2),
                                    y: Math.round(r.y + r.height / 2),
                                };
                            }
                        }
                    }
                    return null;
                }
            """)
        except Exception:
            return

        if not target:
            return

        log.info(f"🎯 '{target['text']}' @({target['x']},{target['y']})")
        try:
            await page.mouse.move(target["x"] - 100, target["y"] - 50, steps=4)
            await page.wait_for_timeout(80)
            await page.mouse.move(target["x"], target["y"], steps=3)
            await page.wait_for_timeout(80)
            await page.mouse.down(); await page.wait_for_timeout(60); await page.mouse.up()
            log.info("✅ mouse click")
            await self._shot(page, "1️⃣ TOS مضغوط")
        except Exception as e:
            log.warning(f"❌ mouse: {e}")
            try:
                await page.get_by_role("button", name="I understand").click(timeout=3000)
            except Exception:
                pass

        # انتظار ذكي: نخرج بمجرد اختفاء الزر
        try:
            await page.wait_for_function(
                """() => {
                    for (const el of document.querySelectorAll('button, [role="button"]')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').toLowerCase();
                        if (t.includes('i understand') || t.includes('agree and continue')) return false;
                    }
                    return true;
                }""",
                timeout=12000,
            )
            log.info("✅ TOS اختفت")
            await self._check_nav(page, "step1-done")
            await self._shot(page, "1️⃣ TOS انتهت")
        except Exception:
            pass

    # ═══════════════════════════════════════
    # STEP 2: Terms Dialog
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2: Terms Dialog")
        await self._check_nav(page, "step2")

        has_dialog = False
        for _ in range(10):
            try:
                has_dialog = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').toLowerCase();
                            if (t.includes('terms of service') || t.includes('i agree to')) return true;
                        }
                        return false;
                    }
                """)
                if has_dialog:
                    break
            except Exception:
                pass
            await page.wait_for_timeout(250)

        if not has_dialog:
            log.info("ℹ️ ما كاينش Dialog")
            return

        log.info("📋 لقينا Dialog")
        await self._shot(page, "2️⃣ Terms Dialog")

        # checkbox
        try:
            cb = await page.evaluate("""
                () => {
                    const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                    for (const d of dialogs) {
                        if (d.offsetParent === null) continue;
                        for (const sel of ['input[type="checkbox"]', '[role="checkbox"]', 'mat-checkbox']) {
                            for (const el of d.querySelectorAll(sel)) {
                                if (el.offsetParent === null) continue;
                                const r = el.getBoundingClientRect();
                                if (r.width === 0 || r.height === 0) continue;
                                return { x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2) };
                            }
                        }
                    }
                    return null;
                }
            """)
            if cb:
                await page.mouse.click(cb["x"], cb["y"])
                await page.wait_for_timeout(400)
                await self._shot(page, "2️⃣ checkbox مفعّل")
        except Exception as e:
            log.warning(f"checkbox: {e}")

        # زر agree
        agree = None
        for _ in range(10):
            try:
                agree = await page.evaluate("""
                    () => {
                        const kws = ['agree and continue', 'i agree', 'accept', 'agree'];
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || el.value || '').trim().toLowerCase();
                            for (const kw of kws) {
                                if (t === kw || t.includes(kw)) {
                                    const r = el.getBoundingClientRect();
                                    if (r.width === 0 || r.height === 0) continue;
                                    const disabled = el.disabled ||
                                                    el.getAttribute('aria-disabled') === 'true' ||
                                                    el.classList.contains('mat-button-disabled');
                                    return { x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), disabled };
                                }
                            }
                        }
                        return null;
                    }
                """)
                if agree and not agree["disabled"]:
                    break
            except Exception:
                pass
            await page.wait_for_timeout(400)

        if not agree:
            return

        try:
            await page.mouse.click(agree["x"], agree["y"])
            log.info("✅ Agree")
            await self._shot(page, "2️⃣ موافقة")
        except Exception:
            pass

        try:
            await page.wait_for_function(
                """() => {
                    for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').toLowerCase();
                        if (t.includes('terms of service') || t.includes('i agree')) return false;
                    }
                    return true;
                }""",
                timeout=15000,
            )
            log.info("✅ Dialog اختفى")
            await self._check_nav(page, "step2-done")
            await self._shot(page, "2️⃣ Dialog انتهى")
        except Exception:
            pass

    # ═══════════════════════════════════════
    # STEP 3: Enable API
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        # اسحب أي dialog عالق
        try:
            await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('button, [role="button"]')) {
                        const t = (el.innerText || '').toLowerCase();
                        if (t.includes('agree')) { try { el.disabled = false; el.click(); } catch(e){} }
                    }
                }
            """)
        except Exception:
            pass

        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        log.info("🚀 step3: Enable API")
        await page.goto(api_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(600)
        await self._check_nav(page, "step3")
        await self._shot(page, "3️⃣ صفحة API")

        enable_btn = page.get_by_role("button", name="Enable")
        manage_btn = page.get_by_role("button", name="Manage")
        disable_btn = page.get_by_text("Disable API")

        for attempt in range(60):  # 60 × 400ms = 24s
            try:
                if await enable_btn.count() > 0 and await enable_btn.is_visible():
                    await enable_btn.click()
                    await self._shot(page, "3️⃣ Enable مضغوط")
                    try:
                        await expect(manage_btn.or_(disable_btn)).to_be_visible(timeout=90000)
                    except Exception:
                        pass
                    await self._check_nav(page, "step3-done")
                    await self._shot(page, "3️⃣ API مفعل")
                    return
                if await manage_btn.count() > 0 and await manage_btn.is_visible():
                    await self._shot(page, "3️⃣ API مفعل مسبقاً")
                    return
            except Exception:
                pass
            await page.wait_for_timeout(400)

        raise RuntimeError("ما لقيناش زر Enable ولا Manage")

    # ═══════════════════════════════════════
    # STEP 4: Create Cloud Run
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        log.info("🌐 step4: Create Cloud Run")
        await page.goto(run_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(700)
        await self._check_nav(page, "step4")
        await self._shot(page, "4️⃣ صفحة الإنشاء")

        image_found = False
        for attempt in range(20):  # 20 × 400ms = 8s
            for clicker in (
                lambda: page.get_by_text("Container Image URL").first.click(),
                lambda: page.locator('input[aria-label*="Container Image URL" i]').first.click(),
                lambda: page.locator('text=/Container Image/i').first.click(),
            ):
                try:
                    await clicker()
                    image_found = True
                    break
                except Exception:
                    continue
            if image_found:
                break
            # JS fallback
            try:
                clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('*')) {
                            const t = (el.innerText || '').trim();
                            if (t.includes('Container Image URL') && t.length < 100) {
                                try { el.click(); return true; } catch(e){}
                            }
                        }
                        return false;
                    }
                """)
                if clicked:
                    image_found = True
                    break
            except Exception:
                pass
            await page.wait_for_timeout(400)

        if not image_found:
            try:
                await page.locator('input[type="text"]').first.click()
            except Exception as e:
                raise RuntimeError(f"فشل لقاء حقل الصورة: {e}")

        await page.wait_for_timeout(200)
        await page.keyboard.type(image, delay=15)
        log.info("✅ رابط الحاوية")
        await self._shot(page, "4️⃣ الصورة مكتوبة")

        try:
            await page.get_by_role("radio", name="Allow public access").click(timeout=4000)
        except Exception:
            pass
        try:
            await page.get_by_role("radio", name="Instance-based").click(timeout=4000)
        except Exception:
            pass
        try:
            await page.get_by_role("button", name="Hide").click(timeout=1000)
        except Exception:
            pass

        await page.keyboard.press("End")
        await page.wait_for_timeout(300)

        try:
            await page.get_by_role("button", name="Create").click(force=True)
            log.info("✅ Create")
            await self._shot(page, "4️⃣ Create مضغوط")
        except Exception as e:
            raise RuntimeError(f"فشل الإعدادات: {e}")

    # ═══════════════════════════════════════
    # STEP 5: Get URL
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page, project_id=None, authuser="1"):
        import re

        def clean_url(value):
            if not value:
                return None
            m = re.search(r'https?://[a-z0-9.\-]+\.run\.app', str(value), flags=re.IGNORECASE)
            return m.group(0).rstrip(".,);]}>") if m else None

        async def scan_current_page():
            try:
                values = await page.evaluate("""
                    () => {
                        const out = [];
                        for (const a of document.querySelectorAll('a')) {
                            out.push(a.href || '', a.innerText || '', a.getAttribute('aria-label') || '');
                        }
                        for (const el of document.querySelectorAll('[href], [title], [aria-label], input, code')) {
                            out.push(el.getAttribute('href') || '');
                            out.push(el.getAttribute('title') || '');
                            out.push(el.getAttribute('aria-label') || '');
                            if ('value' in el) out.push(el.value || '');
                            out.push(el.innerText || '');
                        }
                        out.push(document.body ? document.body.innerText : '');
                        return out.join('\\n');
                    }
                """)
                return clean_url(values)
            except Exception:
                return None

        log.info("🚀 step5: البحث عن URL")
        # 60 × 500ms = 30s بمراقبة URL
        for attempt in range(60):
            await self._check_nav(page, "step5")
            found = await scan_current_page()
            if found:
                log.info(f"✅ URL: {found}")
                await self._shot(page, f"5️⃣ رابط الخدمة")
                return found

            try:
                body = (await page.locator("body").inner_text(timeout=2000)).lower()
                for term in ("failed to create", "creation failed", "could not create", "deployment failed"):
                    if term in body:
                        await self._shot(page, "5️⃣ فشل الإنشاء")
                        raise RuntimeError("Cloud Run عرض رسالة فشل. راجع السجل.")
            except RuntimeError:
                raise
            except Exception:
                pass

            await page.wait_for_timeout(500)

        # fallback: صفحة الخدمات
        if project_id:
            services_url = f"https://console.cloud.google.com/run?project={project_id}&authuser={authuser}"
            try:
                await page.goto(services_url, wait_until="domcontentloaded", timeout=45000)
                await self._check_nav(page, "step5-services")
                await self._shot(page, "5️⃣ صفحة الخدمات")
                for _ in range(60):  # 30s
                    found = await scan_current_page()
                    if found:
                        log.info(f"✅ URL في الخدمات: {found}")
                        await self._shot(page, "5️⃣ رابط في الخدمات")
                        return found

                    href = await page.evaluate("""
                        () => {
                            const a = [...document.querySelectorAll('a[href]')]
                                .find(x => /\\/run\\/detail\\//.test(x.getAttribute('href')||''));
                            return a ? a.href : null;
                        }
                    """)
                    if href:
                        try:
                            await page.goto(href, wait_until="domcontentloaded", timeout=30000)
                            await self._check_nav(page, "step5-detail")
                            found = await scan_current_page()
                            if found:
                                log.info(f"✅ URL في التفاصيل: {found}")
                                await self._shot(page, "5️⃣ رابط في التفاصيل")
                                return found
                            await page.go_back(wait_until="domcontentloaded", timeout=20000)
                        except Exception:
                            pass
                    await page.wait_for_timeout(500)
            except Exception as e:
                log.warning(f"قائمة الخدمات: {e}")

        raise RuntimeError(
            "لم يظهر رابط run.app. تأكد من نجاح النشر وصحة صورة الحاوية."
        )
