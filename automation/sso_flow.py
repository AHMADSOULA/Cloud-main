"""
automation/sso_flow.py
تنسيق العملية — سريع + تصوير كل مرحلة + صفحة واحدة
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


async def run_sso_flow(context, sso_url: str, image: str, sender=None, user_tag="@user") -> dict:
    project_id = extract_project_id(sso_url)
    if not project_id:
        raise RuntimeError("❌ Project ID ماكانش في الرابط.")

    log.info(f"🚀 SSO flow — project={project_id}")

    console = CloudConsole(context, sender=sender, user_tag=user_tag)

    # صفحة واحدة مشتركة بين كل المراحل — مثل GC.py
    page = await context.new_page()
    final_url = None
    authuser = "1"

    try:
        # ══════════════════════════════════════
        # المرحلة 1: SSO + TOS + Terms Dialog
        # ══════════════════════════════════════
        try:
            await page.goto(sso_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            raise RuntimeError(f"فشل فتح رابط SSO: {e}")

        await console._shot(page, "0️⃣ رابط SSO")

        await console.step1_welcome_screen(page)
        await console.step2_terms_dialog(page)

        # انتظار ذكي قصير للـ dashboard بدل 60s + 2s
        try:
            await page.wait_for_url("**/home/dashboard**", timeout=20000)
        except Exception:
            pass
        
        # انتظار إضافي بسيط لاستقرار الجلسة (مثل GC.py)
        await page.wait_for_timeout(2000)

        authuser = extract_authuser(page.url)
        log.info(f"🔑 authuser = {authuser}")
        await console._shot(page, "✅ TOS / Dialog انتهت")

        # ══════════════════════════════════════
        # المرحلة 2: Enable API
        # ══════════════════════════════════════
        await console.step3_enable_api(page, project_id, authuser)
        await console._shot(page, "✅ API مفعل")

        # ══════════════════════════════════════
        # المرحلة 3: Create Cloud Run + URL
        # ══════════════════════════════════════
        await console.step4_create_cloud_run(page, project_id, authuser, image)
        await console._shot(page, "⏳ Cloud Run يُنشأ…")

        final_url = await console.step5_get_deployed_url(page, project_id, authuser)
        await console._shot(page, "🎉 الخدمة جاهزة")

    except Exception as e:
        # صورة عند الفشل (بأفضل مجهود) — مثل دالة handle_error في GC.py
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

    domain = extract_domain_from_service_url(final_url)

    return {
        "project_id": project_id,
        "authuser": authuser,
        "final_url": final_url,
        "domain": domain,
    }
