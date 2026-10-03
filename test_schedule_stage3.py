"""Focused stage-3 direct tests for G/H/I schedule evidence behavior."""
from pathlib import Path
import json
import fde_schedule

SAMPLES = Path(__file__).parent / "现场新增能力准备包" / "samples"


def load(name):
    return (SAMPLES / name).read_bytes()


def test_g_confirmation_versions_switch_and_clean_undo():
    content = load("SYNTHETIC_VALID_two_stores.csv")
    result1 = fde_schedule.parse_schedule_csv(content)
    store = fde_schedule.ScheduleEvidenceStore()
    try:
        store.apply(content, result1, confirmed=False)
    except PermissionError:
        pass
    else:
        raise AssertionError("unconfirmed result was applied")
    assert store.versions == []

    v1 = store.apply(content, result1, source="未确认", synthetic=True, confirmed=True)
    assert v1.version_id == "v1"
    assert v1.file_hash == __import__("hashlib").sha256(content).hexdigest()
    assert v1.parser_rule_version == fde_schedule.RULE_VERSION
    assert v1.calculation["minutes"] == 1800
    assert v1.previous_version is None
    assert v1.application_status == "用户已确认应用"
    assert v1.synthetic is True
    assert v1.material_type == "合成测试材料"
    assert v1.source == "未确认"

    changed = content.replace(b",60\n", b",30\n", 1)
    result2 = fde_schedule.parse_schedule_csv(changed)
    v2 = store.apply(changed, result2, source="未确认", synthetic=True, confirmed=True)
    assert v2.version_id == "v2"
    assert v2.previous_version == "v1"
    assert v2.calculation["minutes"] != v1.calculation["minutes"]
    assert v2.change_report
    assert all(item["basis"] and item["source"] for item in v2.change_report)

    assert store.switch("v1").version_id == "v1"
    assert store.current.version_id == "v1"
    store.switch("v2")
    restored = store.undo()
    assert restored.version_id == "v1"
    assert store.current.version_id == "v1"
    assert store.versions[-1].application_status == "已撤回"
    assert [v.version_id for v in store.versions] == ["v1", "v2"]
    assert store.current.calculation == v1.calculation


def test_h_independent_source_and_synthetic_states_are_retained():
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_VALID_two_stores.csv"))
    store = fde_schedule.ScheduleEvidenceStore()
    version = store.apply(load("SYNTHETIC_VALID_two_stores.csv"), result,
                          source="未确认", synthetic=True,
                          material_type="合成测试材料", confirmed=True)
    payload = version.to_dict()
    assert payload["source"] == "未确认"
    assert payload["synthetic"] is True
    assert payload["material_type"] == "合成测试材料"
    assert payload["validation_status"] == "结构校验通过"
    assert payload["application_status"] == "用户已确认应用"
    assert "definition" in payload["calculation"]
    assert "合成测试材料" in store.export_text()


def test_i_page_and_export_are_same_source_and_row_basis_is_present():
    content = load("SYNTHETIC_VALID_two_stores.csv")
    result = fde_schedule.parse_schedule_csv(content)
    store = fde_schedule.ScheduleEvidenceStore()
    store.apply(content, result, source="未确认", synthetic=True, confirmed=True)
    page = store.page_data()
    exported = json.loads(store.export_text())
    assert exported == page
    current = page["current_version"]
    assert current["calculation"]["minutes"] == 1800
    assert current["calculation"]["by_staff_minutes"] == {
        "E-001": 840, "E-002": 240, "E-003": 480, "E-004": 240,
    }
    assert current["calculation"]["by_store_minutes"] == {"S-01": 1080, "S-02": 720}
    assert current["synthetic"] is True
    assert all(ref["row"] >= 2 and ref["fields"]
               for item in current["change_report"] for ref in item["source"]) is True


if __name__ == "__main__":
    for name in ("test_g_confirmation_versions_switch_and_clean_undo",
                 "test_h_independent_source_and_synthetic_states_are_retained",
                 "test_i_page_and_export_are_same_source_and_row_basis_is_present"):
        globals()[name]()
        print(f"PASS {name}")
