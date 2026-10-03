"""源级检查:app.py 的 <style> 里还有没有「裸值」——裸色值 / 裸字号 / 裸间距。

审计脚本只看渲染结果,看不到「这个值是不是来自 token」。这个检查补那一半。
用法(默认查同目录的 app.py):
    python check_tokens.py            # 只报告
    python check_tokens.py --strict   # 有任何裸值就 exit 1

规则:
  · 十六进制色值只能出现在 :root 里,组件区只准用 var(--…)
  · 字号只准用 var(--fs-*) 或 em/rem(移动端输入框 16px 是防 iOS 缩放的规格,豁免)
  · 间距只准用 var(--sp-*)
  · 结构规格豁免:1px 边框、焦点环、44px 触控目标、断点
注释一律先剥掉再判断(中文注释里写着的 px 数值不是样式)。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

EXEMPT = (
    "border", "outline", "min-height", "min-width",
    "@media", "max-width", "vertical-align", "font-size:16px",
)
hex_re = re.compile(r"#[0-9a-fA-F]{3,8}\b")
px_re = re.compile(r"\b\d+(?:\.\d+)?px\b")


def strip_comments(text: str) -> str:
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            out.append(" ")
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=str(pathlib.Path(__file__).with_name("app.py")))
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()

    raw = pathlib.Path(a.path).read_text(encoding="utf-8")
    if "<style>" not in raw:
        print("找不到 <style> 块")
        return 2
    s = raw.index("<style>")
    e = raw.index("</style>", s)
    base = raw[:s].count("\n") + 1

    cleaned = strip_comments(raw[s:e]).splitlines()
    root_i = next(i for i, l in enumerate(cleaned) if l.strip().startswith(":root{"))
    root_j = next(i for i in range(root_i, len(cleaned)) if cleaned[i].strip() == "}")

    bad: list[str] = []
    for i, l in enumerate(cleaned):
        if root_i <= i <= root_j or not l.strip():
            continue
        if not (hex_re.search(l) or px_re.search(l)):
            continue
        if any(x in l for x in EXEMPT):
            continue
        kind = "裸色值" if hex_re.search(l) else "裸长度"
        bad.append(f"  {base + i}  [{kind}]  {l.strip()}")

    if bad:
        print(f"发现 {len(bad)} 处裸值:")
        print("\n".join(bad))
    else:
        print("OK:组件区没有裸色值 / 裸字号 / 裸间距")
    return 1 if (a.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
