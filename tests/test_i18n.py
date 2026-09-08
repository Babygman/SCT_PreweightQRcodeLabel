import ast
import re
from pathlib import Path
from string import Formatter

from app.i18n import TRANSLATIONS, message, status_label, translate


def _catalog_keys_from_source() -> list[str]:
    tree = ast.parse(Path("app/i18n.py").read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "TRANSLATIONS"
            for target in node.targets
        )
    )
    assert isinstance(assignment.value, ast.Dict)
    return [ast.literal_eval(key) for key in assignment.value.keys]


def _placeholders(value: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in Formatter().parse(value)
        if field_name is not None
    }


def test_translation_catalog_has_unique_keys_and_matching_placeholders():
    source_keys = _catalog_keys_from_source()
    assert len(source_keys) == len(set(source_keys))
    assert set(source_keys) == set(TRANSLATIONS)
    for english, thai in TRANSLATIONS.items():
        assert _placeholders(thai) == _placeholders(english), english


def test_every_literal_template_translation_key_exists_in_catalog():
    missing = []
    for template in Path("app/templates").rglob("*.html"):
        source = template.read_text(encoding="utf-8")
        for match in re.finditer(r'''\bt\(\s*(["'])(.*?)\1''', source):
            if match.group(2) not in TRANSLATIONS:
                missing.append((str(template), match.group(2)))
    assert missing == []


def test_translation_helpers_preserve_codes_and_stored_status_values():
    assert translate("Standard Weight per Container") == (
        "น้ำหนักมาตรฐานต่อภาชนะ / Standard Weight per Container"
    )
    assert status_label("COMPLETED") == "เสร็จสมบูรณ์ / Completed"
    assert message("MATCH — R07047S1") == "ตรงกัน — R07047S1 / MATCH — R07047S1"
    assert message("Wrong Material: expected MAT-A, scanned MAT-B.") == (
        "วัตถุดิบไม่ถูกต้อง: ต้องการ MAT-A แต่สแกน MAT-B / "
        "Wrong Material: expected MAT-A, scanned MAT-B."
    )
    assert translate("Please select a valid date from the calendar.") == (
        "กรุณาเลือกวันที่ที่ถูกต้องจากปฏิทิน / "
        "Please select a valid date from the calendar."
    )
    assert translate("Expected Finish Date cannot be earlier than Production Date.") == (
        "วันที่คาดว่าจะผลิตเสร็จต้องไม่ก่อนวันที่ผลิต / "
        "Expected Finish Date cannot be earlier than Production Date."
    )
    assert translate("Open calendar for {field}", field="วันที่ผลิต / Production Date") == (
        "เปิดปฏิทินสำหรับ วันที่ผลิต / Production Date / "
        "Open calendar for วันที่ผลิต / Production Date"
    )
