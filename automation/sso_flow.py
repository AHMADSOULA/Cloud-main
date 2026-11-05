"""
automation/sso_flow.py
تنسيق العملية — يدعم تسجيل دخول Google التلقائي (Next + سؤال كلمة السر)
"""
import re
from urllib.parse import urlparse, parse_qs

from automation.console import CloudConsole
from utils.logger import get_logger

log = get_logger("SSOFlow")


def extract_project_id(url: str) -> str:
    m = re.search(r'(qwiklabs-gcp-[\w-]+)', url or "")
    return m.group(1) if m else None


def extract_domain_from_service_url(service_url: str) -> str:
    s = (service_url or "").strip()
    if s.startswith("http://") or s.startswith("https://"):
        return urlparse(s).netloc.strip()
    return s.replace("http://", "").replace("https://", "").split("/")[0].strip()


def extract_authuser(page_url: str) -> str:
    try:
        qs = parse_qs(urlparse(page_url).query)
        return qs.get('authuser', ['1'])[0]
    except Exception:
        return '1'


async def _reach_dashboard(console, page, max_attempts=8):
    """
    حلقة ذكية: تتعامل مع أي مزيج من:
      - صفحة تسجيل دخول (إيميل → تالي → كلمة سر)
      - TOS
      - Terms Dialog
    حتى الوصول إلى /home/dashboard.
    """
    for attempt in range(max_attempts):
        try:
            cur = (page.url or "").lower()
        except Exception:
            cur = ""

        if "/home/dashboard" in cur:
            return True

        # 1) تسجيل دخول
        try:
            if await console.handle_google_signin(page):
                await page.wait_for_timeout(2000)
                continue
        except Exception as e:
            log.warning(f"signin step: {e}")

        # 2) TOS
        try:
            await console.step1_welcome_screen(page)
        except Exception as e:
            log.debug(f"step1: {e}")

        # 3) Terms dialog
        try:
            await console.step2_terms_dialog(page)
        except Exception as e:
            log.debug(f"step2: {e}")

        # 4) انتظار قصير لتحديث الحالة
        await page.wait_for_timeout(2000)

    try:
        return "/home/dashboard" in (page.url or "").lower()
    except Exception:
        return False


async def run_sso_flow(
    context,
    sso_url: str,
    image: str,
    sender=None,
    user_tag="@user",
    password_requester=None,
    chat_id=None,
    user_id=None,
) -> dict:
    project_id = extract_project_id(sso_url)
    if not project_id:
        raise RuntimeError("❌ Project ID ماكانش في الرابط.")

    log.info(f"🚀 SSO flow — project={project_id}")

    console = CloudConsole(
        context,
        sender=sender,
        user_tag=user_tag,
        password_requester=password_requester,
        chat_id=chat_id,
        user_id=user_id,
    )

    page = await context.new_page()
    final_url = None
    authuser = "1"

    try:
        # فتح رابط SSO
        try:
            await page.goto(sso_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            raise RuntimeError(f"فشل فتح رابط SSO: {e}")

        await console._shot(page, "0️⃣ فتح رابط SSO")

        # حلقة الوصول للوحة التحكم
        ok = await _reach_dashboard(console, page)
        if not ok:
            log.warning("لم نصل إلى لوحة التحكم بعد كل المحاولات.")
        else:
            log.info("✅ وصلنا إلى /home/dashboard")

        try:
            await page.wait_for_url("**/home/dashboard**", timeout=15000)
        except Exception:
            pass

        await page.wait_for_timeout(1500)
        authuser = extract_authuser(page.url)
        log.info(f"🔑 authuser = {authuser}")
        await console._shot(page, "✅ لوحة التحكم")

        # Enable API
        await console.step3_enable_api(page, project_id, authuser)
        await console._shot(page, "✅ API مفعل")

        # Create Cloud Run + URL
        await console.step4_create_cloud_run(page, project_id, authuser, image)
        await console._shot(page, "⏳ Cloud Run يُنشأ…")

        final_url = await console.step5_get_deployed_url(page, project_id, authuser)
        await console._shot(page, "🎉 الخدمة جاهزة")

    except Exception as e:
        try:
            await console._shot(page, f"❌ فشل: {str(e)[:60]}")
        except Exception:
            pass
        raise
    finally:
        try:
            await page.close()
        except Exception:
            pass

    if not final_url:
        raise RuntimeError("لم يتم استخراج URL بعد النشر.")

    return {
        "project_id": project_id,
        "authuser": authuser,
        "final_url": final_url,
        "domain": extract_domain_from_service_url(final_url),
    }
