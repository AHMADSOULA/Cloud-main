"""
automation/console.py
كل خطوات Google Cloud Console — بنفس منطق GC.py
+ تصوير في كل خطوة عبر sender
"""
import asyncio
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("Console")


class CloudConsole:
    def __init__(self, sender=None):
        self.sender = sender  # async def sender(img_bytes, caption)

    async def _shot(self, page, caption):
        if not self.sender:
            return
        try:
            img = await page.screenshot(type="jpeg", quality=65, full_page=False)
            await self.sender(img, caption)
        except Exception as e:
            log.debug(f"screenshot: {e}")

    # ═══════════════════════════════════════
    # STEP 1: TOS الأولى — نفس GC.py
    # ═══════════════════════════════════════
    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: Welcome / TOS")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)
        await self._shot(page, "1️⃣ بداية الصفحة")

        await page.keyboard.press("Enter")

        try:
            button = page.locator("text='I understand'")
            if await button.is_visible(timeout=3000):
                await button.click()
                log.info("✅ ضغط 'I understand'")
        except Exception:
            pass

        await page.wait_for_load_state("networkidle")
        await self._shot(page, "1️⃣ TOS انتهت")

    # ═══════════════════════════════════════
    # STEP 2: TOS + Country — نفس GC.py
    # ═══════════════════════════════════════
    async def step2_tos_and_country(self, page):
        log.info("🚀 step2: TOS + Country")
        await self._shot(page, "2️⃣ قبل TOS Country")

        agree_btn = page.get_by_role("button", name="Agree and continue")

        try:
            await agree_btn.wait_for(state="visible", timeout=10000)

            checkboxes = page.get_by_role("checkbox")
            await checkboxes.nth(0).click()
            await asyncio.sleep(1)
            await checkboxes.nth(1).click()

            await agree_btn.click()
            await page.wait_for_load_state("domcontentloaded")
            log.info("✅ TOS Country تمت")

        except Exception:
            log.info("ℹ️ رسالة الشروط لم تظهر، تم التخطي.")

        await self._shot(page, "2️⃣ TOS Country انتهت")

    # ═══════════════════════════════════════
    # STEP 3: Enable API — نفس GC.py
    # ═══════════════════════════════════════
    async def step3_enable_api(self, page, project_id, authuser):
        log.info("🚀 step3: Enable API")
        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        await page.goto(api_url, wait_until="domcontentloaded")
        await self._shot(page, "3️⃣ صفحة API")

        # فحص صفحة تسجيل الدخول
        if "signin" in page.url.lower() or "accounts.google.com" in page.url:
            raise Exception(
                "توقفنا في صفحة تسجيل دخول Google! الرابط منتهي أو الجلسة لم تكتمل."
            )

        enable_btn = page.get_by_role("button", name="Enable")
        manage_btn = page.get_by_role("button", name="Manage")
        disable_btn = page.get_by_text("Disable API")

        try:
            await expect(enable_btn.or_(manage_btn)).to_be_visible(timeout=15000)

            if await enable_btn.is_visible():
                await enable_btn.click()
                await self._shot(page, "3️⃣ Enable مضغوط")
                await expect(manage_btn.or_(disable_btn)).to_be_visible(timeout=60000)
            elif await manage_btn.is_visible():
                log.info("ℹ️ API مفعل مسبقاً")

        except Exception as e:
            await self._shot(page, "3️⃣ فشل تفعيل API")
            raise Exception(f"عطل في إيجاد زر تفعيل الـ API: {str(e)}")

        await self._shot(page, "3️⃣ API مفعل")

    # ═══════════════════════════════════════
    # STEP 4: Create Cloud Run — نفس GC.py
    # ═══════════════════════════════════════
    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        log.info("🚀 step4: Create Cloud Run")
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        await page.goto(run_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await self._shot(page, "4️⃣ صفحة الإنشاء")

        try:
            label = page.get_by_text("Container Image URL").first
            await label.click()
            await page.wait_for_timeout(500)
            await page.keyboard.type(image, delay=50)
            log.info("✅ تم إدخال الصورة")
        except Exception as e:
            raise Exception(f"فشل في الضغط وكتابة الرابط: {str(e)}")

        await page.wait_for_timeout(3000)
        await self._shot(page, "4️⃣ الصورة مكتوبة")

        try:
            await page.get_by_role("radio", name="Allow public access").click()
            await page.get_by_role("radio", name="Instance-based").click()

            try:
                await page.get_by_role("button", name="Hide").click(timeout=2000)
            except Exception:
                pass

            await page.keyboard.press("End")
            await page.wait_for_timeout(1000)

            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True)
            log.info("✅ Create مضغوط")

        except Exception as e:
            raise Exception(f"فشل في اختيار الإعدادات أو ضغط Create: {str(e)}")

        await self._shot(page, "4️⃣ Create انضغط")

    # ═══════════════════════════════════════
    # STEP 5: Get URL — نفس GC.py
    # ═══════════════════════════════════════
    async def step5_get_deployed_url(self, page):
        log.info("🚀 step5: انتظار الرابط")
        await self._shot(page, "5️⃣ انتظار ظهور الرابط")

        link_locator = page.locator('a[href*="run.app"]')
        await link_locator.wait_for(state="visible", timeout=120000)

        final_url = await link_locator.get_attribute("href")
        log.info(f"✅ URL: {final_url}")

        await self._shot(page, "5️⃣ الرابط ظهر")
        return final_url
