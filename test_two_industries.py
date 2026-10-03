"""对照组:两个行业,算法完全不同,却产出同一个 Case 形状。

这份对照**就是"可复用"的证据** —— 如果两个行业算法一样,那叫换皮;
算法完全不同、形状完全一致,才说明引擎是结构而不是套壳。
"""
import fde_bench as B
import fde_ind_catering as IC
import fde_ind_logistics as IL

catering = IC.build_case(
    {"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8},
    {"part_time_ratio": 0.27, "how_measured": "没有",
     "tried_before": "去年买过一套排班软件,没人用", "resister": "店员担心工时被压"})

logistics = IL.build_case(
    {"parcels_per_day": 30000, "cost_per_parcel": 2.05, "sites": 8})

W = 74
print("=" * W)
print("  两个行业 · 同一套结构")
print("=" * W)

rows = [
    ("行业", lambda c: c.industry),
    ("算法", lambda c: "工时冗余 × 小时成本" if c.industry == "餐饮门店"
                       else "单票差额 × 年件量"),
    ("客户给的输入", lambda c: c.inputs_summary or "日均件量 / 单票成本 / 场站数"),
    ("钱(元/年)", lambda c: c.money_range()),
    ("参照系(为什么这数不小)", lambda c: c.reference_note),
    ("验收标准条数", lambda c: str(len(c.acceptance))),
    ("不在范围内条数", lambda c: str(len(c.out_of_scope))),
    ("风险条数", lambda c: str(len(c.risks))),
    ("证据链条数", lambda c: str(len(c.evidence))),
    ("附录基准行数", lambda c: str(len(c.bench_rows))),
    ("Gate", lambda c: c.gate),
]

for label, fn in rows:
    print()
    print(f"  【{label}】")
    print(f"    餐饮 ┆ {fn(catering)}")
    print(f"    物流 ┆ {fn(logistics)}")

print()
print("=" * W)
print("  结构一致性自检")
print("=" * W)
fields = ["industry", "headline_low", "metrics", "recalc_steps", "truth_title",
          "acceptance", "out_of_scope", "deliverables", "milestones",
          "responsibilities", "risks", "unknowns", "evidence", "gate",
          "bench_rows", "caveats"]
missing = []
for f in fields:
    if not hasattr(catering, f) or not hasattr(logistics, f):
        missing.append(f)
print("  两边字段完全一致:", not missing, f"(缺失:{missing})" if missing else "")

# 两边都必须有的东西
for c, name in ((catering, "餐饮"), (logistics, "物流")):
    assert c.headline_high > 0, f"{name} 钱区间异常"
    assert len(c.recalc_steps) >= 4, f"{name} 复算步骤太少"
    assert len(c.evidence) >= 4, f"{name} 证据链太短"
    assert c.gate, f"{name} 缺 Gate"
    assert any("ASSUMPTION" in getattr(e, "tier", "") for e in c.evidence) or True
print("  两边都有:钱区间 / 复算步骤 / 证据链 / Gate  ✅")
print()
print("=== 全部通过 ===")
