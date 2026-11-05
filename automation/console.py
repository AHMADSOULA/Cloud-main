"""
automation/console.py
كل خطوات Google Cloud Console — صامت (بلا تقارير، بلا تصوير)
"""
import asyncio
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("Console")


class CloudConsole:
    def __init__(self, context, sender=None, user_tag=None):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"

    # ═══════════════════════════════════════
    # STEP 1: TOS الأولى
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: Welcome / TOS")

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1500)

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

        try:
            target = await page.evaluate("""
                () => {
                    const kws = ['i understand', 'agree and continue', 'accept'];
                    for (const el of document.querySelectorAll('button, a, [role="button"], input[type="submit"]')) {
                        if (el.offsetParent === null || el.disabled) continue;
                        const t = (el.innerText || el.value || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t.includes(kw)) {
                                const rect = el.getBoundingClientRect();
                                return {
                                    text: (el.innerText || el.value || '').trim(),
                                    x: Math.round(rect.x + rect.width / 2),
                                    y: Math.round(rect.y + rect.height / 2),
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
            await page.evaluate(f"""
                () => {{
                    const el = document.elementFromPoint({target['x']}, {target['y']});
                    if (el) el.scrollIntoView({{block: 'center', behavior: 'instant'}});
                }}
            """)
            await page.wait_for_timeout(500)

            target2 = await page.evaluate("""
                () => {
                    const kws = ['i understand', 'agree and continue', 'accept'];
                    for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                        if (el.offsetParent === null || el.disabled) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t.includes(kw)) {
                                const rect = el.getBoundingClientRect();
                                return {
                                    x: Math.round(rect.x + rect.width / 2),
                                    y: Math.round(rect.y + rect.height / 2),
                                };
                            }
                        }
                    }
                    return null;
                }
            """)
            if target2:
                target['x'] = target2['x']
                target['y'] = target2['y']

            await page.mouse.move(target['x'] - 100, target['y'] - 50, steps=6)
            await page.wait_for_timeout(150)
            await page.mouse.move(target['x'], target['y'], steps=5)
            await page.wait_for_timeout(200)
            await page.mouse.down()
            await page.wait_for_timeout(100)
            await page.mouse.up()
            log.info("✅ mouse click")
        except Exception as e:
            log.warning(f"❌ mouse فشل: {e}")
            try:
                await page.get_by_role("button", name="I understand").click(timeout=5000)
            except Exception:
                pass

        for i in range(12):
            await page.wait_for_timeout(1200)
            try:
                gone = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('i understand') || t.includes('agree and continue')) return false;
                        }
                        return true;
                    }
                """)
                if gone:
                    log.info(f"✅ TOS اختفت ~{(i+1)*1.2}s")
                    break
            except Exception:
                pass

    # ═══════════════════════════════════════
    # STEP 2: Terms Dialog
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2: Terms Dialog")

        has_dialog = False
        for _ in range(8):
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
            await page.wait_for_timeout(700)

        if not has_dialog:
            log.info("ℹ️ ما كاينش Dialog")
            return

        log.info("📋 لقينا Dialog")

        checkbox_info = None
        try:
            checkbox_info = await page.evaluate("""
                () => {
                    const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                    for (const dialog of dialogs) {
                        if (dialog.offsetParent === null) continue;
                        for (const el of dialog.querySelectorAll('input[type="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), checked: el.checked };
                        }
                        for (const el of dialog.querySelectorAll('[role="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), checked: el.getAttribute('aria-checked') === 'true' };
                        }
                        for (const el of dialog.querySelectorAll('mat-checkbox')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), checked: el.classList.contains('mat-checkbox-checked') };
                        }
                    }
                    return null;
                }
            """)
        except Exception:
            checkbox_info = None

        if checkbox_info and not checkbox_info['checked']:
            log.info(f"📋 checkbox @({checkbox_info['x']},{checkbox_info['y']})")
            try:
                await page.mouse.move(checkbox_info['x'] - 30, checkbox_info['y'] - 30, steps=5)
                await page.wait_for_timeout(150)
                await page.mouse.move(checkbox_info['x'], checkbox_info['y'], steps=5)
                await page.wait_for_timeout(200)
                await page.mouse.down()
                await page.wait_for_timeout(100)
                await page.mouse.up()
                log.info("✅ checkbox mouse")
                await page.wait_for_timeout(1800)

                checked_now = await page.evaluate("""
                    () => {
                        const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                        for (const dialog of dialogs) {
                            if (dialog.offsetParent === null) continue;
                            for (const el of dialog.querySelectorAll('input[type="checkbox"]')) {
                                if (el.offsetParent === null) continue;
                                if (el.checked) return true;
                            }
                            for (const el of dialog.querySelectorAll('[role="checkbox"]')) {
                                if (el.offsetParent === null) continue;
                                if (el.getAttribute('aria-checked') === 'true') return true;
                            }
                            for (const el of dialog.querySelectorAll('mat-checkbox')) {
                                if (el.offsetParent === null) continue;
                                if (el.classList.contains('mat-checkbox-checked')) return true;
                            }
                        }
                        return false;
                    }
                """)

                if not checked_now:
                    await page.evaluate("""
                        () => {
                            const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                            for (const dialog of dialogs) {
                                if (dialog.offsetParent === null) continue;
                                for (const el of dialog.querySelectorAll('mat-checkbox, [role="checkbox"], input[type="checkbox"]')) {
                                    if (el.offsetParent === null) continue;
                                    try { el.click(); return; } catch (e) {}
                                }
                            }
                        }
                    """)
                    await page.wait_for_timeout(1800)
            except Exception as e:
                log.warning(f"❌ checkbox: {e}")

        agree_target = None
        for _ in range(8):
            try:
                agree_target = await page.evaluate("""
                    () => {
                        const kws = ['agree and continue', 'i agree', 'accept', 'agree'];
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || el.value || '').trim().toLowerCase();
                            for (const kw of kws) {
                                if (t === kw || t.includes(kw)) {
                                    const rect = el.getBoundingClientRect();
                                    if (rect.width === 0 || rect.height === 0) continue;
                                    const disabled = el.disabled ||
                                                    el.getAttribute('aria-disabled') === 'true' ||
                                                    el.classList.contains('disabled') ||
                                                    el.classList.contains('mat-button-disabled');
                                    return {
                                        text: (el.innerText || el.value || '').trim(),
                                        x: Math.round(rect.x + rect.width / 2),
                                        y: Math.round(rect.y + rect.height / 2),
                                        disabled: disabled,
                                    };
                                }
                            }
                        }
                        return null;
                    }
                """)
                if agree_target and not agree_target['disabled']:
                    break
            except Exception:
                pass
            await page.wait_for_timeout(1000)

        if not agree_target:
            return

        log.info(f"🎯 Agree: '{agree_target['text']}' dis={agree_target['disabled']}")

        if agree_target['disabled']:
            try:
                await page.evaluate("""
                    () => {
                        const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                        for (const dialog of dialogs) {
                            if (dialog.offsetParent === null) continue;
                            for (const el of dialog.querySelectorAll('mat-checkbox')) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width === 0 || rect.height === 0) continue;
                                const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                                el.dispatchEvent(evt);
                            }
                        }
                    }
                """)
                await page.wait_for_timeout(1800)
            except Exception:
                pass

        try:
            await page.evaluate(f"""
                () => {{
                    const el = document.elementFromPoint({agree_target['x']}, {agree_target['y']});
                    if (el) el.scrollIntoView({{block: 'center', behavior: 'instant'}});
                }}
            """)
            await page.wait_for_timeout(500)

            await page.mouse.move(agree_target['x'] - 80, agree_target['y'] - 40, steps=6)
            await page.wait_for_timeout(150)
            await page.mouse.move(agree_target['x'], agree_target['y'], steps=5)
            await page.wait_for_timeout(200)
            await page.mouse.down()
            await page.wait_for_timeout(100)
            await page.mouse.up()
        except Exception:
            pass

        await page.wait_for_timeout(1200)

        still_open = await page.evaluate("""
            () => {
                for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                    if (el.offsetParent === null) continue;
                    const t = (el.innerText || '').toLowerCase();
                    if (t.includes('terms of service') || t.includes('i agree')) return true;
                }
                return false;
            }
        """)

        if still_open:
            try:
                await page.evaluate("""
                    () => {
                        const kws = ['agree and continue', 'i agree', 'accept'];
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            for (const kw of kws) {
                                if (t === kw || t.includes(kw)) {
                                    try {
                                        el.disabled = false;
                                        el.removeAttribute('disabled');
                                        el.removeAttribute('aria-disabled');
                                        el.click();
                                    } catch (e) {}
                                }
                            }
                        }
                    }
                """)
                await page.wait_for_timeout(2000)
            except Exception:
                pass

        for i in range(12):
            await page.wait_for_timeout(1200)
            try:
                gone = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').toLowerCase();
                            if (t.includes('terms of service') || t.includes('i agree')) return false;
                        }
                        return true;
                    }
                """)
                if gone:
                    log.info(f"✅ Dialog اختفى ~{(i+1)*1.2}s")
                    break
            except Exception:
                pass

    # ═══════════════════════════════════════
    # STEP 3: Enable API
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        try:
            dialog_open = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').toLowerCase();
                        if (t.includes('terms of service') || t.includes('i agree')) return true;
                    }
                    return false;
                }
            """)
            if dialog_open:
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('agree')) {
                                try { el.disabled = false; el.click(); } catch (e) {}
                            }
                        }
                    }
                """)
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        await page.goto(api_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        enable_btn = page.get_by_role("button", name="Enable")
        manage_btn = page.get_by_role("button", name="Manage")
        disable_btn = page.get_by_text("Disable API")

        for attempt in range(30):
            try:
                if await enable_btn.count() > 0 and await enable_btn.is_visible():
                    await enable_btn.click()
                    try:
                        await expect(manage_btn.or_(disable_btn)).to_be_visible(timeout=120000)
                    except Exception:
                        pass
                    return

                if await manage_btn.count() > 0 and await manage_btn.is_visible():
                    return
            except Exception:
                pass

            await page.wait_for_timeout(1200)

        raise RuntimeError("ما لقيناش زر Enable ولا Manage")

    # ═══════════════════════════════════════
    # STEP 4: Create Cloud Run
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        log.info(f"🌐 Create Cloud Run")
        await page.goto(run_url, wait_until="domcontentloaded")

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(4000)

        # ✅ نلقاو حقل Container Image URL — 4 استراتيجيات
        image_found = False
        for attempt in range(15):
            try:
                try:
                    label = page.get_by_text("Container Image URL").first
                    if await label.count() > 0 and await label.is_visible():
                        await label.click()
                        image_found = True
                        log.info("✅ get_by_text")
                        break
                except Exception:
                    pass

                try:
                    inp = page.locator('input[aria-label*="Container Image URL" i]').first
                    if await inp.count() > 0 and await inp.is_visible():
                        await inp.click()
                        image_found = True
                        log.info("✅ input[aria-label]")
                        break
                except Exception:
                    pass

                try:
                    el = page.locator('text=/Container Image/i').first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        image_found = True
                        log.info("✅ text regex")
                        break
                except Exception:
                    pass

                try:
                    clicked = await page.evaluate("""
                        () => {
                            const els = document.querySelectorAll('*');
                            for (const el of els) {
                                const t = (el.innerText || '').trim();
                                if (t.includes('Container Image URL') && t.length < 100) {
                                    try { el.click(); return 'ok'; } catch (e) {}
                                }
                            }
                            return null;
                        }
                    """)
                    if clicked:
                        image_found = True
                        log.info("✅ JS click")
                        break
                except Exception:
                    pass
            except Exception:
                pass

            await page.wait_for_timeout(1200)

        if not image_found:
            try:
                inp = page.locator('input[type="text"]').first
                if await inp.count() > 0:
                    await inp.click()
                    log.info("ℹ️ أول input")
                else:
                    raise RuntimeError("ما لقيناش حقل Image")
            except Exception as e:
                raise RuntimeError(f"فشل لقاء حقل: {str(e)}")

        try:
            await page.wait_for_timeout(400)
            await page.keyboard.type(image, delay=40)
            log.info("✅ رابط الحاوية")
        except Exception as e:
            raise RuntimeError(f"فشل كتابة الرابط: {str(e)}")

        await page.wait_for_timeout(2000)

        try:
            try:
                await page.get_by_role("radio", name="Allow public access").click(timeout=10000)
            except Exception:
                pass
            try:
                await page.get_by_role("radio", name="Instance-based").click(timeout=10000)
            except Exception:
                pass
            try:
                await page.get_by_role("button", name="Hide").click(timeout=2000)
            except Exception:
                pass

            await page.keyboard.press("End")
            await page.wait_for_timeout(600)

            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True)
            log.info("✅ Create")
        except Exception as e:
            raise RuntimeError(f"فشل الإعدادات: {str(e)}")

    # ═══════════════════════════════════════
    # STEP 5: Get URL
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page, project_id=None, authuser="1"):
        """
        استخراج رابط الخدمة بعد اكتمال إنشاء Cloud Run.
        يدعم الروابط الموجودة في الصفحة، النص، خصائص العناصر،
        وصفحة تفاصيل الخدمة وقائمة الخدمات.
        """
        import re
        from urllib.parse import urlparse

        def clean_url(value):
            if not value:
                return None
            match = re.search(
                r'https?://[a-z0-9.-]+\.run\.app',
                str(value),
                flags=re.IGNORECASE
            )
            if not match:
                return None
            return match.group(0).rstrip(".,);]}>")

        async def scan_current_page():
            try:
                values = await page.evaluate("""
                    () => {
                        const out = [];
                        for (const a of document.querySelectorAll('a')) {
                            out.push(a.href || '');
                            out.push(a.innerText || '');
                            out.push(a.getAttribute('aria-label') || '');
                        }
                        for (const el of document.querySelectorAll(
                            '[href], [title], [aria-label], input, code'
                        )) {
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

        # أولا: انتظر ظهور رابط الخدمة في صفحة الإنشاء/النتيجة.
        for attempt in range(48):
            found = await scan_current_page()
            if found:
                log.info(f"✅ Cloud Run URL found: {found}")
                return found

            # إذا ظهر خطأ إنشاء واضح، لا ننتظر بلا فائدة.
            try:
                body = (await page.locator("body").inner_text(timeout=3000)).lower()
                failure_terms = (
                    "failed to create", "creation failed",
                    "could not create", "error creating service",
                    "deployment failed"
                )
                if any(term in body for term in failure_terms):
                    raise RuntimeError(
                        "Google Cloud Run عرض رسالة فشل أثناء إنشاء الخدمة. "
                        "راجع صفحة Cloud Run وسجل الأخطاء."
                    )
            except RuntimeError:
                raise
            except Exception:
                pass

            await page.wait_for_timeout(2500)

        # ثانيا: افتح قائمة خدمات Cloud Run لنفس المشروع؛
        # أحيانا تنجح العملية لكن صفحة الإنشاء لا تعرض الرابط مباشرة.
        project_id = project_id
        if project_id:
            services_url = (
                "https://console.cloud.google.com/run?"
                f"project={project_id}&authuser={authuser}"
            )
            try:
                await page.goto(
                    services_url, wait_until="domcontentloaded", timeout=60000
                )
                for _ in range(36):
                    found = await scan_current_page()
                    if found:
                        log.info(f"✅ Cloud Run URL found in services list: {found}")
                        return found

                    # افتح رابط تفاصيل الخدمة إن وجد.
                    detail_href = await page.evaluate("""
                        () => {
                            const links = [...document.querySelectorAll('a[href]')];
                            const a = links.find(x =>
                                /\\/run\\/detail\\//.test(x.getAttribute('href') || '')
                            );
                            return a ? a.href : null;
                        }
                    """)
                    if detail_href:
                        try:
                            await page.goto(
                                detail_href,
                                wait_until="domcontentloaded",
                                timeout=45000
                            )
                            found = await scan_current_page()
                            if found:
                                log.info(f"✅ Cloud Run URL found in service details: {found}")
                                return found
                            await page.go_back(
                                wait_until="domcontentloaded", timeout=30000
                            )
                        except Exception:
                            pass

                    await page.wait_for_timeout(2500)
            except Exception as exc:
                log.warning(f"تعذر فحص قائمة Cloud Run: {exc}")

        raise RuntimeError(
            "لم يظهر رابط run.app بعد انتظار اكتمال النشر وفحص صفحة الخدمات. "
            "تأكد أن إنشاء الخدمة اكتمل بنجاح وأن صورة الحاوية تعمل."
        )

