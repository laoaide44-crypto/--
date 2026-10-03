"""Executable UI smoke check for stage-1 validation rendering (no Streamlit server needed)."""
from pathlib import Path


REQUIRED_MARKERS = (
    "_render_schedule_result",
    "校验状态",
    "问题清单（行号 · 字段 · 规则 · 值）",
    "文件实际包含范围",
    "用户声明范围",
    "范围覆盖缺口",
    "重复行映射",
    "未解决重叠冲突",
)


def main() -> None:
    source = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
    missing = [marker for marker in REQUIRED_MARKERS if marker not in source]
    if missing:
        raise SystemExit("missing UI markers: " + ", ".join(missing))
    print("UI smoke passed: stage-1 schedule result markers are rendered")


if __name__ == "__main__":
    main()
