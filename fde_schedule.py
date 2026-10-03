"""Deterministic CSV schedule parsing and validation for stage 1."""
from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

REQUIRED_FIELDS = ("store_id", "staff_id", "shift_start", "shift_end", "break_minutes")
RULE_VERSION = "schedule-csv-v1"


@dataclass
class Issue:
    code: str
    level: str
    row: int | None
    field: str | None
    message: str
    value: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedRow:
    row_number: int
    store_id: str
    staff_id: str
    shift_start: datetime
    shift_end: datetime
    break_minutes: int
    net_minutes: int
    duplicate_of: int | None = None
    conflict: bool = False

    @property
    def net_hours(self) -> float:
        return _minutes(self.net_minutes)

    @property
    def source_references(self) -> dict[str, Any]:
        """Stable provenance for every value used in the row calculation."""
        return {"row": self.row_number, "fields": [
            "store_id", "staff_id", "shift_start", "shift_end", "break_minutes"
        ]}

    def key(self) -> tuple[Any, ...]:
        return (self.store_id.strip(), self.staff_id.strip(),
                self.shift_start.astimezone(timezone.utc).isoformat(),
                self.shift_end.astimezone(timezone.utc).isoformat(),
                self.break_minutes)


@dataclass
class ScheduleResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    rows: list[ParsedRow] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    unknown_columns: list[str] = field(default_factory=list)
    duplicate_count: int = 0
    duplicate_minutes: int = 0
    actual_range: dict[str, Any] = field(default_factory=dict)
    declared_range: dict[str, Any] | None = None
    coverage_gaps: list[str] = field(default_factory=list)
    subtotal_minutes: int = 0
    total_minutes: int = 0
    complete: bool = False
    status: str = "待校验"
    summary_kind: str = "无"
    summary_label: str = ""
    clean_minutes: int = 0
    duplicate_impact_minutes: int = 0
    by_staff_minutes: dict[str, int] = field(default_factory=dict)
    by_store_minutes: dict[str, int] = field(default_factory=dict)

    @property
    def can_apply(self) -> bool:
        return not self.errors and not self.conflicts

    def preview_rows(self) -> list[dict[str, Any]]:
        """Return deterministic, human-auditable row previews.

        Invalid rows are absent because they cannot produce a net duration; valid
        duplicate rows remain visible and point at their retained source row.
        """
        return [{
            "row": row.row_number,
            "store_id": row.store_id,
            "staff_id": row.staff_id,
            "net_minutes": row.net_minutes,
            "net_hours": row.net_hours,
            "source": row.source_references,
            "duplicate_of": row.duplicate_of,
            "conflict": row.conflict,
            "included": row.duplicate_of is None and not row.conflict,
        } for row in self.rows]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["errors"] = [i.to_dict() for i in self.errors]
        value["warnings"] = [i.to_dict() for i in self.warnings]
        value["preview_rows"] = self.preview_rows()
        value["complete"] = self.complete
        return value


def _issue(code: str, level: str, row: int | None, field: str | None,
           message: str, value: Any = "") -> Issue:
    return Issue(code, level, row, field, message, str(value))


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    # fromisoformat accepts dates and naive datetimes, so enforce the contract first.
    if "T" not in text or ("+" not in text[10:] and "-" not in text[10:]):
        raise ValueError("ISO-8601 完整日期时间必须带时区偏移")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("时间必须带时区偏移")
    return parsed


def _minutes(value: int) -> float:
    return float((Decimal(value) / Decimal(60)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _range_gaps(declared: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    stores = declared.get("stores") or declared.get("store_ids")
    if stores:
        missing = sorted(set(stores) - set(actual.get("stores", [])))
        if missing:
            gaps.append("缺少门店: " + ", ".join(missing))
    start = declared.get("start_date")
    end = declared.get("end_date")
    if start and end and actual.get("dates"):
        try:
            lo, hi = date.fromisoformat(str(start)), date.fromisoformat(str(end))
            observed = set(date.fromisoformat(x) for x in actual["dates"])
            missing_dates = [d.isoformat() for d in (lo.fromordinal(n) for n in range(lo.toordinal(), hi.toordinal() + 1)) if d not in observed]
            if missing_dates:
                gaps.append("缺少日期: " + ", ".join(missing_dates))
        except ValueError:
            pass
    return gaps


def parse_schedule_csv(content: str | bytes, declared_range: dict[str, Any] | None = None) -> ScheduleResult:
    """Parse UTF-8 CSV deterministically; never interprets cell text as instructions."""
    result = ScheduleResult(declared_range=declared_range)
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    else:
        content = content.lstrip("\ufeff")
    try:
        reader = csv.reader(io.StringIO(content, newline=""))
        header = next(reader)
    except (StopIteration, csv.Error, UnicodeDecodeError) as exc:
        result.errors.append(_issue("E6", "error", 1, None, "无法读取 CSV 表头", exc))
        result.status = "有阻断问题"
        return result

    normalized = [cell.strip().lower() for cell in header]
    positions: dict[str, int] = {}
    for index, name in enumerate(normalized):
        if name in REQUIRED_FIELDS and name not in positions:
            positions[name] = index
    missing = [name for name in REQUIRED_FIELDS if name not in positions]
    if missing or len(set(normalized)) != len(normalized):
        detail = "缺少必需列: " + ", ".join(missing) if missing else "表头存在重复列"
        result.errors.append(_issue("E6", "error", 1, None, detail))
        result.status = "有阻断问题"
        return result
    result.unknown_columns = [header[i].strip() for i, name in enumerate(normalized) if name not in REQUIRED_FIELDS]
    if result.unknown_columns:
        result.warnings.append(_issue("W3", "warning", 1, None, "忽略未知额外列: " + ", ".join(result.unknown_columns)))

    seen: dict[tuple[Any, ...], int] = {}
    offsets: set[str] = set()
    raw_rows: list[ParsedRow] = []
    try:
        for row in reader:
            row_number = reader.line_num
            if not any(cell.strip() for cell in row):
                continue
            values = {name: row[pos] if pos < len(row) else "" for name, pos in positions.items()}
            row_errors: list[Issue] = []
            for name in REQUIRED_FIELDS:
                if not values[name].strip():
                    row_errors.append(_issue("E1", "error", row_number, name, "必需字段为空", values[name]))
            for name in ("store_id", "staff_id"):
                value = values[name]
                if any(ch in value for ch in (",", '"', "\n", "\r")) or len(value.strip()) > 64:
                    row_errors.append(_issue("E7", "error", row_number, name, "标识字段含非法字符或超过 64 个字符", value))
            starts = ends = None
            if not any(i.field == "shift_start" for i in row_errors):
                try:
                    starts = _parse_datetime(values["shift_start"])
                    offsets.add(str(starts.utcoffset()))
                except (ValueError, TypeError) as exc:
                    row_errors.append(_issue("E2", "error", row_number, "shift_start", f"解析失败: {exc}", values["shift_start"]))
            if not any(i.field == "shift_end" for i in row_errors):
                try:
                    ends = _parse_datetime(values["shift_end"])
                    offsets.add(str(ends.utcoffset()))
                except (ValueError, TypeError) as exc:
                    row_errors.append(_issue("E2", "error", row_number, "shift_end", f"解析失败: {exc}", values["shift_end"]))
            break_value = None
            if not any(i.field == "break_minutes" for i in row_errors):
                try:
                    text = values["break_minutes"].strip()
                    if not text or any(ch not in "0123456789-+" for ch in text) or text.count("-") > 1 or text.count("+") > 1:
                        raise ValueError("必须为整数")
                    break_value = int(text)
                except (ValueError, TypeError) as exc:
                    row_errors.append(_issue("E2", "error", row_number, "break_minutes", f"解析失败: {exc}", values["break_minutes"]))
            if starts is not None and ends is not None:
                duration = int((ends.astimezone(timezone.utc) - starts.astimezone(timezone.utc)).total_seconds() // 60)
                if ends <= starts:
                    row_errors.append(_issue("E3", "error", row_number, "shift_end", "结束时间早于或等于开始时间", values["shift_end"]))
                if break_value is not None:
                    if break_value < 0:
                        row_errors.append(_issue("E4", "error", row_number, "break_minutes", "休息分钟数不能为负", break_value))
                    elif duration > 0 and break_value >= duration:
                        row_errors.append(_issue("E5", "error", row_number, "break_minutes", "休息分钟数大于或等于班次长度", break_value))
            if row_errors:
                result.errors.extend(row_errors)
                continue
            parsed = ParsedRow(row_number, values["store_id"].strip(), values["staff_id"].strip(), starts, ends, break_value, duration - break_value)
            key = parsed.key()
            if key in seen:
                parsed.duplicate_of = seen[key]
                result.duplicate_count += 1
                result.duplicate_minutes += parsed.net_minutes
                result.warnings.append(_issue("W1", "warning", row_number, None, f"完全重复（重复于第 {seen[key]} 行）"))
            else:
                seen[key] = row_number
            raw_rows.append(parsed)
    except csv.Error as exc:
        result.errors.append(_issue("E2", "error", reader.line_num or None, None, f"CSV 解析失败: {exc}"))

    if len(offsets) > 1:
        result.warnings.append(_issue("W4", "warning", None, None, "文件内时区偏移不一致，按绝对时刻计算"))

    active = [row for row in raw_rows if row.duplicate_of is None]
    by_staff: dict[str, list[ParsedRow]] = {}
    for row in active:
        by_staff.setdefault(row.staff_id, []).append(row)
    pairs: set[tuple[int, int]] = set()
    for staff_rows in by_staff.values():
        for index, left in enumerate(staff_rows):
            for right in staff_rows[index + 1:]:
                start = max(left.shift_start.astimezone(timezone.utc), right.shift_start.astimezone(timezone.utc))
                end = min(left.shift_end.astimezone(timezone.utc), right.shift_end.astimezone(timezone.utc))
                if start < end:
                    pair = tuple(sorted((left.row_number, right.row_number)))
                    if pair in pairs:
                        continue
                    pairs.add(pair)
                    minutes = int((end - start).total_seconds() // 60)
                    left.conflict = right.conflict = True
                    result.conflicts.append({"rows": list(pair), "staff_id": left.staff_id, "stores": [left.store_id, right.store_id], "overlap_minutes": minutes})
                    result.warnings.append(_issue("W2", "warning", left.row_number, "staff_id", f"与第 {right.row_number} 行班次重叠（{minutes} 分钟）", left.staff_id))
    result.rows = raw_rows
    clean = [row for row in active if not row.conflict]
    result.clean_minutes = sum(row.net_minutes for row in clean)
    result.subtotal_minutes = result.clean_minutes
    result.total_minutes = sum(row.net_minutes for row in active)
    result.duplicate_impact_minutes = result.duplicate_minutes
    result.by_staff_minutes = _group_minutes(clean, "staff_id")
    result.by_store_minutes = _group_minutes(clean, "store_id")
    dates = sorted({row.shift_start.date().isoformat() for row in active} | {row.shift_end.date().isoformat() for row in active})
    result.actual_range = {"stores": sorted({row.store_id for row in active}), "dates": dates, "start_date": dates[0] if dates else None, "end_date": dates[-1] if dates else None, "staff_ids": sorted({row.staff_id for row in active}), "staff_count": len({row.staff_id for row in active}), "shift_count": len(active)}
    result.coverage_gaps = _range_gaps(declared_range or {}, result.actual_range)
    if result.coverage_gaps:
        result.warnings.append(_issue("W5", "warning", None, None, "文件未覆盖用户声明范围: " + "; ".join(result.coverage_gaps)))
    result.complete = bool(declared_range) and not result.coverage_gaps
    result.summary_kind = "无异常记录小计" if result.errors or result.conflicts else "文件内已解析记录工时合计"
    result.summary_label = result.summary_kind
    result.status = "有阻断问题" if result.errors else "结构校验通过"
    return result


def _group_minutes(rows: Iterable[ParsedRow], attribute: str) -> dict[str, int]:
    grouped: dict[str, int] = {}
    for row in rows:
        key = str(getattr(row, attribute))
        grouped[key] = grouped.get(key, 0) + row.net_minutes
    return dict(sorted(grouped.items()))


def compare_to_self_report(result: ScheduleResult, self_report: dict[str, Any]) -> dict[str, Any]:
    """Compare a parsed plan with a self-report without mutating either history.

    The report uses the same four dimensions as the field specification. Any
    mismatch makes the result non-comparable and deliberately omits a delta.
    """
    report = dict(self_report or {})
    actual = result.actual_range
    declared = result.declared_range or {}
    expected = {
        "stores": declared.get("stores", actual.get("stores", [])),
        "start_date": declared.get("start_date", actual.get("start_date")),
        "end_date": declared.get("end_date", actual.get("end_date")),
        "staff_ids": declared.get("staff_ids", actual.get("staff_ids", [])),
        "time_definition": "计划排班、已扣休息",
    }
    supplied = {
        "stores": report.get("stores", report.get("store_ids", [])),
        "start_date": report.get("start_date"),
        "end_date": report.get("end_date"),
        "staff_ids": report.get("staff_ids", []),
        "time_definition": report.get("time_definition", report.get("kind", "")),
    }
    dimensions = {}
    for key in expected:
        left, right = expected[key], supplied[key]
        if key in {"stores", "staff_ids"}:
            left, right = sorted(set(left or [])), sorted(set(right or []))
        dimensions[key] = {"match": left == right, "plan": left, "self_report": right}
    comparable = all(item["match"] for item in dimensions.values())
    out: dict[str, Any] = {"comparable": comparable, "dimensions": dimensions, "self_report": report}
    if comparable:
        report_minutes = report.get("minutes")
        report_hours = report.get("hours")
        if report_minutes is None and report_hours is not None:
            report_minutes = int((Decimal(str(report_hours)) * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if report_minutes is not None:
            out["plan_minutes"] = result.total_minutes if not (result.errors or result.conflicts) else result.subtotal_minutes
            out["self_report_minutes"] = int(report_minutes)
            out["difference_minutes"] = out["plan_minutes"] - out["self_report_minutes"]
            out["difference_hours"] = _minutes(out["difference_minutes"])
    else:
        out["message"] = "不可直接比较"
    return out


# Descriptive alias for callers that prefer the domain wording.
compare_with_self_report = compare_to_self_report


def hours(minutes: int) -> float:
    return _minutes(minutes)
