"""验证离线演示模式:缓存能加载、界面能渲染、契约里带诚实标注。

缓存**按行业分开**:餐饮 / 物流各一份,载入时必须和当前选的行业对得上。
"""
import fde_contract as C
import fde_demo
import fde_ind_catering as IC
import fde_ind_logistics as IL

print("=== 1) 缓存元信息(餐饮,按行业那份) ===")
info = fde_demo.info(IC.INDUSTRY)
if not info:
    print(f"没有「{IC.INDUSTRY}」的缓存,先跑 capture_demo.py")
    raise SystemExit(1)
print(f"  捕捉时间: {info['captured_at']}")
print(f"  行业标记: {info.get('industry')}")
assert info.get("industry") == IC.INDUSTRY, "餐饮缓存的行业标记不对"
print(f"  材料长度: {info['material_len']} 字")
print(f"  事实条数: {info['facts']}")
v = info.get("verify") or {}
print(f"  回指校验: {v.get('ok')}/{v.get('total')} 失败 {v.get('fail')}")

print()
print("=== 2) 加载成 pack ===")
pack = fde_demo.load(IC.INDUSTRY)
assert pack, "加载失败"
assert pack.get("demo") is True
assert pack.get("demo_captured_at")
assert pack.get("demo_industry") == IC.INDUSTRY
print(f"  demo 标记: {pack.get('demo')}")
print(f"  捕捉时间: {pack.get('demo_captured_at')}")
print(f"  行业标记: {pack.get('demo_industry')}")
print(f"  scan 还原: {pack['scan'] is not None}")
print(f"  facts: {len(pack['result'].get('facts') or [])} 条")
print(f"  prefill: {list((pack['result'].get('prefill') or {}).keys())}")

print()
print("=== 3) 契约里的诚实标注 ===")
case = IC.build_case({"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8},
                     {"part_time_ratio": 0.27})
md = C.render(case, {"who_does_it": "店长", "how_measured": "没有",
                     "resister": "店长", "tried_before": "软件"}, pack)
open("契约-草稿.md", "w", encoding="utf-8").write(md)
checks = {
    "含 演示模式": "演示模式" in md,
    "含 捕捉时间": pack["demo_captured_at"] in md,
    "含 不是本次现场实时计算": "不是本次现场实时计算" in md,
    "含 附录 F": "附录 F" in md,
}
for k, ok in checks.items():
    print(f"  {k}: {ok}")
assert all(checks.values()), "标注不完整"

print()
print("=== 4) 界面能否渲染(演示模式) ===")
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=60)
at.run()
if at.exception:
    print("  FAIL 初始:", at.exception)
    raise SystemExit(1)
at.session_state["screen"] = "intake"
at.session_state["intake"] = pack
at.run()
if at.exception:
    print("  FAIL 演示模式:", at.exception)
    raise SystemExit(1)
print("  OK 丢材料页 + 演示包 渲染无异常")

print()
print("=== 5) 物流那份缓存也对得上(主场景) ===")
linfo = fde_demo.info(IL.INDUSTRY)
if not linfo:
    print("  没有物流缓存 —— 先跑:python capture_demo.py 快递物流")
else:
    lpack = fde_demo.load(IL.INDUSTRY)
    assert lpack and lpack.get("demo_industry") == IL.INDUSTRY
    assert "排班" not in (lpack.get("demo_material") or ""), "物流缓存里混进了餐饮材料"
    assert any("单票" in (f.get("text") or "") or "派费" in (f.get("text") or "")
               for f in lpack["result"]["facts"]), "物流缓存的事实不像物流的"
    print(f"  ✅ 物流缓存 {linfo['facts']} 条事实,行业标记 {linfo.get('industry')}")

print()
print("=== 全部通过 ===")
