"""录屏前空跑:按演示脚本的顺序把整条流程走一遍,**给每一步计时**。

用途(录制当天早上跑一次):
  · 确认每一步都点得动(现场不卡)
  · 拿到真实耗时 —— 分镜里写"要等十几秒"到底是多少秒
  · 顺便验证离线路径(用预跑结果)也是通的

跑法:  python dryrun_timing.py          # 联网全流程(含模型调用)
"""
from __future__ import annotations

import time

import fde_bench as B
from streamlit.testing.v1 import AppTest

STEPS: list[tuple[str, float]] = []


def timed(name: str, fn):
    t = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t
    STEPS.append((name, dt))
    print(f"  {dt:7.2f}s   {name}")
    return out


def click(at, label: str):
    next(b for b in at.button if b.label == label).click().run()


def marks(at) -> str:
    return " ".join(m.value for m in at.markdown)


def assert_clean(at, where: str):
    if list(at.exception):
        print(f"  ❌ 异常 @{where}: {list(at.exception)[:1]}")
        raise SystemExit(1)


print("=" * 62)
print("空跑 A · 联网全流程(主场景 = 快递物流)")
print("=" * 62)
B.select_industry("快递物流")

at = timed("A1 冷启动(打开页面)", lambda: AppTest.from_file("app.py", default_timeout=300).run())
assert_clean(at, "A1")
assert "两毛七" in marks(at), "开场文案不是物流的"
print("       开场页 OK(含「两毛七」)")

timed("A2 点「丢一份材料进来 →」", lambda: click(at, "丢一份材料进来 →"))
assert_clean(at, "A2")
timed("A3 选「用示例材料」", lambda: at.radio[0].set_value("用示例材料").run())
caps = " ".join(c.value for c in at.caption)
assert "网点群聊" in caps, f"示例材料不是物流的:{caps[:80]}"
print("       示例材料 OK(网点群聊)")

timed("A4 抽取事实(⚠️ 含模型调用,这里就是录屏要等的那段)", lambda: click(at, "抽取事实 →"))
assert_clean(at, "A4")
_msg = " ".join(s.value for s in list(at.success) + list(at.warning) + list(at.info))
_ok = "引用定位" in _msg
print(f"       回指校验出现: {_ok}")
_rows = [len(df.value) for df in at.dataframe]
print(f"       表格行数(事实/人物/时间线/未知项): {_rows}")

timed("A5 点「带着这份材料继续 →」(到参数表单)", lambda: click(at, "带着这份材料继续 →"))
assert_clean(at, "A5")
labels = [n.label for n in at.number_input]
print(f"       表单字段: {labels}")
assert any("日均件量" in x for x in labels), "表单没换成物流的"

timed("A6 点「算给我看 →」(到第一屏,含区间计算)", lambda: click(at, "算给我看 →"))
assert_clean(at, "A6")
_txt = marks(at)
assert "元/年" in _txt, "第一屏没出钱"
import re
_m = re.search(r"(\d[\d,\.]*)\s*[–-]\s*(\d[\d,\.]*)\s*元/年", _txt)
print(f"       第一屏区间: {_m.group(0) if _m else '(没匹配到,看下面原文)'}")

print("\n  -- 追问(一次只问一件事)--")
_n = 0
while _n < 8:
    qs = [b for b in at.button if b.label == "回答 →"]
    if not qs:
        break
    _q = ""
    for _ti in at.text_input:
        if _ti.label == "你的回答":
            _q = _ti.label
    t = time.perf_counter()
    if _q:
        next(_ti for _ti in at.text_input if _ti.label == "你的回答").set_value(
            "口径里含派费,场地和折旧没算进去")
    qs[0].click().run()
    dt = time.perf_counter() - t
    _n += 1
    STEPS.append((f"A7.{_n} 回答第 {_n} 问", dt))
    print(f"  {dt:7.2f}s   回答第 {_n} 问")
    assert_clean(at, f"A7.{_n}")

timed("A8 契约页(含模型生成结论)", lambda: at.run())
assert_clean(at, "A8")
_txt = marks(at)
print(f"       到契约页了: {'第 4 步' in _txt or '契约' in _txt}")

_def_sb = next(s for s in at.selectbox if s.label == "当前行业")
timed("A9 切侧栏到「餐饮门店」(收尾那 30 秒的证明)", lambda: _def_sb.select("餐饮门店").run())
assert_clean(at, "A9")
assert "几十万工资" in marks(at), "切行业后开场文案没变"
print("       切行业 OK(开场文案跟着变)")

print()
print("=" * 62)
print("空跑 B · 断网路径(用预跑结果)")
print("=" * 62)
B.select_industry("快递物流")
at2 = timed("B1 冷启动", lambda: AppTest.from_file("app.py", default_timeout=300).run())
timed("B2 点「丢一份材料进来 →」", lambda: click(at2, "丢一份材料进来 →"))
timed("B3 选「用预跑结果(离线演示)」",
      lambda: at2.radio[0].set_value("用预跑结果(离线演示)").run())
assert_clean(at2, "B3")
timed("B4 点「载入这份预跑结果 →」", lambda: click(at2, "载入这份预跑结果 →"))
assert_clean(at2, "B4")
_msg = " ".join(s.value for s in list(at2.warning) + list(at2.info))
assert "演示模式" in _msg, "没看到演示模式标注"
print("       演示模式标注 OK(含捕捉时间)")
timed("B5 点「带着这份材料继续 →」", lambda: click(at2, "带着这份材料继续 →"))
assert_clean(at2, "B5")
timed("B6 点「算给我看 →」", lambda: click(at2, "算给我看 →"))
assert_clean(at2, "B6")
print(f"       离线到第一屏: {'元/年' in marks(at2)}")

print()
print("=" * 62)
print("耗时汇总(录屏时照着这个数心里有底)")
print("=" * 62)
_total = sum(d for _, d in STEPS)
for _name, _dt in STEPS:
    bar = "█" * max(1, int(_dt * 2))
    print(f"  {_dt:7.2f}s  {bar}  {_name}")
print(f"\n  合计 {_total:.1f}s(其中模型相关的那几步是主要耗时)")
print("  ✅ 结论:全部步骤可点通,无卡死" if True else "")
