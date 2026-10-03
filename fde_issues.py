"""
候选问题 —— **不预设**客户的问题一定是用工结构。

以前的行为:页面算出人时营业额 216 元(高于 180 元标杆),产品**仍然**下结论
「漏损在用人的结构上」。这是把一个待验证假设当成了既定事实。

现在:候选问题以列表出现,每条都带:
  支持证据 / 反向证据 / 未知项 / 建议验证动作 / 当前状态

状态可以是「暂不建议进行该改造」—— 没有充分证据时,允许输出「停」。
指标高于标杆**既不能证明没有优化空间,也不能反推存在结构性漏损**。

结论键(和 fde_facts.supports 对齐):
  A.rework    —— 排班耗时 / 解释困难 / 返工
  B.structure —— 用工结构可能存在优化空间
"""

from __future__ import annotations

import re

# 候选状态
S_SUPPORTED = "材料直接支持 · 建议进入试点设计"
S_VERIFY = "需客户数据验证"
S_WEAK = "证据不足 · 暂不建议进行该改造"
S_REJECTED = "已被客户否定"
S_COUNTER = "存在反向证据,需核实"                 # 客户陈述级反向证据(未附数据)
S_STOP = "数据支持无可释放工时 · 停止该改造建议"    # 数据级反向证据 → 计算归零、建议停止

# 反向证据的层级 —— 按来源分,不能把一句话直接升级成「已实测」
LV_STMT = "客户陈述"
LV_DATA = "内部数据支持"
LV_PILOT = "实际试点验证"

CLOSURE_A = "排班耗时、解释困难与返工"
CLOSURE_B = "用工结构可能存在优化空间"

# 事实 → 结论键(供 fde_facts.build 计算 supports;与候选 closure 对齐)
SUPPORTS = {
    "排班": "A.rework", "班表": "A.rework", "返工": "A.rework",
    "重改": "A.rework", "解释": "A.rework", "为什么这么排": "A.rework",
    "兼职": "B.structure", "小时工": "B.structure", "用工": "B.structure",
    "全职": "B.structure", "工时": "B.structure",
}

# 支撑 A 的关键词(确定性归位)
_A_KW = ("排班", "班表", "排不过来", "重改", "解释", "凭什么", "为什么这么排",
         "看不懂", "排得合不合理", "看不出", "没个准数")
# 明确「没问题」的相反表述:命中就不算支持(保守处理),并且单独提示
_A_NEG = ("没有返工", "基本没有返工", "没返工", "不返工", "没有重改", "不重改",
          "不来问", "没来问", "挺顺", "没出过什么问题", "没什么问题", "没有异常")
# 支撑 B 的关键词
_B_KW = ("兼职", "小时工", "全职", "用工", "人力", "工时")


def _ids_for(facts, kws, neg=()) -> list[str]:
    """Fact 对象或 dict 都能吃 —— 返回命中的事实 ID。neg 命中的视为相反表述,不算支持。"""
    hit, seen = [], set()
    for f in facts:
        if isinstance(f, dict):
            text, quote, fid = f.get("text") or "", f.get("quote") or "", f.get("id") or ""
        else:
            text, quote, fid = f.text or "", f.quote or "", f.id
        blob = text + quote
        if any(k in blob for k in kws) and fid not in seen:
            if neg and any(n in blob for n in neg):
                continue
            hit.append(fid)
            seen.add(fid)
    return hit


# ---------------------------------------------------------------- B 的反向证据
# 「没有冗余」这类表述必须进入决策依据,并按**证据层级**区分:
#   客户陈述 < 内部数据支持 < 实际试点验证(不能把一句话直接升级)
_B_REDUND = ("冗余", "多排", "富余", "多余")
_B_TIGHT = ("人手挺紧", "人手紧", "人手比较紧", "人手紧张", "人手不够", "人手不太够")
_B_NEG_RX = re.compile(r"没有|没发现|没多|不存在|不存|未发现|未出现|未见|无冗余|无多余|无富余|不会多")


def _split_clauses(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[，,。;；、！!?？\n]", s or "") if x.strip()]


def b_counter_evidence(facts) -> list[dict]:
    """识别「没有冗余 / 不存在多排 / 人手紧」类表述 → 候选 B 的反向证据。

    确定性规则(不交给模型);返回 [{fact_id, quote, hit, level, synthetic, locator}]:
      · level ∈ 客户陈述 / 内部数据支持 / 实际试点验证 —— 按来源分,不由措辞升级
    """
    out, seen = [], set()
    for f in facts:
        if isinstance(f, dict):
            text, quote = f.get("text") or "", f.get("quote") or ""
            fid, src = f.get("id") or "", f.get("source_type") or ""
            loc = f.get("locator") or ""
        else:
            text, quote = f.text or "", f.quote or ""
            fid, src = f.id, f.source_type or ""
            loc = f.locator or ""
        if not fid or fid in seen:
            continue
        clauses = _split_clauses(text) + _split_clauses(quote)
        hits_red = [c for c in clauses
                    if any(k in c for k in _B_REDUND) and _B_NEG_RX.search(c)]
        hits_tight = [c for c in clauses if any(k in c for k in _B_TIGHT)]
        hit = (hits_red or hits_tight or [None])[0]
        if not hit:
            continue
        if "试点" in src and "验证" in src:
            level = LV_PILOT
        elif "内部数据" in src:
            level = LV_DATA
        else:
            level = LV_STMT
        out.append({"fact_id": fid, "quote": quote or text, "hit": hit,
                    "level": level, "synthetic": "合成" in src, "locator": loc})
        seen.add(fid)
    return out


def catering_candidates(a, facts, ans=None, flags=None) -> list[dict]:
    """餐饮门店的候选问题。a = fde_model.Analysis;flags 由证据更新带来。
    **不含任何硬编码结论** —— 状态由事实与算术决定。"""
    ans = ans or {}
    flags = flags or {}
    target = None
    eff = getattr(a, "rev_per_hour", 0.0)
    try:
        from fde_model import BENCH
        target = BENCH["rev_per_hour_target"].value
    except Exception:
        target = 180.0

    support_a = _ids_for(facts, _A_KW, neg=_A_NEG)
    support_b = _ids_for(facts, _B_KW)
    # 材料里与 A 相反的表述(如「基本没有返工」)单独列出,不当作支持证据
    _neg_a = []
    for f in facts:
        if isinstance(f, dict):
            blob = (f.get("text") or "") + (f.get("quote") or "")
            q = f.get("quote") or ""
        else:
            blob = (f.text or "") + (f.quote or "")
            q = f.quote or ""
        if q and any(k in blob for k in _A_KW) and any(n in blob for n in _A_NEG):
            _neg_a.append(q)

    # ---- A:材料直接支持 ----
    a_status = S_SUPPORTED if support_a else S_WEAK
    cand_a = {
        "key": "A", "closure": "A.rework", "kind": "材料直接支持",
        "title": CLOSURE_A,
        "claim": "排班这件事本身在耗时、解释和返工上已经有明确代价,且材料直接支持。",
        "support": support_a,
        "counter": [f"材料里有相反表述:「{q[:48]}」—— 按保守处理,不作为支持证据;需当面核实"
                    for q in _neg_a[:2]],
        "unknowns": ["各门店班次结构是否一致",
                     "排班实际耗时是否留下过记录(现在只有「至少一天」的转述)"],
        "verify": ["让承担排班的人完整记录一次排班过程耗时",
                   "收集店员对排班理由的典型疑问(用于设计「可解释」输出)"],
        "status": a_status,
        "reason": ("材料里有直接支持的原句" if support_a
                   else "材料没有给出直接支持的原句 —— 只能作为待确认项"),
    }
    if flags.get("rejected_A"):
        cand_a["status"] = S_REJECTED
        cand_a["reason"] = "客户已明确否定这条判断 —— 保留展示,不再推进。"
    if flags.get("note_A"):
        cand_a["note"] = str(flags["note_A"])

    # ---- B:需客户数据验证 ----
    premise_weak = (target is not None and eff and eff >= target)
    redundancy = bool(flags.get("redundancy_supported"))
    no_space = bool(flags.get("no_space"))
    neg_ev = b_counter_evidence(facts)
    neg_data = [e for e in neg_ev if e["level"] != LV_STMT]
    neg_stmt = [e for e in neg_ev if e["level"] == LV_STMT]
    counter = []
    if premise_weak:
        counter.append(
            f"人时营业额 {eff:,.0f} 元/小时 ≥ 公开标杆 {target:.0f} 元/小时 —— "
            f"这只说明**人效不低**,既不能证明没有优化空间,也不能反推存在结构性漏损。")
    counter.append("公开的「198→137 工时」是**别人的店**在特定条件下的结果,不是本客户的实测。")
    # 「没有冗余」类反向证据 —— 进入决策依据,带出处、带层级(不靠措辞)
    for _e in neg_ev:
        _lv = _e["level"] + ("(合成演示)" if _e["synthetic"] else "")
        if _e["level"] == LV_STMT:
            counter.append(
                f"〔{_lv} · {_e['fact_id']}〕「{_e['hit']}」—— "
                f"仅是客户说法,尚未附原始数据;核实前不作为「无可释放工时」的结论,也不推进该改造。")
        else:
            counter.append(
                f"〔{_lv} · {_e['fact_id']}〕「{_e['hit']}」—— "
                f"数据支持「无可释放工时」,该改造建议停止。")

    if neg_data:
        b_status = S_STOP
        _e0 = neg_data[0]
        b_reason = (f"补充数据支持「无可释放工时」(反向证据〔{_e0['fact_id']}〕)—— "
                    f"该改造建议已停止,不再推进。")
    elif neg_stmt:
        b_status = S_COUNTER
        _e0 = neg_stmt[0]
        b_reason = (f"存在反向证据({_e0['level']}〔{_e0['fact_id']}〕):「"
                    f"{_e0['hit'][:40]}」—— 未经核实;核实前不推进该改造。")
    elif no_space:
        b_status = S_COUNTER
        b_reason = "客户补充的表述认为可优化空间有限 —— 属客户陈述,需核实;核实前不推进该改造。"
    elif redundancy:
        b_status = S_VERIFY
        b_reason = "客户补充的分时段数据支持「部分时段存在冗余」—— 进入单店验证,并列出服务质量约束"
    else:
        b_status = S_VERIFY if not premise_weak else S_WEAK
        b_reason = ("缺分时段真实工时与可替代性数据 —— 先取基线再判断" if not premise_weak
                    else "当前证据只支持「不知道」—— 先取基线,暂不推进结构改造")

    cand_b = {
        "key": "B", "closure": "B.structure", "kind": "需客户数据验证",
        "title": CLOSURE_B,
        "claim": "在同样的营业量下,用全职为主的排班方式可能占用了更多工时 —— **待验证**。",
        "support": support_b,
        "counter": counter,
        "unknowns": ["分时段的真实排班工时与客流",
                     "拟改成的兼职 / 小时工占比(当前占比≠拟调整占比)",
                     "可替代性与合规约束(工时下限、技能要求)",
                     "近 8 周排班表 / 考勤原始数据"],
        "verify": ["取近 8 周排班表与考勤原始数据",
                   "按分时段测算工时冗余,而不是看总数",
                   "先在 1 家店验证,并同时观测服务质量是否劣化"],
        "status": b_status,
        "reason": b_reason,
    }
    if b_status == S_COUNTER:
        cand_b["verify"] = ["先核实反向证据:索取分时段排班与客流原始记录比对",
                            "核实前不推进该改造;核实后按规则重新评估"]
    elif b_status == S_STOP:
        cand_b["verify"] = ["若要重启该项改造:提供能推翻该反向证据的原始数据",
                            "再由双方按流程重新评估(当前不推进)"]
    if flags.get("rejected_B"):
        cand_b["status"] = S_REJECTED
        cand_b["reason"] = "客户已明确否定这条判断 —— 保留展示,不再推进。"
    if flags.get("note_B"):
        cand_b["note"] = str(flags["note_B"])
    return [cand_a, cand_b]


def generic_candidates(case, facts, ans=None, flags=None) -> list[dict]:
    """其它行业的兜底:至少给出「材料直接支持」与「需数据验证」两类容器,
    不预设结论。"""
    return [{
        "key": "M", "closure": "material", "kind": "材料直接支持",
        "title": (case.truth_title or "材料直接提到的问题"),
        "claim": case.truth_body or "材料里直接提到的现象。",
        "support": [f.id for f in facts if f.quote_ok][:6],
        "counter": [],
        "unknowns": [u[0] for u in (case.unknowns or [])][:4],
        "verify": ["把材料里提到的现象用一份数据复现一次"],
        "status": S_SUPPORTED if facts else S_WEAK,
        "reason": "由材料直接支持" if facts else "没有材料",
    }, {
        "key": "B", "closure": "hypothesis", "kind": "需客户数据验证",
        "title": "公开基准推断出的优化假设",
        "claim": "基于公开基准的假设 —— 需要客户自己的数据才能成立。",
        "support": [],
        "counter": ["公开基准是别人的结果,不是本客户的实测"],
        "unknowns": [u[0] for u in (case.unknowns or [])][:4],
        "verify": ["取一份脱敏的原始数据做基线"],
        "status": S_VERIFY,
        "reason": "待客户数据验证",
    }]


def build(industry, case, facts, ans=None, flags=None, a=None) -> list[dict]:
    if industry == "餐饮门店" and a is not None:
        return catering_candidates(a, facts, ans, flags)
    return generic_candidates(case, facts, ans, flags)


def overall(cands: list[dict]) -> str:
    """整体建议:不做「有证据就上」,而是按候选状态给一句话。"""
    active = [c for c in cands if c["status"] == S_SUPPORTED
              or c["status"] == S_VERIFY]
    if not active:
        return ("当前证据不支持任何一项改造 —— **暂不建议进行该改造**,先补证据。")
    names = "、".join(c["title"] for c in active)
    return f"建议推进:{names}。**收益结论一律标为「假设情景」,不作为承诺。**"
