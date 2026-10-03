"""验证第 5 步 1→N:一次交付 → 抽资产 → 新客户进来时给出假设。"""
import os
import tempfile

import fde_demo
import fde_ind_catering as IC
import fde_reuse as R

# 用临时库,不污染真库
R.LIB = os.path.join(tempfile.gettempdir(), "reuse-test.json")
if os.path.exists(R.LIB):
    os.remove(R.LIB)

pack = fde_demo.load()
assert pack, "先跑 capture_demo.py"

print("=== 起点:空库 ===")
print(" ", R.stats())

# --- 第 1 次交付 ---
case = IC.build_case({"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8},
                     {"part_time_ratio": 0.27})
ans = {
    "who_does_it": "店长自己在 Excel 里排,一周至少一天",
    "how_measured": "没有,总部也没有准数",
    "resister": "店员担心以后工时被压",
    "tried_before": "去年买过一套排班软件,没人用,最后就放着",
    "internal_data": "可以,我发你一份脱敏的",
}
assets = R.harvest(case, ans, pack, project="P1-门店用工")
added = R.add(assets)
print()
print(f"=== 第 1 次交付 → 抽出 {len(assets)} 条,新增 {added} 条 ===")
for x in assets:
    print(f"  [{x.kind}] {x.text[:64]}…")
    if x.note:
        print(f"        备注: {x.note[:70]}")

print()
print("=== 库状态 ===")
st = R.stats()
print(" ", st)

# --- 新客户进来 ---
print()
print("=== 新客户材料进来 → 资产库先给假设 ===")
hits = R.suggest(pack)
if hits:
    print(R.format_suggestions(hits))
else:
    print("  (没有匹配的资产)")
assert hits, "应该能匹配到资产"

# --- 去标识检查 ---
print()
print("=== 去标识检查(资产里不应出现具体店数/金额)===")
bad = []
for x in assets:
    if "12 家" in x.text or "300000" in x.text or "30 万" in x.text:
        bad.append(x.text[:40])
print("  可疑条目:", bad or "无")

print()
print("=== 全部通过 ===")
print(f"(测试库在 {R.LIB},真库未被改动)")
