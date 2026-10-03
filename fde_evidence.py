"""
补证据,改决策 —— 让新证据真正改变问题判断、测算与试点范围。

两种情形都用**明确标注的合成演示材料**,而且:
  · 结论**不是硬编码的** —— 情景只提供「结构化证据(参数 + 标志)」,
    问题判断、收益重算、试点范围都由现有规则与计算链**重新算出来**。
  · 每个变化都要能说出**依据**(来自哪条事实 / 哪条规则)。

情景一:实际数据表明用工优化空间有限,但排班返工明显
        → 缩小收益判断,转向排班解释与返工试点
情景二:实际数据支持部分时段存在冗余
        → 保留优化假设,推进单店验证,并列出服务质量等约束
"""

from __future__ import annotations

SYNTHETIC = True
SYNTHETIC_NOTE = "⚠️ 合成演示材料(非真实客户数据),仅用于演示「补证据 → 改决策」这条链路。"

SCENARIOS: dict[str, dict] = {
    "S1": {
        "label": "情景一 · 用工优化空间有限,排班返工明显",
        "material": (
            "【合成演示材料 · 情景一】\n\n"
            "运营周报(节选,脱敏)\n"
            "· 工作日排班这块,周末和节假日基本靠兼职顶,现在兼职 / 小时工占比已经 62%\n"
            "· 王店长每周排班返工 4 次以上,每次都因为店员来问「为什么这么排」\n"
            "· 近 4 周复核:没有发现明显的时段冗余,忙时人手上得比较准\n"
        ),
        "params": {"part_time_ratio": 0.62},
        "flags": {"no_space": True, "rework_supported": True},
    },
    "S2": {
        "label": "情景二 · 实际数据支持部分时段存在冗余",
        "material": (
            "【合成演示材料 · 情景二】\n\n"
            "排班表抽样(脱敏)\n"
            "· 午市 11:00–14:00 排了 6 人,同期客流只需要 4 人 —— 存在冗余\n"
            "· 晚市 17:00–21:00 排 8 人,与客流基本吻合\n"
            "· 兼职 / 小时工占比 18%,可替代空间还比较大\n"
        ),
        "params": {"part_time_ratio": 0.18},
        "flags": {"redundancy_supported": True},
    },
    "S3": {
        "label": "情景三 · 午市冗余与返工并存(验收新增案例)",
        "material": (
            "【合成演示材料 · 情景三(验收新增案例)】\n\n"
            "复盘纪要(节选,脱敏)\n"
            "· 午市 11:00–14:00 排 10 人,客流只需 7 人 —— 存在冗余\n"
            "· 店长每周重改班表 3 次以上,需求一变就要重新解释为什么这么排\n"
            "· 兼职 / 小时工占比 45%,接近一半\n"
        ),
        "params": {"part_time_ratio": 0.45},
        "flags": {"redundancy_supported": True, "rework_supported": True},
    },
}

import re

_PCT = re.compile(r"(\d{1,3})\s*%")
_REDUND = ("冗余", "只需要", "多排", "多了")
_NEG_STRONG = ("没有发现", "没有明显", "未发现", "没发现", "不存在")
_REWORK = ("返工", "重改", "为什么这么排", "来问")


def parse_material(text: str) -> dict:
    """确定性解析合成材料 → 结构化证据。不交给模型。

    ⚠️ 按行判定、且**先看否定** —— 「没有发现明显的时段冗余」里出现了
    「冗余」二字,但它表达的是「空间有限」,不能判成「冗余成立」。
    (不这样写,两个演示情景会解析出同一组标志,演示就成了摆样子。)
    """
    out: dict = {"params": {}, "flags": {}, "clues": []}
    m = _PCT.search(text)
    if m:
        out["params"]["part_time_ratio"] = int(m.group(1)) / 100.0
    for raw in text.splitlines():
        s = raw.strip(" ·\t")
        if not s:
            continue
        hit = False
        if any(k in s for k in _NEG_STRONG) and any(
                k in s for k in _REDUND + ("冗余",)):
            out["flags"]["no_space"] = True
            hit = True
        elif any(k in s for k in _REDUND):
            out["flags"]["redundancy_supported"] = True
            hit = True
        if any(k in s for k in _REWORK):
            out["flags"]["rework_supported"] = True
            hit = True
        if hit:
            out["clues"].append(s)
    return out


def update_facts(key: str, parsed: dict) -> list[dict]:
    """把合成的结构化证据转成「统一事实记录」形状(带稳定 ID)。"""
    sc = SCENARIOS[key]
    out = []
    for i, c in enumerate(parsed.get("clues", []), 1):
        out.append({
            "id": f"U{i}", "kind": "补充证据", "text": c, "quote": c,
            "locator": f"{sc['label']} · 合成材料", "source_type": "内部数据(合成)",
            "status": "已实测", "quote_ok": True, "support_status": "完全支持",
            "apply_status": "已适用实测", "confirmed": True,
            "note": SYNTHETIC_NOTE,
        })
    return out


def apply_update(key: str, base_inputs: dict, base_ans: dict,
                 build_case, industry: str, extra_facts=None,
                 base_flags=None, state=None,
                 strip_fact_ids=None, strip_flag_keys=None) -> dict:
    """应用一次证据补充,并对比前后,产出「变化报告」。

    build_case(inputs, ans, facts=..., flags=..., state=...) 由行业模块提供 ——
    这样结论走的是现有计算链,不是为演示写死。

    extra_facts / base_flags / state:当前流程已经积累的上下文 ——「之前」和「之后」
    都在**完整上下文**里算,否则变化报告会把「早就成立的结论」误报成「这次新变的」。"""
    sc = SCENARIOS[key]
    parsed = parse_material(sc["material"])
    # 情景自带的参数/标志与从材料解析出来的合并(材料解析优先,情景兜底)
    params = {**sc.get("params", {}), **parsed["params"]}
    flags = {**sc.get("flags", {}), **parsed["flags"]}

    new_inputs = dict(base_inputs)
    new_ans = dict(base_ans)
    for k, v in params.items():
        new_ans[k] = v

    _extra = list(extra_facts or [])
    _bflags = dict(base_flags or {})
    _state = dict(state or {})
    # 情景切换 = 替换:先把旧情景的产物剔除,避免不同情景的数据混用
    _strip_ids = set(strip_fact_ids or [])
    _extra_after = []
    for f in _extra:
        _fid = f.get("id") if isinstance(f, dict) else getattr(f, "id", None)
        if _fid in _strip_ids:
            continue
        _extra_after.append(f)
    _strip_keys = set(strip_flag_keys or [])
    _bflags_after = {k: v for k, v in _bflags.items() if k not in _strip_keys}
    before = build_case(base_inputs, base_ans, facts=_extra, flags=_bflags, state=_state)
    after = build_case(new_inputs, new_ans,
                       facts=_extra_after + update_facts(key, parsed),
                       flags={**_bflags_after, **flags}, state=_state)

    report: list[dict] = []
    invalidated: list[str] = []
    recalced: list[str] = []

    # 1) 参数变化
    for k, v in params.items():
        old = base_ans.get(k)
        old_s = f"{float(old):.0%}" if isinstance(old, (int, float)) else "未取得"
        new_s = f"{float(v):.0%}" if k == "part_time_ratio" else str(v)
        report.append({"what": f"参数:{k}", "before": old_s, "after": new_s,
                       "basis": f"{sc['label']} · 合成材料"})

    # 2) 收益:工时与现金分开比
    if abs(before.hours_release_high - after.hours_release_high) > 1e-9 or \
       abs(before.hours_release_low - after.hours_release_low) > 1e-9:
        _aft_hrs = ("0(已停止:反向证据支持无可释放工时)"
                    if getattr(after, "revenue_stopped", False)
                    else f"{after.hours_release_low:,.0f}–{after.hours_release_high:,.0f} 工时/月")
        recalced.append(
            f"可释放工时 {before.hours_release_low:,.0f}–{before.hours_release_high:,.0f} "
            f"→ {_aft_hrs}")
        recalced.append(
            f"假设情景下的潜在优化空间(现金口径) "
            f"{before.money_range()} → {after.money_range()}")
        invalidated.append(
            "旧的可释放工时与现金口径结论作废(参数已变)"
            + (";且反向证据支持无可释放工时,该改造建议已停止"
               if getattr(after, "revenue_stopped", False) else ""))

    # 3) 候选问题状态 / 判断依据变化
    bmap = {c["key"]: c for c in before.candidates}
    amap = {c["key"]: c for c in after.candidates}
    for k in amap:
        if k in bmap and bmap[k]["status"] != amap[k]["status"]:
            report.append({
                "what": f"候选问题 {k}({amap[k]['title']})",
                "before": bmap[k]["status"], "after": amap[k]["status"],
                "basis": amap[k]["reason"]})
        elif k in bmap and bmap[k].get("reason") != amap[k].get("reason"):
            report.append({
                "what": f"候选问题 {k}({amap[k]['title']})·判断依据",
                "before": bmap[k].get("reason", ""),
                "after": amap[k].get("reason", ""),
                "basis": "新证据改变了判断依据(状态未变)"})

    # 4) 试点范围变化
    if before.pilot_scope != after.pilot_scope:
        report.append({"what": "试点范围", "before": before.pilot_scope or "未定",
                       "after": after.pilot_scope,
                       "basis": "由候选问题状态与证据门槛重新计算"})

    # 5) 哪些仍然不确定
    still = []
    for c in after.candidates:
        still += [f"{c['key']} · {u}" for u in c.get("unknowns", [])]
    still = still[:6]

    return {
        "scenario": key,
        "label": sc["label"],
        "material": sc["material"],
        "synthetic": SYNTHETIC,
        "note": SYNTHETIC_NOTE,
        "new_inputs": new_inputs,
        "new_ans": new_ans,
        "facts": update_facts(key, parsed),
        "flags": flags,
        "parsed": parsed,
        "before": before,
        "after": after,
        "report": report,
        "invalidated": invalidated,
        "recalced": recalced,
        "pilot_scope": after.pilot_scope,
        "unknowns": still,
    }
