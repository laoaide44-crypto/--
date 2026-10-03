"""界面外壳也必须行业感知:示例材料 / 追问清单 / 讨数据那句 / 提问计划 / 缺口参数。

背景:这三样原来写死在 app.py 里(全局唯一一份、餐饮口径)——
切到快递物流时,示例材料还是门店群聊、追问还在问排班,与「行业感知」自相矛盾。
"""
import fde_ask
import fde_bench as B
import fde_ind_catering as IC
import fde_ind_logistics as IL
from streamlit.testing.v1 import AppTest


def fake_pack(lines):
    """把每行当成一条已回指通过的事实 —— 模拟「模型把这几句抽出来了」。"""
    facts = [{"text": x, "quote": x, "quote_ok": True, "level": "DIRECT"}
             for x in lines]
    return {"result": {"facts": facts, "prefill": {}}}


print("=== 0) 注册表 / 基准库 / MODEL_READY 三者对得上 ===")
import fde_registry as REG

_REQUIRED = ("INPUTS", "HERO", "SAMPLE_MATERIAL", "SAMPLE_CAPTION",
             "QUESTIONS", "TOPICS", "INTERNAL_ASK")
for _name, _mod in REG.MODULES.items():
    assert _name in B.industries(), f"{_name} 不在基准库里"
    assert B.MODEL_READY.get(_name) is True, f"{_name} 有模块,但 MODEL_READY 不是 True"
    for _attr in _REQUIRED:
        assert hasattr(_mod, _attr), f"{_name} 缺 {_attr}"
    assert callable(getattr(_mod, "build_case", None)), f"{_name} 缺 build_case"
for _name, _ready in B.MODEL_READY.items():
    if _ready:
        assert _name in REG.MODULES, f"{_name} 标了模型就绪,但注册表里没有模块"
print(f"  行业 {list(REG.MODULES)} · 与 MODEL_READY 一致 ✅")

print()
print("=== 1) 每个行业自己带示例材料 / 追问清单 / 讨数据那句 ===")
B.select_industry("快递物流")
assert "单票" in IL.SAMPLE_MATERIAL and "派费" in IL.SAMPLE_MATERIAL
assert "排班" not in IL.SAMPLE_MATERIAL, "物流的示例材料里还有排班"
assert "网点群聊" in IL.SAMPLE_CAPTION
assert "近 30 天" in IL.INTERNAL_ASK
_qs = " ".join(q[1] + q[2] for q in IL.QUESTIONS)
assert "排班" not in _qs and "兼职" not in _qs, "物流的追问清单串了餐饮"
assert any("单票成本" in q[1] for q in IL.QUESTIONS)
assert all(k != "part_time_ratio" for k, *_ in IL.QUESTIONS), "物流不该问兼职占比"
print("  物流 OK:", IL.SAMPLE_CAPTION, "|", IL.INTERNAL_ASK)

B.select_industry("餐饮门店")
assert "排班" in IC.SAMPLE_MATERIAL and "门店群聊" in IC.SAMPLE_CAPTION
assert "近 8 周" in IC.INTERNAL_ASK
assert not any("单票" in q[1] for q in IC.QUESTIONS), "餐饮的追问清单串了物流"
print("  餐饮 OK:", IC.SAMPLE_CAPTION, "|", IC.INTERNAL_ASK)

print()
print("=== 2) 提问计划由行业话题库驱动(不是全局一份) ===")
pack = fake_pack([
    "这个月对账又对到现在,我一个人拉了三天表",
    "就怕又跟去年一样,从派费里往下抠",
])
pl = fde_ask.plan(pack, topics=IL.TOPICS, inputs=IL.INPUTS)
keys = [a["key"] for a in pl["ask"]]
print("  物流 已答:", [a["key"] for a in pl["asked"]])
print("  物流 必问(按分):", keys)
assert keys[0] == "cost_basis", f"物流第一问应该是成本口径,实际:{keys}"
assert "part_time_ratio" not in keys, "物流还在问兼职占比"
assert set(keys) >= {"cost_basis", "how_measured", "internal_data", "tried_before"}
assert pl["missing_params"] == ["日均件量", "你的单票综合成本", "网点 / 分拨场站数"], \
    pl["missing_params"]

pl_c = fde_ask.plan(fake_pack([]))
assert pl_c["ask"][0]["key"] == "part_time_ratio", pl_c["ask"][0]["key"]
assert pl_c["missing_params"] == ["门店数", "单店月流水", "单店员工数"]
print("  餐饮默认第一问:", pl_c["ask"][0]["key"], "| 缺口:", pl_c["missing_params"])

print()
print("=== 3) 界面:切到物流点「用示例材料」,给的是物流的材料 ===")
B.select_industry("快递物流")
at = AppTest.from_file("app.py", default_timeout=60).run()
assert not list(at.exception), at.exception
next(b for b in at.button if b.label == "丢一份材料进来 →").click().run()
at.radio[0].set_value("用示例材料").run()
assert not list(at.exception), at.exception
caps = " ".join(c.value for c in at.caption)
assert "网点群聊" in caps and "门店群聊" not in caps, caps
_blocks = getattr(at, "code", None)
if _blocks:
    _code = " ".join(c.value for c in _blocks)
    assert "单票" in _code or "派费" in _code, "示例材料正文还是餐饮的"
print("  ✅ 示例材料跟着行业变了")

print()
print("=== 全部通过:外壳、清单、计划、缺口参数都随行业走 ===")
