"""赛前自检(联网时跑):物流示例材料 → 抽取 → 回指校验 → 只问该问的。

用途:现场演示前确认「丢材料 → 抽事实 → 只问该问的」这条链在物流口径下真的通,
以及示例材料确实留下 3 个必须当面问的问题(否则现场就没得演了)。
"""
import fde_ask
import fde_ind_logistics as L
import fde_intake as I
import fde_llm

fields = {i.key: i.label for i in L.INPUTS}
chat = fde_llm.chat if fde_llm.available() else None
print("模型可用:", bool(chat), "| 要抽的参数:", list(fields.values()))

pack = I.run(L.SAMPLE_MATERIAL, chat, fields)
v = pack["verify"]
print(f"回指校验: {v['ok']}/{v['total']} 通过(失败 {v['fail']})")
print("模型是否用了:", pack["model_used"], "| 错误:", pack["error"])

pl = fde_ask.plan(pack, topics=L.TOPICS, inputs=L.INPUTS)
print("\n" + pl["summary"])
print("已答(带原句):")
for a in pl["asked"]:
    print(f"  - {a['key']}: {(a['quote'] or '')[:40]}")
print("必问(按分):")
for a in pl["ask"]:
    print(f"  [{a['score']:>3}] {a['key']}  {a['question']}")
print("材料里抽到的参数:", {k: (vv or {}).get("value")
                            for k, vv in (pack["result"]["prefill"] or {}).items()})

print()
print("=== 离线演示用的预跑缓存(按行业存的那份) ===")
import fde_demo

cached = fde_demo.load(L.INDUSTRY)
if cached is None:
    print("还没有物流的预跑缓存 —— 先跑 python capture_demo.py 快递物流")
else:
    inf = fde_demo.info(L.INDUSTRY)
    print(f"捕捉于 {inf['captured_at']} · 事实 {inf['facts']} 条 · "
          f"回指 {inf['verify'].get('ok')}/{inf['verify'].get('total')}")
    plc = fde_ask.plan(cached, topics=L.TOPICS, inputs=L.INPUTS)
    print(plc["summary"])
    print("已答:", [a["key"] for a in plc["asked"]])
    print("必问:", [(a["key"], a["score"]) for a in plc["ask"]])
