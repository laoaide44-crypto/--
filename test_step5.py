"""验证第 5 步在界面里真的跑通:资产库给假设 + 契约页一键沉淀。"""
import os
import tempfile

import fde_reuse as R

# 隔离测试库(AppTest 与主进程共用同一模块对象,先改再跑)
R.LIB = os.path.join(tempfile.gettempdir(), "reuse-app-test.json")
if os.path.exists(R.LIB):
    os.remove(R.LIB)

import fde_demo
import fde_ind_catering as IC
from streamlit.testing.v1 import AppTest

pack = fde_demo.load()
assert pack, "先跑 capture_demo.py"

print("=== 1) 材料页:空库时不该乱给假设 ===")
at = AppTest.from_file("app.py", default_timeout=60)
at.run()
at.session_state["screen"] = "app"
_c = IC.build_case({"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8}, {})
at.session_state["case"] = _c
at.session_state["inputs"] = {"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8}
at.session_state["width_before"] = _c.headline_high - _c.headline_low
at.session_state["step"] = "input"
at.session_state["answers"] = {}
at.session_state["qIndex"] = 0
at.session_state["summary"] = None
at.session_state["intake"] = pack
at.run()
if at.exception:
    print("  FAIL:", at.exception); raise SystemExit(1)
print("  空库渲染正常")

print()
print("=== 2) 契约页:找「沉淀」按钮并点它 ===")
at.session_state["step"] = "done"
at.session_state["answers"] = {
    "part_time_ratio": 0.27, "who_does_it": "店长自己在 Excel 里排,一周至少一天",
    "how_measured": "没有,总部也没有准数", "resister": "店员担心以后工时被压",
    "tried_before": "去年买过一套排班软件,没人用,最后就放着",
    "internal_data": "可以,我发你一份脱敏的",
}
at.run()
if at.exception:
    print("  FAIL:", at.exception); raise SystemExit(1)

btn = next((b for b in at.button if "沉淀" in (b.label or "")), None)
print("  找到按钮:", btn.label if btn else "(没找到)")
assert btn, "契约页上没有沉淀按钮"

btn.click()
at.run()
if at.exception:
    print("  FAIL 点击后:", at.exception); raise SystemExit(1)

hv = at.session_state.get("harvested")
print("  沉淀结果:", {k: hv[k] for k in ("code", "added", "total")} if hv else None)
assert hv and hv["added"] > 0, "没有沉淀出资产"

print()
print("=== 3) 库里现在有东西了吗 ===")
st = R.stats()
print(" ", st)
assert st["total"] > 0

print()
print("=== 4) 新客户材料进来 → 应能拿到假设 ===")
hits = R.suggest(pack)
print(f"  匹配到 {len(hits)} 条")
assert hits, "应该能匹配到"

print()
print("=== 全部通过 ===")
print(f"(测试库在 {R.LIB})")
