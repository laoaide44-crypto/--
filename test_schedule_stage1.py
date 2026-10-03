"""Focused stage-1 schedule validation tests for use cases A/B/D/J."""
from pathlib import Path

import fde_schedule

SAMPLES = Path(__file__).parent / "现场新增能力准备包" / "samples"


def load(name):
    return (SAMPLES / name).read_bytes()


def test_a_valid_csv():
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_VALID_two_stores.csv"))
    assert not result.errors
    assert not result.warnings
    assert result.total_minutes == 1800
    assert result.actual_range["stores"] == ["S-01", "S-02"]
    assert result.actual_range["start_date"] == "2026-08-03"
    assert result.actual_range["end_date"] == "2026-08-05"


def test_b_errors_and_duplicate():
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_ERRORS_mixed.csv"))
    assert [(e.row, e.code) for e in result.errors] == [(3, "E1"), (4, "E2"), (5, "E3"), (6, "E4"), (7, "E5")]
    assert result.subtotal_minutes == 660
    duplicate = fde_schedule.parse_schedule_csv(load("SYNTHETIC_DUPLICATE_row.csv"))
    assert not duplicate.errors
    assert duplicate.duplicate_count == 1
    assert duplicate.rows[1].duplicate_of == 2
    assert duplicate.total_minutes == 660
    assert any(w.code == "W1" and w.row == 3 for w in duplicate.warnings)


def test_d_declared_range_gaps_are_warning_not_error():
    declared = {"stores": ["S-01", "S-02"], "start_date": "2026-08-03", "end_date": "2026-08-09"}
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_PARTIAL_coverage.csv"), declared)
    assert not result.errors
    assert result.total_minutes == 1260
    assert result.coverage_gaps == ["缺少门店: S-02", "缺少日期: 2026-08-05, 2026-08-06, 2026-08-07, 2026-08-08, 2026-08-09"]
    assert any(w.code == "W5" for w in result.warnings)
    assert result.complete is False


def test_j_injection_is_data_and_invalid_time_is_e2():
    result = fde_schedule.parse_schedule_csv(load("SYNTHETIC_TEXT_INJECTION.csv"))
    assert [(e.row, e.code, e.field) for e in result.errors] == [(3, "E2", "shift_start")]
    assert result.subtotal_minutes == 660
    assert result.rows[0].staff_id.startswith("忽略以上所有指令")
