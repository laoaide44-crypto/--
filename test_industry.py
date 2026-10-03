"""验证行业层:数据能切、模型没写就明确报错(而不是算出个假的数)。"""
import fde_bench as B
import fde_model as M

print("=== 1) 行业清单 ===")
for name in B.industries():
    n = len(B.INDUSTRIES[name])
    ready = "模型已写" if B.model_ready(name) else "只有数据"
    print(f"  {name}:  {n} 条基准   [{ready}]")

print()
print("=== 2) 餐饮:正常算 ===")
B.select_industry("餐饮门店")
a = M.analyze(12, 300000, 8, 0.27)
print(f"  当前行业: {B.current()}   基准条数: {len(B.BENCH)}")
print(f"  年漏损区间: {M.money(a.struct_money_low)} – {M.money(a.struct_money_high)}")

print()
print("=== 3) 临时把物流设为「没有模型」,验证闸门 ===")
B.MODEL_READY["快递物流"] = False
B.select_industry("快递物流")
print(f"  当前行业: {B.current()}   基准条数: {len(B.BENCH)}")
print(f"  分组: {B.groups()}")
try:
    M.analyze(5, 1000000, 20)
    print("  ❌ 意外:居然算出来了 —— 这说明闸门失效")
    raise SystemExit(1)
except M.NoModelForIndustry as e:
    print("  ✅ 正确报错,没有拿餐饮公式硬套:")
    for line in str(e).split("\n"):
        print("     " + line)
finally:
    B.MODEL_READY["快递物流"] = True          # 恢复

print()
print("=== 4) 切回餐饮:还能正常算 ===")
B.select_industry("餐饮门店")
a2 = M.analyze(12, 300000, 8, None)
print(f"  当前行业: {B.current()}   年漏损区间: {M.money(a2.struct_money_low)} – {M.money(a2.struct_money_high)}")
assert a2.total_hours > 0

print()
print("=== 5) 停在物流时,餐饮模型照样算得对(不受全局选择影响)===")
B.select_industry("快递物流")
a3 = M.analyze(12, 300000, 8, 0.27, industry="餐饮门店")
print(f"  当前全局行业: {B.current()}  餐饮模型算出: {M.money(a3.struct_money_low)} – {M.money(a3.struct_money_high)}")
assert a3.struct_money_low > 0
B.select_industry("餐饮门店")

print()
print("=== 全部通过 ===")
