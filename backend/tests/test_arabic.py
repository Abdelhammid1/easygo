"""Arabic normalization (ticket §5 acceptance)."""
from app.utils.arabic import contains_any, normalize_ar, tokens


def test_tashkeel_and_tatweel_fold():
    # شوكوبون vs شوكوبُون (damma) -> identical after normalization.
    assert normalize_ar("شوكوبون") == normalize_ar("شوكوبُون")
    # Tatweel is stripped.
    assert normalize_ar("صـيـدلـيـة") == normalize_ar("صيدلية")


def test_ta_marbuta_fold():
    # صيدليه vs صيدلية -> match (ة -> ه).
    assert normalize_ar("صيدلية") == normalize_ar("صيدليه")


def test_alef_and_ya_fold():
    assert normalize_ar("أحمد") == normalize_ar("احمد")
    assert normalize_ar("مصطفى") == normalize_ar("مصطفي")


def test_digit_fold():
    # مسجد الرضوان written with Arabic-Indic digits matches the Latin-digit form.
    assert normalize_ar("مسجد الرضوان ٢٠٢٦") == normalize_ar("مسجد الرضوان 2026")
    assert normalize_ar("۰۱۲۳٤٥") == "012345"


def test_token_overlap_after_fold():
    q = tokens("عايز اتأخر الطلب")
    doc = tokens("الطلب اتاخر كتير")
    assert "اتاخر" in q  # اتأخر folds to اتاخر
    assert q & doc  # they intersect


def test_contains_any_keyword_variants():
    assert contains_any("الطلب اتأخر جدا", ["اتاخر"]) == ["اتاخر"]
    assert contains_any("عايز استرجاع فلوسي", ["استرجاع", "نصب"]) == ["استرجاع"]
    assert contains_any("كل حاجة تمام شكرا", ["شكوى", "نصب"]) == []
