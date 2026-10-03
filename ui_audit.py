"""界面体检:把每一屏渲染出来的文字逐字导出来,给人眼找细节问题。

跑法:  python ui_audit.py            # 结果写到 ui-audit.txt
"""
from __future__ import annotations

import io
import sys

import fde_bench as B
from streamlit.testing.v1 import AppTest

OUT = "ui-audit.txt"
buf = io.StringIO()


def w(s=""):
    buf.write(str(s) + "\n")


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()


def dump(at, title: str):
    # 侧栏在每屏都会渲染 —— 去掉重复内容,只留主区
    _side = {
        (m.value or "").strip() for m in at.sidebar.markdown
    } | {c.value for c in at.sidebar.caption}

    w("=" * 70)
    w(f"### {title}")
    w("=" * 70)
    for m in at.markdown:
        t = (m.value or "").strip()
        if t and t not in _side:
            w(f"[markdown] {t[:600]}")
    for c in at.caption:
        if c.value not in _side:
            w(f"[caption ] {c.value}")
    for e in at.error:
        w(f"[ERROR   ] {e.value}")
    for e in at.warning:
        w(f"[warn    ] {e.value}")
    for e in at.info:
        w(f"[info    ] {e.value}")
    for e in at.success:
        w(f"[ok      ] {e.value}")
    for b in at.button:
        w(f"[button  ] {b.label}")
    for r in at.radio:
        w(f"[radio   ] label={r.label} options={r.options} value={r.value}")
    for s in at.selectbox:
        w(f"[select  ] label={s.label} options={s.options} value={s.value}")
    for n in at.number_input:
        w(f"[number  ] label={n.label} value={n.value} help={getattr(n, 'help', None)}")
    for t in at.text_input:
        w(f"[text    ] label={t.label} placeholder={getattr(t, 'placeholder', None)}")
    for d in at.dataframe:
        try:
            w(f"[table   ] rows={len(d.value)} cols={list(d.value.columns)}")
        except Exception:
            w("[table   ] (读不出)")
    for x in at.expander:
        w(f"[expander] {x.label}")
    for c in at.checkbox:
        w(f"[checkbox] {c.label}")
    w("")


w("# 界面体检导出(逐屏文字,已去掉重复的侧栏)")
w("")
B.select_industry("快递物流")

at0 = AppTest.from_file("app.py", default_timeout=300).run()
w("--- 侧栏(每屏都在,单独看一次)---")
for m in at0.sidebar.markdown:
    _t = (m.value or "").strip()
    w(f"[sidebar/md] {_t[:300]}")
for c in at0.sidebar.caption:
    w(f"[sidebar/cap] {c.value}")
for s in at0.sidebar.selectbox:
    w(f"[sidebar/select] label={s.label} options={s.options} value={s.value}")
w("")

at = at0
dump(at, "① 开场页(快递物流)")

# 侧栏在所有屏都一样,单独看一眼
w("--- 侧栏 ---")
for m in at.sidebar.markdown:
    w(f"[sidebar/md] {(m.value or '')[:200]}")
for c in at.sidebar.caption:
    w(f"[sidebar/cap] {c.value}")
w("")

click(at, "丢一份材料进来 →")
dump(at, "② 丢材料页(还没载入材料)")

at.radio[0].set_value("用预跑结果(离线演示)").run()
dump(at, "② b 丢材料页(选了「用预跑结果」,还没点载入)")

click(at, "载入这份预跑结果 →")
dump(at, "③ 材料已载入(抽取结果 + 只问该问的 + 资产库)")

click(at, "带着这份材料继续 →")
dump(at, "④ 参数表单")

click(at, "算给我看 →")
dump(at, "⑤ 第一屏(钱)+ 追问第 1 问")

n = 0
while n < 8:
    qs = [b for b in at.button if b.label == "回答 →"]
    if not qs:
        break
    if at.text_input:
        at.text_input[0].set_value("口径里含派费,场地和折旧没算")
    qs[0].click().run()
    n += 1
dump(at, f"⑥ 契约页(答完 {n} 问)")

w("--- 换行业:餐饮的开场页 ---")
at.selectbox[0].select("餐饮门店").run()
dump(at, "⑦ 开场页(餐饮)")

buf.seek(0)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(buf.getvalue())
print(f"已写入 {OUT} —— {len(buf.getvalue().splitlines())} 行")
