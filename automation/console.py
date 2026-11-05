class CloudConsole:
    def __init__(self, context, sender=None, user_tag=None,
                 password_requester=None, chat_id=None, user_id=None):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"
        self.password_requester = password_requester  # async fn(chat_id, user_id) -> str|None
        self.chat_id = chat_id
        self.user_id = user_id
        self._last_url = ""
        self._shot_count = 0

    # ═══════════════════════════════════════
    # كشف صفحة Google Sign-in (إيميل → التالي → كلمة سر)
    # ═══════════════════════════════════════
    async def handle_google_signin(self, page):
        """
        إذا كنا في صفحة تسجيل دخول Google:
        - إن كان الإيميل مُعبّأ → اضغط "التالي".
        - انتظر صفحة كلمة السر → اطلبها من المستخدم عبر تيليجرام → املأها → اضغط "التالي".
        ترجع True إذا تعاملت مع الصفحة (سواءً نجحت أو لا)، False إذا لم تكن صفحة تسجيل دخول.
        """
        try:
            url = (page.url or "").lower()
        except Exception:
            return False

        is_signin = (
            "accounts.google.com" in url
            or "/v3/signin" in url
            or "/signin" in url
            or "serviceLogin" in url
        )
        if not is_signin:
            return False

        log.info("🔐 صفحة تسجيل دخول Google مكتشفة")
        await self._shot(page, "🔐 صفحة تسجيل الدخول")

        # ─── انتظار حقل الإيميل ───
        try:
            await page.wait_for_selector(
                'input[type="email"], input[name="identifier"]',
                timeout=6000,
            )
        except Exception:
            log.warning("لم يظهر حقل الإيميل")
            return True

        email_val = await page.evaluate("""
            () => {
                const el = document.querySelector('input[type="email"], input[name="identifier"]');
                return el ? (el.value || '').trim() : '';
            }
        """)
        log.info(f"📧 الإيميل المُعبّأ: {email_val or '(فارغ)'}")

        if not email_val:
            log.warning("الإيميل غير مُعبّأ — لن نضغط التالي، المستخدم يحتاج لتعبئته يدوياً.")
            await self._shot(page, "⚠️ إيميل فارغ — توقف")
            return True

        # ─── الضغط على "التالي / Next" ───
        clicked = await page.evaluate("""
            () => {
                const kws = ['next', 'التالي', 'تالٍ'];
                const candidates = document.querySelectorAll(
                    'button, [role="button"], div[role="button"], #identifierNext'
                );
                for (const el of candidates) {
                    if (el.offsetParent === null || el.disabled) continue;
                    const t = (el.innerText || el.getAttribute('aria-label') || '').trim().toLowerCase();
                    for (const kw of kws) {
                        if (t === kw || t.includes(kw)) {
                            try { el.click(); return 'kw'; } catch(e){}
                        }
                    }
                }
                const idn = document.querySelector('#identifierNext');
                if (idn) { try { idn.click(); return 'id'; } catch(e){} }
                return null;
            }
        """)
        log.info(f"➡️ ضغط التالي: {clicked}")
        await page.wait_for_timeout(1200)
        await self._shot(page, "🔐 بعد ضغط التالي")

        # ─── انتظار صفحة كلمة السر ───
        try:
            await page.wait_for_selector('input[type="password"]', timeout=20000)
        except Exception:
            log.warning("لم تظهر صفحة كلمة السر (ربما الجلسة مسجلة مسبقاً).")
            return True

        await self._shot(page, "🔐 صفحة كلمة السر")

        # ─── طلب كلمة السر من المستخدم ───
        if not self.password_requester or not self.chat_id or not self.user_id:
            log.warning("لا يوجد password_requester — لا يمكن طلب كلمة السر.")
            return True

        password = await self.password_requester(self.chat_id, self.user_id)
        if not password:
            log.warning("لم تُستلم كلمة السر.")
            return True

        # ─── إدخال كلمة السر ───
        try:
            await page.fill('input[type="password"]', password)
            await page.wait_for_timeout(400)
            await self._shot(page, "🔐 تم إدخال كلمة السر")

            clicked_next = await page.evaluate("""
                () => {
                    const idn = document.querySelector('#passwordNext');
                    if (idn) { try { idn.click(); return 'id'; } catch(e){} }
                    const kws = ['next', 'التالي'];
                    for (const el of document.querySelectorAll('button, [role="button"]')) {
                        if (el.offsetParent === null || el.disabled) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t.includes(kw)) { try { el.click(); return 'kw'; } catch(e){} }
                        }
                    }
                    return null;
                }
            """)
            log.info(f"➡️ تأكيد كلمة السر: {clicked_next}")
            await page.wait_for_timeout(3000)
            await self._shot(page, "✅ بعد إدخال كلمة السر")

            # قد يظهر تحذير أمان أو صفحة إضافية — نمنحها وقت
            await page.wait_for_timeout(1500)
        except Exception as e:
            log.warning(f"خطأ في تعبئة كلمة السر: {e}")

        return True
