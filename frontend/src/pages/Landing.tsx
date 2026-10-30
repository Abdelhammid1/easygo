import { useEffect } from "react";

const PHONE_DISPLAY = "01069982183";
const TEL = "tel:+201069982183";
const TELEGRAM = "https://t.me/easygo_quweisna_bot";
const INSTAGRAM = "https://www.instagram.com/easygo1_/";
const FACEBOOK = "https://www.facebook.com/EasyGoDeliveryService";
const CREDIT_URL =
  "https://manasety.ai/?utm_source=easygo&utm_medium=footer&utm_campaign=powered_by";

const WHAT = [
  { icon: "🍔", title: "أكل ومشروبات", text: "من مطعم، كافيه، أو حتى من ست البيت اللي بتعمل أحلى محشي." },
  { icon: "💊", title: "أدوية وصيدلية", text: "قول اسم الدوا والصيدلية، والمندوب يجيبه لحد عندك." },
  { icon: "📄", title: "مستندات وأوراق", text: "ملفات، عقود، أوراق حكومية، أي حاجة لازم توصل بإيد أمينة." },
  { icon: "🛍️", title: "طلبات من المحلات", text: "اشتريت من محل ومش فاضي تروح؟ هنروح بدالك." },
  { icon: "📦", title: "طرود وهدايا", text: "هدية لحد عزيز في بلد تانية قريبة؟ إحنا نوصلها." },
  { icon: "✨", title: "أي حاجة تانية", text: "لو ينفع تتشال وتتوصل.. يبقى إحنا بنوصلها." },
];

const STEPS = [
  { n: "1", title: "كلمنا", text: "اتصل بينا أو ابعتلنا على تليجرام، وقولنا عايز إيه ومن فين ولفين." },
  { n: "2", title: "المندوب يتحرك", text: "بنستلم الطلب من المكان اللي تحدده ونتابعه معاك." },
  { n: "3", title: "يوصلك لحد الباب", text: "بتستلم طلبك وإنت مرتاح، وإحنا بنحاسب على التوصيل بس." },
];

const WHY = [
  { icon: "🧭", title: "بنعرف بلدنا", text: "عارفين شوارع قويسنا وقراها وكل الطرق المختصرة." },
  { icon: "🎯", title: "توصيل أي حاجة", text: "مش مرتبطين بمطعم أو محل معين. إنت اللي بتختار." },
  { icon: "📞", title: "سهل زي مكالمة", text: "مكالمة واحدة أو رسالة، ومحدش هيعقّدها عليك." },
  { icon: "🪙", title: "بنحاسب على التوصيل بس", text: "مش بنزوّد على أسعار المحلات." },
];

const AREAS = ["قويسنا", "كل قرى قويسنا", "بنها", "شبين الكوم"];

const FAQ = [
  {
    q: "بتوصّلوا لفين؟",
    a: "قويسنا وكل قراها، وكمان بنها وشبين الكوم. لو مكانك برا الأماكن دي كلمنا واحنا نقولك.",
  },
  {
    q: "أطلب إزاي؟",
    a: "اتصل بينا على 01069982183 أو ابعتلنا على تليجرام، وقولنا إنت عايز إيه ومن فين ولفين، وإحنا نكمل معاك.",
  },
  {
    q: "هدفع كام؟",
    a: "إحنا بنحاسب على التوصيل بس. كلمنا وهنعرّفك بالتفاصيل.",
  },
  {
    q: "ينفع توصّلوا من أي محل أو مطعم؟",
    a: "أيوه. إنت اللي بتحدد المكان، والمندوب هيستلم لك الطلب منه ويوصله.",
  },
  {
    q: "أنا شركة أو محل، ينفع نتعاقد معاكم؟",
    a: "طبعًا. اتصل بينا ونظبط لكم طريقة تناسب شغلكم.",
  },
];

function Phone() {
  return <bdi dir="ltr">{PHONE_DISPLAY}</bdi>;
}

export function Landing() {
  useEffect(() => {
    const prev = document.title;
    document.title = "إيزي جو — بنوصّل أي حاجة لحد بابك | قويسنا";
    return () => {
      document.title = prev;
    };
  }, []);

  return (
    <div className="lp" dir="rtl">
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-in">
          <a href="/" className="lp-brand" aria-label="إيزي جو">
            <img src="/easygo-logo.png" alt="إيزي جو" width={150} height={42} />
          </a>
          <nav className="lp-links" aria-label="الأقسام">
            <a href="#what">بنوصّل إيه</a>
            <a href="#how">إزاي بنشتغل</a>
            <a href="#who">أفراد وشركات</a>
            <a href="#area">التغطية</a>
            <a href="#faq">أسئلة</a>
          </nav>
          <div className="lp-nav-cta">
            <a className="lp-btn lp-btn-yellow lp-btn-sm" href={TEL}>
              📞 اتصل دلوقتي
            </a>
            <a className="lp-login" href="/login">دخول</a>
          </div>
        </div>
      </header>

      <main>
        <section className="lp-hero">
          <div className="lp-wrap lp-hero-in">
            <div className="lp-hero-text">
              <span className="lp-pill">🛵 توصيل في قويسنا والمدن المجاورة</span>
              <h1>
                أي حاجة.. من أي مكان..
                <br />
                <span className="lp-hl">لحد بابك</span>
              </h1>
              <p>
                قول لنا عايز إيه وإحنا نجيبه. أكل، دوا، أوراق، هدية.. إحنا موجودين وعارفين الطريق.
              </p>
              <div className="lp-hero-btns">
                <a className="lp-btn lp-btn-yellow" href={TEL}>
                  📞 اتصل واطلب · <Phone />
                </a>
                <a className="lp-btn lp-btn-ghost" href={TELEGRAM} target="_blank" rel="noopener noreferrer">
                  ابعتلنا على تليجرام
                </a>
              </div>
            </div>
            <div className="lp-hero-art" aria-hidden="true">
              <div className="lp-bubble lp-b1">🍔 أكل</div>
              <div className="lp-bubble lp-b2">💊 دوا</div>
              <div className="lp-bubble lp-b3">📄 أوراق</div>
              <div className="lp-bubble lp-b4">🎁 هدية</div>
              <div className="lp-road">
                <span className="lp-arrow">➜</span>
              </div>
              <div className="lp-door">🏠</div>
            </div>
          </div>
        </section>

        <section id="what" className="lp-sec">
          <div className="lp-wrap">
            <h2>بنوصّل إيه؟</h2>
            <p className="lp-sub">الإجابة المختصرة: أي حاجة.</p>
            <div className="lp-grid lp-grid-3">
              {WHAT.map((x) => (
                <div className="lp-card" key={x.title}>
                  <div className="lp-ico">{x.icon}</div>
                  <h3>{x.title}</h3>
                  <p>{x.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className="lp-sec lp-sec-purple">
          <div className="lp-wrap">
            <h2>إزاي بنشتغل؟</h2>
            <p className="lp-sub">تلات خطوات وطلبك عندك.</p>
            <div className="lp-grid lp-grid-3">
              {STEPS.map((s) => (
                <div className="lp-step" key={s.n}>
                  <div className="lp-num">{s.n}</div>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="who" className="lp-sec">
          <div className="lp-wrap">
            <h2>لكل الناس</h2>
            <p className="lp-sub">سواء إنت فرد أو شركة، عندنا ليك مكان.</p>
            <div className="lp-grid lp-grid-2">
              <div className="lp-card lp-card-big">
                <div className="lp-ico">🙋</div>
                <h3>للأفراد</h3>
                <p>محتاج حاجة دلوقتي ومش قادر تتحرك؟ مكالمة واحدة وإحنا نتصرف.</p>
                <a className="lp-btn lp-btn-purple" href={TEL}>اطلب كفرد</a>
              </div>
              <div className="lp-card lp-card-big">
                <div className="lp-ico">🏪</div>
                <h3>للشركات والمحلات</h3>
                <p>عندك طلبات بتتوصّل كل يوم؟ سيب التوصيل علينا وركّز في شغلك.</p>
                <a className="lp-btn lp-btn-purple" href={TEL}>كلمنا كشركة</a>
              </div>
            </div>
          </div>
        </section>

        <section className="lp-sec lp-sec-soft">
          <div className="lp-wrap">
            <h2>ليه إيزي جو؟</h2>
            <div className="lp-grid lp-grid-4">
              {WHY.map((x) => (
                <div className="lp-card" key={x.title}>
                  <div className="lp-ico">{x.icon}</div>
                  <h3>{x.title}</h3>
                  <p>{x.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="area" className="lp-sec">
          <div className="lp-wrap lp-center">
            <h2>بنغطّي فين؟</h2>
            <p className="lp-sub">من قويسنا لحد المدن اللي حواليها.</p>
            <div className="lp-chips">
              {AREAS.map((a) => (
                <span className="lp-chip" key={a}>📍 {a}</span>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="lp-sec lp-sec-soft">
          <div className="lp-wrap lp-narrow">
            <h2>أسئلة بتتسأل كتير</h2>
            <div className="lp-faq">
              {FAQ.map((f) => (
                <details key={f.q}>
                  <summary>{f.q}</summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="lp-cta">
          <div className="lp-wrap lp-center">
            <h2>جاهز؟ كلمنا بس</h2>
            <p>إحنا مستنيين مكالمتك.</p>
            <a className="lp-btn lp-btn-yellow lp-btn-lg" href={TEL}>
              📞 اتصل دلوقتي · <Phone />
            </a>
            <div className="lp-social" aria-label="تابعنا">
              <a href={TELEGRAM} target="_blank" rel="noopener noreferrer">تليجرام</a>
              <a href={INSTAGRAM} target="_blank" rel="noopener noreferrer">إنستجرام</a>
              <a href={FACEBOOK} target="_blank" rel="noopener noreferrer">فيسبوك</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-foot">
        <div className="lp-wrap lp-foot-in">
          <img src="/easygo-logo.png" alt="إيزي جو" width={120} height={33} />
          <span>© {new Date().getFullYear()} إيزي جو — جميع الحقوق محفوظة</span>
          <span>
            تطوير{" "}
            <a href={CREDIT_URL} target="_blank" rel="noopener noreferrer">منصتي</a>
          </span>
        </div>
      </footer>

      <a className="lp-call-float" href={TEL} aria-label="اتصل بإيزي جو">
        📞
      </a>
    </div>
  );
}
