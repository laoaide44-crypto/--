"""Focused stage-2 tests for preview, summaries, conflicts, ranges and comparison."""
from pathlib import Path

import fde_schedule

SAMPLES = Path(__file__).parent / "现场新增能力准备包" / "samples"


def load(name):
    return (SAMPLES / name).read_bytes()


def test_a_preview_summary_and_provenance():
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_VALID_two_stores.csv"))
    assert result.summary_label == "文件内已解析记录工时合计"
    assert result.clean_minutes == 1800
    assert [r["net_hours"] for r in result.preview_rows()] == [7.0, 4.0, 7.0, 4.0, 4.0, 4.0]
    assert result.preview_rows()[0]["source"] == {"row": 2, "fields": ["store_id", "staff_id", "shift_start", "shift_end", "break_minutes"]}
    assert result.by_staff_minutes == {"E-001": 840, "E-002": 240, "E-003": 480, "E-004": 240}
    assert result.by_store_minutes == {"S-01": 1080, "S-02": 720}


def test_c_overlap_only_clean_subtotal_and_no_unsafe_total():
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_OVERLAP_cross_store.csv"))
    assert result.conflicts[0]["rows"] == [2, 3]
    assert result.summary_label == "无异常记录小计"
    assert result.clean_minutes == 420
    assert result.total_minutes == 900
    assert result.can_apply is False
    assert all(row["included"] is False for row in result.preview_rows() if row["conflict"])


def test_d_range_and_completeness_are_separate():
    declared = {"stores": ["S-01", "S-02"], "start_date": "2026-08-03", "end_date": "2026-08-09"}
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_PARTIAL_coverage.csv"), declared)
    assert result.clean_minutes == 1260
    assert result.complete is False
    assert result.declared_range == declared
    assert result.actual_range["stores"] == ["S-01"]
    assert result.coverage_gaps == ["缺少门店: S-02", "缺少日期: 2026-08-05, 2026-08-06, 2026-08-07, 2026-08-08, 2026-08-09"]


def test_e_same_definition_comparison_preserves_self_report():
    declared = {"stores": ["S-01", "S-02"], "start_date": "2026-08-03", "end_date": "2026-08-05", "staff_ids": ["E-001", "E-002", "E-003", "E-004"]}
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_VALID_two_stores.csv"), declared)
    report = {**declared, "time_definition": "计划排班、已扣休息", "hours": 33, "source": "自报"}
    comparison = fde_schedule.compare_to_self_report(result, report)
    assert comparison["comparable"] is True
    assert comparison["difference_hours"] == -3.0
    assert comparison["self_report"] == report
    assert report["hours"] == 33


def test_f_plan_vs_attendance_is_not_comparable_without_delta():
    declared = {"stores": ["S-01", "S-02"], "start_date": "2026-08-03", "end_date": "2026-08-05"}
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_VALID_two_stores.csv"), declared)
    comparison = fde_schedule.compare_to_self_report(result, {
        **declared, "time_definition": "实际出勤", "hours": 26,
    })
    assert comparison["comparable"] is False
    assert comparison["message"] == "不可直接比较"
    assert "difference_hours" not in comparison
