"""Custom Flask CLI commands: init-db and seed."""
from __future__ import annotations

import os

import click
from flask import Flask, current_app

from app.extensions import db
from app.models.ai import AISettings, PromptVersion
from app.models.core import Channel, User
from app.models.enums import ChannelStatus, ChannelType, UserRole
from app.models.org import OrgSettings
from app.models.support import CannedResponse, Tag

DEFAULT_PROMPT = (
    "أنت مساعد ذكي لخدمة توصيل الطلبات والمشاوير للمنازل. العميل بيطلب منك تجيبله "
    "حاجات من محلات (صيدلية، مطعم، سوبر ماركت، أي محل) وتوصّلها له. ردّ باللهجة "
    "المصرية بأسلوب ودود وواضح ومختصر.\n"
    "شغلتك إنك تفهم الطلب وتجمع تفاصيله وتأكّده، والمندوب هو اللي ينفّذ ويشتري — "
    "فإنت مش محتاج تعرف الأسعار بالظبط، ولا تصعّد لمجرد إنك مش متأكد من السعر.\n"
    "اجمع من العميل في أقل عدد رسائل: إيه المطلوب ومن أي محل/محلات (كل محل وأصنافه)، "
    "مكان التسليم وعلامة مميزة قريبة منه، رقم تليفون، وطريقة الدفع (كاش/محفظة)، "
    "ومحتاج فاتورة ولا لأ. لو العميل عنده عنوان محفوظ اعرضه واسأله \"نفس العنوان؟\".\n"
    "لما تجمع التفاصيل اعرض ملخّص قصير للطلب واسأله \"تمام كده؟\". ولما يوافق "
    "(زي \"تمام\" أو \"أكّد\" أو \"ماشي\") اعتبره تأكيد أوردر (order_confirmed) واكتب "
    "رسالة تأكيد ودّية — وده مش تصعيد خالص.\n"
    "صعّد لموظف فقط لو: العميل طلب صراحةً يتكلم مع موظف، أو كان غاضب أو بيشتكي شكوى "
    "حقيقية، أو موضوع حساس فعلًا (شكوى رسمية أو مسألة قانونية). لو مش فاهم الطلب أو "
    "ناقصة معلومة أو مش متأكد، اسأل العميل يوضّح أو اجمع تفاصيل أكتر — متصعّدش لمجرد "
    "عدم التأكد. الكلام العادي عن الطلب أو ذكر الدفع/الكاش مش سبب للتصعيد.\n"
    "كن واثقًا في دورك كمساعد طلبات. متخترعش أسعار أو سياسات مش موجودة في قاعدة المعرفة."
)


def register_cli(app: Flask) -> None:
    app.cli.add_command(init_db)
    app.cli.add_command(seed)
    app.cli.add_command(maintenance)


@click.command("init-db")
def init_db():
    """Create all tables directly (quick start without migrations)."""
    db.create_all()
    click.echo("✓ tables created")


@click.command("seed")
def seed():
    """Create the first admin, AI settings, and sample reference data."""
    created = []

    # Org settings singleton (automation, hours, retention).
    if db.session.get(OrgSettings, 1) is None:
        db.session.add(OrgSettings(id=1))
        created.append("org_settings")

    # AI settings singleton + default prompt version.
    settings = db.session.get(AISettings, 1)
    if settings is None:
        prompt = PromptVersion(version=1, system_prompt=DEFAULT_PROMPT, tone="ودود ومحترف")
        db.session.add(prompt)
        db.session.flush()
        settings = AISettings(
            id=1,
            ai_enabled=True,
            active_prompt_version_id=prompt.id,
            provider=os.environ.get("AI_PROVIDER", "deepseek"),
            model=os.environ.get("AI_MODEL", "deepseek-chat"),
            base_url=os.environ.get("AI_BASE_URL", "https://api.deepseek.com"),
        )
        # Seed the API key from env if provided (editable later via Settings).
        env_key = os.environ.get("DEEPSEEK_API_KEY")
        if env_key:
            settings.set_api_key(env_key)
        db.session.add(settings)
        created.append("ai_settings + prompt")

    # First admin.
    email = current_app.config["ADMIN_EMAIL"].strip().lower()
    admin = db.session.scalar(db.select(User).filter_by(email=email))
    if admin is None:
        admin = User(
            name=current_app.config["ADMIN_NAME"],
            email=email,
            role=UserRole.ADMIN,
        )
        admin.set_password(current_app.config["ADMIN_PASSWORD"])
        db.session.add(admin)
        created.append(f"admin ({email})")

    # Sample tags.
    for name, color in [("عميل متكرر", "#0e8f82"), ("استرجاع", "#bd6f06"),
                        ("طلب متأخر", "#d23f3f")]:
        if not db.session.scalar(db.select(Tag).filter_by(name=name)):
            db.session.add(Tag(name=name, color=color))
            created.append(f"tag:{name}")

    # Sample canned responses.
    for shortcut, body in [
        ("ترحيب", "أهلاً بحضرتك في خدمة التوصيل 👋 كيف أقدر أساعدك؟"),
        ("توصيل", "طلب حضرتك خرج للتوصيل وهيوصلك خلال ٤٥ دقيقة تقريبًا 🚗"),
        ("اعتذار", "آسفين جدًا على الإزعاج 🙏 وهنعوّض حضرتك فورًا."),
    ]:
        if not db.session.scalar(db.select(CannedResponse).filter_by(shortcut=shortcut)):
            db.session.add(CannedResponse(shortcut=shortcut, body=body))
            created.append(f"canned:{shortcut}")

    # Sample Telegram channel (not yet connected).
    if not db.session.scalar(db.select(Channel).filter_by(type=ChannelType.TELEGRAM)):
        db.session.add(Channel(
            type=ChannelType.TELEGRAM, name="تيليجرام الرئيسي",
            status=ChannelStatus.DISCONNECTED,
        ))
        created.append("channel:telegram")

    db.session.commit()
    if created:
        click.echo("✓ seeded: " + ", ".join(created))
    else:
        click.echo("• nothing to seed (already present)")


@click.command("maintenance")
def maintenance():
    """Run periodic automation: SLA alerts + idle auto-close (run via cron)."""
    from app.services import automation

    alerts = automation.run_sla_check()
    closed = automation.run_auto_close()
    purged = automation.run_retention()
    click.echo(
        f"✓ maintenance: {alerts} SLA alert(s), {closed} auto-closed, "
        f"{purged} conversation(s) purged by retention"
    )
