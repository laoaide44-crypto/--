"""把物流这次诊断完整打出来,人眼审一遍。"""
import fde_ind_logistics as L

case = L.build_case({"parcels_per_day": 30000, "cost_per_parcel": 2.05, "sites": 8})

W = "=" * 66
print(W); print(f"  行业:{case.industry}"); print(W); print()

print("【钱】", case.headline_label)
print("   ", case.money_range())
print("    ", case.plain_line)
print()

print("【参照系 —— 让绝对值显得有分量】")
print("   ", case.reference_note)
print()

print("【界面指标】")
for m in case.metrics:
    print(f"    {m.label}: {m.value}" + (f"   ({m.delta})" if m.delta else ""))
print()

print("【② 真问题】")
print("   ", case.truth_title)
for line in case.truth_body.split("\n"):
    print("   ", line)
print()

print("【④ 验收标准 —— 必须能判真假】")
for i, (t, base, tier) in enumerate(case.acceptance, 1):
    print(f"    {i}. {t}")
    print(f"       基线:{base}   来源:{tier}")
print()

print("【⑤ 不在范围内】")
for x in case.out_of_scope:
    print("    -", x)
print()

print("【⑨ 风险】")
for r in case.risks:
    print(f"    - {r[0]}")
    print(f"      影响:{r[1]} / 应对:{r[2]}")
print()

print("【附录 A 证据链】")
for e in case.evidence:
    print(f"    {e.id}  [{e.tier}/{e.confidence}]  {e.conclusion}")
    print(f"         出处:{e.source}")
print()

print("【Gate 证据充分度】")
print("   ", case.gate)
print("    缺口:", case.gate_gap)
print()

print("【复算步骤 —— 客户自己按计算器核】")
for s in case.recalc_steps:
    print("   ", s)
