"""
离线演示模式 —— 把一次真实的「联网抽取」结果存下来,断网时加载它。

为什么要它:实测发现断网时作品不崩、也不编造事实,但抽取结果是**空的**,
现场演示会很难看。解决办法不是让 AI 假装能算,而是:

    联网时跑一份**真实结果**存下来 → 断网时加载它 → **并明确标注这是预跑的**。

诚实性约束(不能破):
  · 加载预跑结果时,界面上必须显著标注「演示模式」+ 捕捉时间 + 用的是哪份材料。
  · 契约附录里也要写明,不能让它变成一份"刚算出来的"证据。
"""

from __future__ import annotations

import dataclasses
import json
import os
import time

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo-cache.json")
SCHEMA = 1


def cache_path(industry: str | None = None) -> str:
    """预跑缓存按**行业**分开存。
    之前只有一个文件(餐饮材料),切到物流后离线演示会载入门店群聊的结果 ——
    与「行业感知」自相矛盾。现在:demo-cache-<行业>.json。"""
    if not industry:
        return CACHE
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f"demo-cache-{industry}.json")


def _jsonable(pack: dict) -> dict:
    """把 run() 的返回值变成可存 JSON 的结构。"""
    sc = pack.get("scan")
    return {
        "schema": SCHEMA,
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "material": pack.get("material", ""),
        "model_used": pack.get("model_used", False),
        "truncated": pack.get("truncated", False),
        "scan": dataclasses.asdict(sc) if sc is not None else None,
        "result": pack.get("result") or {},
        "verify": pack.get("verify") or {},
    }


def save(material: str, pack: dict, industry: str | None = None) -> str:
    data = _jsonable({**pack, "material": material})
    data["industry"] = industry          # _jsonable 只挑固定字段,行业标记在这里补上
    path = cache_path(industry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def info(industry: str | None = None) -> dict | None:
    """只读元信息,给界面判断用。"""
    path = cache_path(industry)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return {
            "captured_at": d.get("captured_at", "?"),
            "industry": d.get("industry"),
            "material_len": len(d.get("material") or ""),
            "facts": len((d.get("result") or {}).get("facts") or []),
            "verify": d.get("verify") or {},
        }
    except (OSError, json.JSONDecodeError):
        return None


def load(industry: str | None = None) -> dict | None:
    """加载预跑结果,还原成和 fde_intake.run() 一样形状的 pack。"""
    path = cache_path(industry)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    import fde_intake as I

    sc = None
    if d.get("scan"):
        try:
            sc = I.Scan(**d["scan"])
        except TypeError:
            sc = None

    return {
        "scan": sc,
        "result": d.get("result") or {},
        "verify": d.get("verify") or {},
        "model_used": True,          # 它确实是模型跑出来的,只是不是"刚才"
        "truncated": d.get("truncated", False),
        "error": None,
        "units": [],
        "demo": True,
        "demo_captured_at": d.get("captured_at", "?"),
        "demo_material": d.get("material", ""),
        "demo_industry": d.get("industry"),
    }


def demo_note(pack: dict) -> str:
    """给契约附录用的说明文字。"""
    if not pack.get("demo"):
        return ""
    return (
        f"\n> ⚠️ **本附录来自「演示模式」**:材料抽取结果捕捉于 "
        f"{pack.get('demo_captured_at', '?')}(联网环境下跑出的真实结果),"
        f"**不是本次现场实时计算的**。评审或甲方若需要实时结果,请在联网环境下重新运行。\n"
    )
