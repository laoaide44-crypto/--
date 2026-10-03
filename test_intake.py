"""端到端测一次真实抽取:模型 + 回指校验。"""
import json

import fde_intake as I
import fde_llm

SAMPLE = """王店长
2026年09月18日 09:12
我真排不过来了,12 家店的班表我一个人弄

李主管
2026年09月18日 09:15
你一周要花多久在这上面

王店长
2026年09月18日 09:16
至少一天吧,周一基本干不了别的

李主管
2026年09月18日 09:20
总部现在也没个准数,每家店到底排得合不合理看不出来

王店长
2026年09月18日 09:22
而且排完了店员老来问为什么这么排,我也说不出个所以然,只能重改

店员小张
2026年09月18日 12:40
店长我这个周末能不能不排晚班啊

王店长
2026年09月18日 12:41
我先看看

李主管
2026年09月18日 14:02
我们去年买过一套排班软件,没人用,最后就放着

王店长
2026年09月18日 14:05
主要是那个排出来的班我看不懂它为啥这么排

李主管
2026年09月18日 14:10
单店月流水差不多 30 万左右,一家店八个人

李主管
2026年09月18日 14:12
兼职现在很少,基本上都是全职

王店长
2026年09月18日 15:30
还有人说怕以后工时被压
"""

print("模型可用:", fde_llm.available())
print("开始抽取…\n")
pack = I.run(SAMPLE, fde_llm.chat if fde_llm.available() else None)

sc, verif, res = pack["scan"], pack["verify"], pack["result"]
print(f"材料:{sc.n_chars} 字 → {sc.n_units} 个单元")
print(f"扫到金额:{sc.money}")
print(f"扫到百分比:{sc.percents}")
print(f"模型是否用了:{pack['model_used']}  错误:{pack['error']}")
print(f"回指校验:{verif['ok']}/{verif['total']} 通过,{verif['fail']} 条失败")
for p, q in verif["details"]:
    print(f"   ✗ {p} → 「{q}」")
print()

print("—— 事实清单 ——")
for f in res.get("facts") or []:
    lv = I.LEVEL_LABEL.get(f.get("level"), f.get("level"))
    ok = "" if f.get("quote_ok", True) else "  ⚠无法回指"
    print(f"[{f.get('kind','')}/{lv}]{ok} {f.get('text','')}")
    print(f"    原文:「{f.get('quote','')}」")
print()

print("—— 矛盾 ——")
for c in res.get("conflicts") or []:
    print(f"  {c.get('a')} ↔ {c.get('b')}  ({c.get('why')})")
print()

print("—— 未知项 ——")
for u in res.get("unknowns") or []:
    print(f"  [{u.get('how_to_get')}] {u.get('what')} —— {u.get('why_needed')}")
print()

print("—— prefill ——")
print(json.dumps(res.get("prefill") or {}, ensure_ascii=False, indent=2))
