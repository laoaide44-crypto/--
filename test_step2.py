"""验证:第 2 步的提问计划真的驱动了追问流程(跳过材料已答的)。"""
import fde_ask
import fde_demo
import fde_ind_catering as IC
from streamlit.testing.v1 import AppTest

pack = fde_demo.load()
pl = fde_ask.plan(pack)

print("计划:", pl["summary"])
print("已答:", [a["key"] for a in pl["asked"]])
print("必问:", [a["key"] for a in pl["ask"]])
print()

at = AppTest.from_file("app.py", default_timeout=60)
at.run()
if at.exception:
    print("FAIL 初始:", at.exception); raise SystemExit(1)

ss = at.session_state
_c = IC.build_case({"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8}, {})
ss["screen"] = "app"
ss["case"] = _c
ss["inputs"] = {"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8}
ss["width_before"] = _c.headline_high - _c.headline_low
ss["step"] = "ask"
ss["qIndex"] = 0
ss["answers"] = {}
ss["summary"] = None
ss["qorder"] = [a["key"] for a in pl["ask"]]
ss["intake"] = pack
at.run()
if at.exception:
    print("FAIL:", at.exception); raise SystemExit(1)

texts = [m.value for m in at.markdown]
hit = [t for t in texts if "问题" in t and "/" in t]
print("界面上的问题计数:")
for h in hit[:3]:
    print("  ", h[:90].replace("\n", " "))

expect = f"问题 1 / {len(pl['ask'])}"
ok = any(expect in t for t in texts)
print()
print(f"期望出现「{expect}」: {ok}")
assert ok, "追问流程没有按计划走"

# 再验证:全部答完后能进契约页
ss["qIndex"] = len(pl["ask"])
at.run()
if at.exception:
    print("FAIL 契约:", at.exception); raise SystemExit(1)
print("答完全部计划问题后 → 契约页渲染正常")

print()
print("=== 全部通过 ===")
