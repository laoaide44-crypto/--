"""联网时跑一份真实抽取结果,存成离线演示用的缓存(**按行业分开**)。

用法:
    python capture_demo.py              # 两个行业都捕捉
    python capture_demo.py 快递物流      # 只捕捉指定行业

前提:  .env.local 里的模型可用(它会检查)。

为什么要按行业分:现场主场景是快递物流,如果离线演示载入的是门店群聊的预跑结果,
「行业感知」当场就自相矛盾了。
"""

import sys

import fde_demo
import fde_ind_catering as IC
import fde_ind_logistics as IL
import fde_intake as I
import fde_llm

MODULES = {m.INDUSTRY: m for m in (IL, IC)}


def capture(mod) -> bool:
    material = mod.SAMPLE_MATERIAL
    fields = {i.key: i.label for i in mod.INPUTS}
    print(f"--- {mod.INDUSTRY}:材料 {len(material)} 字 · 要抽 {list(fields.values())}")
    print("    真实抽取中(联网,约 10–60 秒)…")
    pack = I.run(material, fde_llm.chat, fields)

    if not pack.get("model_used"):
        print(f"    ❌ 抽取失败,不写缓存。错误: {pack.get('error')}")
        return False

    v = pack["verify"]
    print(f"    回指校验: {v.get('ok')}/{v.get('total')} 通过,失败 {v.get('fail')}")
    print(f"    抽出事实: {len((pack.get('result') or {}).get('facts') or [])} 条")

    path = fde_demo.save(material, pack, mod.INDUSTRY)
    info = fde_demo.info(mod.INDUSTRY)
    print(f"    ✅ 已写入: {path}")
    print(f"       捕捉时间 {info['captured_at']} · 事实 {info['facts']} 条")
    return True


def main() -> int:
    if not fde_llm.available():
        print("模型不可用(.env.local 没配或读不到)—— 无法捕捉真实结果。")
        return 1

    want = sys.argv[1:] or list(MODULES)
    unknown = [w for w in want if w not in MODULES]
    if unknown:
        print(f"未知行业:{unknown};可选:{list(MODULES)}")
        return 1
    ok = all([capture(MODULES[w]) for w in want])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
