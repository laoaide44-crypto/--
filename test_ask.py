"""验证第 2 步「只问该问的」:用真实材料跑一遍提问计划。"""
import fde_ask
import fde_demo

pack = fde_demo.load()
if not pack:
    print("没有 demo 缓存,先跑 capture_demo.py")
    raise SystemExit(1)

p = fde_ask.plan(pack)

print("=== 结论 ===")
print(" ", p["summary"])
print()

print(f"=== 材料已经回答了的({len(p['asked'])} 个,这些不用问)===")
if not p["asked"]:
    print("  (无)")
for a in p["asked"]:
    print(f"  · {a['question']}")
    print(f"    依据:「{(a['quote'] or '')[:60]}」")
print()

print(f"=== 还必须要问的({len(p['ask'])} 个,按优先级排)===")
for i, a in enumerate(p["ask"], 1):
    tag = "必须当面问" if a["must"] else "可以顺手问"
    print(f"  {i}. {a['question']}")
    print(f"     为什么 : {a['why']}")
    print(f"     答了会 : {a['impact']}")
    print(f"     从哪拿 : {a['how']}  ({tag})")
    print()

if p["missing_params"]:
    print("=== 算不出数的缺口 ===")
    print("  " + "、".join(p["missing_params"]))
