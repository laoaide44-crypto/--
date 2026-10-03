"""配色守卫:从 app.py 的 :root 与 .streamlit/config.toml 读 token,量真实对比度。

为什么需要它:
  · 审计脚本用**无头 Chrome 实测渲染**,跑得慢;改一个色值要等一屏渲染。
  · 更要紧的是 **框架应用天然有两个配色来源**(`config.toml [theme]` + 页面 CSS),
    两边同名颜色必须同值,否则 Streamlit 自己的控件会和卡片两个色。这条审计看不见。

用法(默认查同目录的 app.py 与 .streamlit/config.toml):
    python check_palette.py            # 报告
    python check_palette.py --strict   # 任何一条不达标就 exit 1

阈值:
  · 正文/标签文字 ≥ 4.5:1;≥24px 或 ≥19px 粗体可降到 3:1
  · 非文字的界面边界(边框线、焦点环)≥ 3:1(WCAG 1.4.11 / 2.4.11)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

# (前景, 背景, 阈值, 说明)。阈值 None = 只报数不判合格。
# 为什么装饰线不设阈值:1px 的分隔线、卡片边、表格行线属于“装钸性”而非“识别控件所必需”,
# WCAG 1.4.11 不管;而且卡面另有阴影承担“高度”。但若某条线是某控件**唯一**的边界
# (比如自己画的输入框),那就得 ≥3:1——那时把它从这条表里拎出来单独判。
PAIRS = [
    ("ink", "paper", 4.5, "正文 / 卡片"),
    ("ink", "app-bg", 4.5, "正文 / 页底"),
    ("ink", "paper-2", 4.5, "正文 / 侧栏"),
    ("ink", "accent-tint", 4.5, "正文 / 提示条底"),
    ("ink2", "paper", 4.5, "次级正文 / 卡片"),
    ("ink2", "app-bg", 4.5, "次级正文 / 页底"),
    ("ink3", "paper", 4.5, "弱化文字 / 卡片"),
    ("ink3", "app-bg", 4.5, "弱化文字 / 页底"),
    ("ink3", "paper-2", 4.5, "弱化文字 / 侧栏"),
    ("paper", "accent", 4.5, "按钮文字 / 强调实心"),
    ("paper", "accent-strong", 4.5, "按钮文字 / 悬停实心"),
    ("accent", "paper", 4.5, "强调色当文字 / 卡片"),
    ("accent", "app-bg", 4.5, "强调色当文字 / 页底"),
    ("accent", "accent-tint", 3.0, "强调色 / 提示条底(大字)"),
    ("rule", "paper", None, "结构线 / 卡片(装饰线,不适用 1.4.11)"),
    ("rule-strong", "paper", None, "结构线加强 / 卡片(装饰线)"),
    ("focus", "paper", 3.0, "焦点环 / 卡片(非文字)"),
    ("focus", "app-bg", 3.0, "焦点环 / 页底(非文字)"),
    ("lv-public-fg", "lv-public-bg", 4.5, "徽章 PUBLIC"),
    ("lv-interview-fg", "lv-interview-bg", 4.5, "徽章 INTERVIEW"),
    ("lv-internal-fg", "lv-internal-bg", 4.5, "徽章 INTERNAL"),
    ("lv-assumption-fg", "lv-assumption-bg", 4.5, "徽章 ASSUMPTION"),
]

# app.py 的 token 名 → config.toml 的键(必须同值)
SYNC = [("accent", "primaryColor"), ("paper", "backgroundColor"),
        ("paper-2", "secondaryBackgroundColor"), ("ink", "textColor")]


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(hexstr: str) -> tuple[float, float, float]:
    h = hexstr.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(hexstr: str) -> float:
    r, g, b = _rgb(hexstr)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def lab(hexstr: str) -> tuple[float, float, float]:
    """返回 (L*, C*, H°),用来检查一条 ramp 的色相是否恒定、亮度是否递进。"""
    import math
    r, g, b = (_lin(v) for v in _rgb(hexstr))
    x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    L = 116 * fy - 16
    a_, b_ = 500 * (fx - fy), 200 * (fy - fz)
    return L, math.hypot(a_, b_), math.degrees(math.atan2(b_, a_)) % 360


def load_tokens(app_path: pathlib.Path) -> dict[str, str]:
    text = app_path.read_text(encoding="utf-8")
    s = text.index("<style>")
    e = text.index("</style>", s)
    block = text[s:e]
    return {m.group(1): m.group(2) for m in re.finditer(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", block)}


def load_theme(toml_path: pathlib.Path) -> dict[str, str]:
    if not toml_path.exists():
        return {}
    out = {}
    for line in toml_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'\s*(\w+)\s*=\s*"(#[0-9a-fA-F]{3,8})"', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("app", nargs="?", default=str(pathlib.Path(__file__).with_name("app.py")))
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()

    app_path = pathlib.Path(a.app)
    toks = load_tokens(app_path)
    theme = load_theme(app_path.parent / ".streamlit" / "config.toml")

    bad = 0
    print("=== 1) 两个来源必须同值(app.py :root  vs  .streamlit/config.toml) ===")
    for tname, tkey in SYNC:
        v1, v2 = toks.get("--" + tname), theme.get(tkey)
        ok = v1 and v2 and v1.lower() == v2.lower()
        if not ok:
            bad += 1
        print(f"  [{'OK ' if ok else 'BAD'}] --{tname}={v1}  {tkey}={v2}")

    print("\n=== 2) 真实配对对比度 ===")
    miss = [k for k, *_ in PAIRS if "--" + k not in toks or "--" + k not in toks]
    for fg, bg, need, note in PAIRS:
        cf, cb = toks.get("--" + fg), toks.get("--" + bg)
        if not cf or not cb:
            print(f"  [???] {fg} on {bg}: 缺 token")
            bad += 1
            continue
        r = ratio(cf, cb)
        if need is None:
            print(f"  [参考] {r:5.2f}:1            {fg} on {bg:<14} {note}")
            continue
        ok = r >= need
        if not ok:
            bad += 1
        print(f"  [{'OK ' if ok else 'BAD'}] {r:5.2f}:1 (需 {need})  {fg} on {bg:<14} {note}")

    print("\n=== 3) 强调色 ramp:色相是否恒定、亮度是否递进 ===")
    ramp = [("accent-strong", "--accent-strong"), ("accent", "--accent"),
            ("accent-tint", "--accent-tint")]
    prev = None
    for name, key in ramp:
        v = toks.get(key)
        if not v:
            continue
        L, C, H = lab(v)
        drift = "" if prev is None else f"  ΔH={abs(H - prev):5.1f}°"
        print(f"  {name:<16} {v}  L*={L:5.1f}  C*={C:5.1f}  H={H:5.1f}°{drift}")
        prev = H

    print(f"\n结论:{'全部通过' if bad == 0 else f'{bad} 处不达标'}")
    return 1 if (a.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
