# easyGo — منصة المحادثات الموحدة مع الذكاء الاصطناعي

منصة ويب لخدمة **توصيل الطلبات للمنازل** تجمع محادثات العملاء من قنوات متعددة
(Telegram، ثم Messenger و Instagram) في صندوق وارد واحد، مع طبقة ذكاء اصطناعي
ترد تلقائيًا وتصعّد للموظف عند الحاجة.

> **الحالة:** الواجهة الخلفية مكتملة تقريبًا (المراحل 0–3)، والواجهة الأمامية
> (React + TypeScript، عربي RTL) تغطّي الشاشات الأساسية كلها: تسجيل الدخول،
> **الصندوق الموحد الحيّ** (Socket.IO)، **جهات الاتصال** (تعديل/حظر/دمج)،
> **قاعدة المعرفة** (إضافة/تعديل/رفع ملفات + Playground)، **التقارير** (+CSV)،
> **المستخدمون والأدوار**، **الإعدادات** (مزوّد الذكاء الاصطناعي + القنوات)،
> و**مركز الإشعارات** الحيّ، بالإضافة إلى **إعدادات المؤسسة** (الترحيب/ساعات العمل/
> التوزيع التلقائي/SLA/الاحتفاظ) و**المفتاح العام للذكاء الاصطناعي** في الشريط العلوي
> (متاح للمدير والمشرف). التبويبات تُعرَض حسب صلاحية الدور.

## المعمارية (Modular Monolith)

| الخدمة | الدور |
|---|---|
| `web` | تطبيق Flask (API + مصادقة + Realtime عبر Socket.IO) خلف gunicorn |
| `worker` | معالج RQ للرسائل الواردة وطلبات الذكاء الاصطناعي (فصل الاستقبال عن المعالجة) |
| `db` | PostgreSQL 16 |
| `redis` | طابور المهام + الكاش + قناة Realtime |
| `frontend` | تطبيق React (Vite) يُبنى ويُقدَّم عبر nginx، ويمرّر `/api` و `/socket.io` إلى `web` |

البنية مبنية على المبادئ الإلزامية في الوثيقة (§4.1): تخزين كل رسالة قبل
المعالجة، منع التكرار (Idempotency) عبر `(channel_id, external_id)`، واجهة قنوات
موحدة، وتشفير أسرار القنوات (Fernet).

## التشغيل محليًا

المتطلب الوحيد: **Docker** + **Docker Compose**.

```bash
# 1) جهّز متغيرات البيئة
cp .env.example .env
# (موصى به) ولّد مفاتيح حقيقية:
#   SECRET_KEY : python -c "import secrets;print(secrets.token_urlsafe(48))"
#   FERNET_KEY : python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"

# 2) شغّل الخدمات
docker compose up --build -d

# 3) أنشئ قاعدة البيانات
#    (أ) بداية سريعة بدون هجرات:
docker compose exec web flask init-db
#    (ب) أو الطريقة الصحيحة بالهجرات (Flask-Migrate):
docker compose exec web flask db init      # أول مرة فقط
docker compose exec web flask db migrate -m "initial schema"
docker compose exec web flask db upgrade

# 4) ازرع المدير الأول والبيانات المبدئية
docker compose exec web flask seed
```

التطبيق على: **http://localhost:8080** (الواجهة + الـ API). سجّل الدخول ببيانات المدير.

### تطوير الواجهة الأمامية

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 — يمرّر الطلبات إلى الـ backend على 8080
npm run build    # بناء الإنتاج (tsc --noEmit ثم vite build)
```
الواجهة تطلب رمز CSRF من ردّ `login`/`/me` وترسله تلقائيًا؛ الجلسة بكوكي HttpOnly.

### فحص سريع

```bash
curl http://localhost:8080/api/health
# {"status":"ok","checks":{"db":true,"redis":true}}

# تسجيل الدخول (بيانات المدير من .env) — واحفظ رمز الـ CSRF
TOKEN=$(curl -s -c cookies.txt -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@easygo.local","password":"admin12345"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['csrf_token'])")

curl -b cookies.txt http://localhost:8080/api/auth/me
```

> **ملاحظة أمان (CSRF):** كل طلب يغيّر بيانات (POST/PUT/DELETE) عبر جلسة المتصفح
> يجب أن يحمل ترويسة `X-CSRF-Token: $TOKEN` (الرمز يأتي من ردّ `login` و `/me`).
> الـ Webhooks و اتصال Socket.IO مُعفاة.

## تشغيل Telegram + DeepSeek (المرحلة 1)

كل الإعدادات تُدار من الـ API (جاهزة لربطها بشاشة الإعدادات لاحقًا). الأمثلة تفترض
أنك سجّلت دخول المدير وحفظت الكوكيز في `cookies.txt`.

**1) اضبط مزوّد الذكاء الاصطناعي (DeepSeek):**
```bash
curl -b cookies.txt -X PUT http://localhost:8080/api/settings/ai \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $TOKEN" \
  -d '{"provider":"deepseek","model":"deepseek-chat","api_key":"sk-...","ai_enabled":true}'
# المفتاح يُحفظ مشفّرًا ولا يُعاد إظهاره أبدًا (has_api_key: true فقط)
```

**2) اضبط بوت Telegram (التوكن + الأوامر):**
```bash
# أنشئ القناة (أو استخدم التي زرعها seed)
curl -b cookies.txt -X POST http://localhost:8080/api/settings/channels \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $TOKEN" \
  -d '{"type":"telegram","name":"بوت التوصيل"}'

# احفظ توكن البوت (من @BotFather) وأوامره
curl -b cookies.txt -X PUT http://localhost:8080/api/settings/channels/1 \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $TOKEN" \
  -d '{"bot_token":"123456:ABC...","commands":[
        {"command":"start","description":"ابدأ المحادثة"},
        {"command":"order","description":"حالة طلبي"}]}'

# اختبر الاتصال (يرجع رابط البوت t.me/...)
curl -b cookies.txt -X POST -H "X-CSRF-Token: $TOKEN" \
  http://localhost:8080/api/settings/channels/1/test
```

**3) اربط الـ Webhook** (يتطلب `PUBLIC_BASE_URL` في `.env` — رابط HTTPS عام؛
في التطوير استخدم نفقًا مثل ngrok):
```bash
curl -b cookies.txt -X POST -H "X-CSRF-Token: $TOKEN" \
  http://localhost:8080/api/settings/channels/1/connect
# يسجّل الـ Webhook على Telegram، يدفع الأوامر، ويحوّل الحالة إلى connected
```

**4) راسل البوت على Telegram** → تظهر المحادثة ويرد الذكاء الاصطناعي تلقائيًا
(أو يصعّد). تابعها:
```bash
curl -b cookies.txt "http://localhost:8080/api/conversations"
curl -b cookies.txt "http://localhost:8080/api/conversations/1/messages"
# رد الموظف يوقف الذكاء الاصطناعي على المحادثة تلقائيًا
curl -b cookies.txt -X POST http://localhost:8080/api/conversations/1/reply \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $TOKEN" \
  -d '{"text":"أهلاً، أنا بساعدك 🙏"}'
# إعادة تفعيل الذكاء الاصطناعي بعد التصعيد
curl -b cookies.txt -X POST http://localhost:8080/api/conversations/1/ai-mode \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $TOKEN" \
  -d '{"mode":"active"}'
```

> **تنبيه:** أضفنا أعمدة جديدة لنموذج البيانات في هذه المرحلة. إن كنت أنشأت القاعدة
> سابقًا شغّل هجرة جديدة: `flask db migrate -m "phase1"` ثم `flask db upgrade`
> (أو `flask init-db` على قاعدة فارغة).

> **الوسائط (صور/صوت):** DeepSeek نصي فقط، لذا رسائل الصور والصوت تُصعَّد للموظف
> حاليًا (تُخزَّن كاملة). إضافة مزوّد تحويل صوت/رؤية لاحقًا = تطبيق نفس الواجهة فقط.

## قنوات Meta: Messenger و Instagram (المرحلة 2)

أُضيفتا كـ Adapters جديدة تطبّق نفس واجهة القنوات — **نواة النظام لم تتغير**. يفرض
الـ Adapter **نافذة الرد 24 ساعة**: عند كل رسالة من العميل يُعاد ضبط النافذة، وأي
إرسال بعد انتهائها يُرفَض ويظهر للموظف (`reply_window_open` في بيانات المحادثة).

**إعداد لمرة واحدة في Meta App Dashboard** (خارج الكود — يتطلب مراجعة Meta و
Advanced Access، انظر النقاط المفتوحة §14):
1. أضف منتج Messenger، واضبط **Callback URL** = `https://<PUBLIC_BASE_URL>/api/webhooks/meta`
   و **Verify Token** = قيمة `META_VERIFY_TOKEN`، واشترك في حقل `messages`.
2. ضع `META_APP_SECRET` و `META_VERIFY_TOKEN` في `.env` (قيم على مستوى التطبيق).

**لكل صفحة/حساب — عبر الإعدادات:**
```bash
# Messenger: أنشئ القناة وأدخل توكن الصفحة ومعرّفها
curl -b cookies.txt -X POST http://localhost:8080/api/settings/channels \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $TOKEN" \
  -d '{"type":"messenger","name":"صفحة فيسبوك"}'
curl -b cookies.txt -X PUT http://localhost:8080/api/settings/channels/2 \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $TOKEN" \
  -d '{"page_access_token":"EAAB...","page_id":"1234567890"}'
curl -b cookies.txt -X POST -H "X-CSRF-Token: $TOKEN" \
  http://localhost:8080/api/settings/channels/2/connect   # يشترك الصفحة في التطبيق

# Instagram: نفس الخطوات بالنوع instagram و ig_id (يتطلب حسابًا Professional مربوطًا بصفحة)
```

رسائل Messenger/Instagram تظهر في نفس الصندوق وتُرسَل بنفس سلوك Telegram، وتعمل
عليها نفس قواعد الذكاء الاصطناعي والتصعيد. التحقق من التوقيع (`X-Hub-Signature-256`)
مُطبّق على كل Webhook وارد من Meta.

## باقي الـ API (المرحلة 3)

كل المسارات تحت `/api` وتتطلب جلسة + ترويسة `X-CSRF-Token` على POST/PUT/DELETE.

| المجال | المسارات | الصلاحية |
|---|---|---|
| المستخدمون §5.7 | `GET/POST /users` · `PUT /users/{id}` | admin |
| جهات الاتصال §5.3 | `GET /contacts` · `GET/PUT /contacts/{id}` · `POST /contacts/{id}/block` · `.../merge` | عرض للكل، الإدارة بالدور |
| قاعدة المعرفة §7 | `GET/POST /knowledge` · `PUT/DELETE /knowledge/{id}` · `POST /knowledge/upload` · `POST /knowledge/playground` · `GET /knowledge/stale` · `GET /knowledge/suggestions` | عرض للكل، تعديل admin/supervisor |
| الوسوم والردود §5.7 | `GET/POST/DELETE /catalog/tags` · `GET/POST/PUT/DELETE /catalog/canned` | — |
| الإشعارات §5.5 | `GET /notifications` · `POST /notifications/{id}/read` · `POST /notifications/read-all` | المستخدم نفسه |
| التقارير §5.6 | `GET /reports/summary` · `GET /reports/agents` · `GET /reports/export/conversations.csv` | عرض (الموظف لنفسه) |
| سجل التدقيق §5.7 | `GET /audit` | admin/supervisor |
| الوسائط | `GET /media/attachments/{id}` (محميّة بالجلسة) | مسجّل الدخول |
| إعدادات المؤسسة §5.4 | `GET/PUT /settings/org` (ترحيب، ساعات عمل، توزيع تلقائي، SLA، إغلاق خامل، احتفاظ) | admin |

**رفع ملف لقاعدة المعرفة** (PDF/Word/Excel/CSV/نص) — يُستخرج نصه ويُجزّأ تلقائيًا:
```bash
curl -b cookies.txt -H "X-CSRF-Token: $TOKEN" \
  -F "file=@menu.pdf" -F "title=قائمة الأسعار" -F "category=الأسعار" \
  http://localhost:8080/api/knowledge/upload
```

**الأتمتة الدورية (SLA + إغلاق الخامل + الاحتفاظ)** — تُشغَّل عبر cron:
```bash
# كل 5 دقائق مثلًا:
docker compose exec web flask maintenance
# ينفّذ: تنبيهات SLA (§5.4 AU-4)، إغلاق المحادثات الخاملة (AU-5)،
#        وحذف المحادثات والوسائط الأقدم من مدة الاحتفاظ (§5.7 AD-6).
```

**الإشعارات الخارجية (§5.5):**
- **بريد إلكتروني (NT-3):** تنبيه المسؤولين عند أعطال القنوات أو فشل الذكاء الاصطناعي.
  اضبط `SMTP_*` و `MAIL_FROM` في `.env` (يُعطَّل تلقائيًا إن لم تُضبط).
- **إشعار المتصفح / Web Push (NT-2):** مكتمل من الطرفين. اضبط مفاتيح `VAPID_*` في
  `.env`، ثم في الواجهة افتح جرس الإشعارات واضغط **تفعيل** إشعارات المتصفح. يسجّل
  التطبيق عامل الخدمة `/sw.js` ويشترك عبر `POST /api/notifications/push/subscribe`،
  وتصل الدفعات مع كل إشعار داخلي (تصعيد، تعيين، SLA، أعطال) حتى والصفحة في الخلفية.
  توليد المفاتيح: `vapid --gen` أو عبر مكتبة `py_vapid`. يتطلب Web Push اتصال HTTPS
  (أو `localhost` في التطوير).

> **هجرة قاعدة البيانات:** هذه المرحلة تضيف جدولي `org_settings` و `push_subscriptions`.
> شغّل: `flask db migrate -m "phase3"` ثم `flask db upgrade` (أو `flask init-db` لقاعدة فارغة).
> و`flask seed` ينشئ صف الإعدادات الافتراضي.

## الأدوار والصلاحيات (§3)

ثلاثة أدوار: `admin` / `supervisor` / `agent`. مصفوفة الصلاحيات معرّفة في
`backend/app/security/permissions.py` وتُطبّق عبر `@require_permission(...)`.

## نموذج البيانات (§9)

كل الكيانات في `backend/app/models/` موزّعة على: `core.py` (المستخدمون،
القنوات، جهات الاتصال، المحادثات، الرسائل، المرفقات)، `support.py` (الوسوم،
الملاحظات، الردود الجاهزة، الإشعارات، سجل التدقيق)، و `ai.py` (قاعدة المعرفة،
إعدادات الذكاء الاصطناعي، إصدارات الـ Prompt، سجل تشغيل الذكاء الاصطناعي).

## بنية المجلدات

```
easygo/
├─ docker-compose.yml        # web · worker · db · redis · frontend
├─ .env.example
├─ pyrightconfig.json
├─ frontend/                 # React + Vite + TS SPA (RTL); nginx serves + proxies
│  ├─ Dockerfile · nginx.conf
│  └─ src/ (api/ · auth · socket · pages/ · components/)
└─ backend/
   ├─ Dockerfile
   ├─ requirements.txt
   ├─ wsgi.py                # gunicorn/dev entrypoint
   ├─ worker.py              # RQ worker entrypoint
   └─ app/
      ├─ __init__.py         # app factory
      ├─ config.py
      ├─ extensions.py       # db, migrate, login, bcrypt, socketio, redis
      ├─ cli.py              # init-db, seed
      ├─ security/           # crypto (Fernet) + permissions (RBAC)
      ├─ models/             # core, support, ai, enums, base
      ├─ channels/           # unified adapter + telegram + meta (messenger/instagram)
      ├─ services/           # ingestion, outgoing, escalation, knowledge, realtime,
      │                      #   automation, audit, ai/ (provider-agnostic + deepseek)
      ├─ auth/               # login / logout / me (+ CSRF token)
      ├─ api/                # health · settings · webhooks · conversations · users ·
      │                      #   contacts · knowledge · catalog · notifications ·
      │                      #   reports · media · automation(org) · audit
      ├─ realtime/           # Socket.IO events
      └─ tasks/              # RQ queue + pipeline (worker task: §6.1 flow)
```

## الخريطة القادمة

- **المرحلة 1:** محوّل Telegram → خط الاستقبال → الصندوق الموحد (Realtime) →
  خدمة الذكاء الاصطناعي (مستقلة عن المزود) + قاعدة المعرفة (Embeddings) → التقارير.
- **المرحلة 2:** محوّلات Meta (Messenger/Instagram) مع فرض نافذة الرد 24 ساعة.

التصميم المرجعي للواجهة (نموذج أولي RTL) متوفر كـ Artifact منفصل.
