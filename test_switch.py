"""终极验证:界面切到物流,表单、第一屏、契约都得跟着变 —— 而且引擎一个字没改。"""
import fde_bench as B
import fde_ind_logistics as IL
from streamlit.testing.v1 import AppTest

print("=== 0) 开场文案也应跟着行业变 ===")
for _ind, _kw in (("快递物流", "两毛七"), ("餐饮门店", "几十万工资")):
    B.select_industry(_ind)
    _at = AppTest.from_file("app.py", default_timeout=60)
    _at.run()
    if _at.exception:
        print("  FAIL:", _at.exception); raise SystemExit(1)
    _txt = " ".join(m.value for m in _at.markdown)
    assert _kw in _txt, f"{_ind} 的开场文案没跟上:{_kw} 不在页面里"
    print(f"  {_ind}: 开场文案 OK (含「{_kw}」)")

print()
print("=== 1) 切到快递物流,界面表单应该换成物流的输入项 ===")
B.select_industry("快递物流")
at = AppTest.from_file("app.py", default_timeout=60)
at.run()
if at.exception:
    print("  FAIL:", at.exception); raise SystemExit(1)
at.session_state["screen"] = "app"
at.run()
if at.exception:
    print("  FAIL(进输入页):", at.exception); raise SystemExit(1)
labels = [n.label for n in at.number_input]
print("  表单字段:", labels)
assert any("日均件量" in x for x in labels), f"表单没换成物流的:{labels}"
assert not any("单店月流水" in x for x in labels), "还在显示餐饮的字段"
print("  ✅ 表单已按行业切换")

print()
print("=== 2) 用物流的数跑一遍 → 第一屏 ===")
_c = IL.build_case({"parcels_per_day": 30000, "cost_per_parcel": 2.05, "sites": 8})
print("  钱:", _c.money_range())
print("  参照系:", _c.reference_note[:50], "…")
at.session_state["screen"] = "app"
at.session_state["case"] = _c
at.session_state["inputs"] = {"parcels_per_day": 30000, "cost_per_parcel": 2.05, "sites": 8}
at.session_state["width_before"] = _c.headline_high - _c.headline_low
at.session_state["step"] = "report"
at.session_state["answers"] = {}
at.session_state["qIndex"] = 0
at.session_state["summary"] = None
at.run()
if at.exception:
    print("  FAIL:", at.exception); raise SystemExit(1)
texts = " ".join(m.value for m in at.markdown)
assert "元/年" in texts and "单票" in texts, "第一屏没显示物流的内容"
print("  ✅ 第一屏渲染的是物流的口径")

print()
print("=== 3) 契约页 ===")
at.session_state["step"] = "done"
at.session_state["answers"] = {"how_measured": "没有", "resister": "一线担心工时被压",
                              "internal_data": "可以给脱敏数据"}
at.run()
if at.exception:
    print("  FAIL:", at.exception); raise SystemExit(1)
texts = " ".join(m.value for m in at.markdown)
assert "快递物流" in texts, "契约里没有行业名"
assert "单票" in texts and "派费" in texts, "契约里没有物流的口径与边界"
print("  ✅ 契约渲染成物流的")

print()
print("=== 4) 切回餐饮,一切照旧 ===")
B.select_industry("餐饮门店")
at2 = AppTest.from_file("app.py", default_timeout=60)
at2.run()
at2.session_state["screen"] = "app"
at2.run()
labels2 = [n.label for n in at2.number_input]
print("  表单字段:", labels2)
assert any("单店月流水" in x for x in labels2), "切回餐饮后表单没回来"
print("  ✅ 切回餐饮正常")

print()
print("=== 全部通过:两个行业走同一个界面、同一份契约 ===")
