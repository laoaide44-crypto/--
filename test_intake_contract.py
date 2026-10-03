"""端到端:材料 → 抽取 → 回指校验 → 契约(含附录 F)。"""
import fde_contract as C
import fde_ind_catering as IC
import fde_intake as I
import fde_llm

# 示例材料现在由**行业模块自己带**(原来写死在 app.py 的全局一份里)
sample = IC.SAMPLE_MATERIAL

print("模型可用:", fde_llm.available())
pack = I.run(sample, fde_llm.chat if fde_llm.available() else None)
print(f"回指校验: {pack['verify']['ok']}/{pack['verify']['total']}  失败 {pack['verify']['fail']}")

case = IC.build_case({"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8},
                     {"part_time_ratio": 0.27})
md = C.render(case, {
    "who_does_it": "店长自己在 Excel 里排",
    "how_measured": "没有",
    "resister": "店长担心失去裁量权",
    "tried_before": "买过一套排班软件,没人用",
}, pack)

open("契约-草稿.md", "w", encoding="utf-8").write(md)
print("契约字符数:", len(md))
for k in ("附录 F", "参数从哪句话来", "引用定位", "矛盾的地方", "F.4", "原句"):
    print(f"  含「{k}」: {k in md}")

# 打印附录 F 开头几行,人眼确认格式
i = md.find("# 附录 F")
print("\n---- 附录 F 预览 ----")
print(md[i:i + 1200])
