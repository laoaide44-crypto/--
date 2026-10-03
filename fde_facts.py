"""
统一事实记录 —— 让追问、测算、契约**引用同一份数据**。

以前的问题:材料里明明抽出了「王店长负责 12 家店排班 / 每周至少一天 /
买过排班软件闲置 / 排班理由难解释 / 员工担心工时被压」,但契约里仍然写
「甲方原话待补 / 目前承担工作的人待补 / 过去尝试过未提供」——
抽取结果和契约之间**没有同一份数据**,信息在传递中丢了。

这份模块提供:
  · `Fact`      —— 一条事实的稳定记录(ID / 原句 / 材料位置 / 来源类型 / 证据状态)
  · `build()`   —— 把材料抽取结果转成统一事实记录(带稳定 ID)
  · `slots()`   —— 把事实**确定性地**映射到契约字段(不再显示「未提供」)
  · `partial()` —— 原句只支持部分结论时,剩下的部分保留为**待验证推断**
  · `classify()`—— 区分「待核实冲突」与「落地失败 / 异常线索」

三层校验分开记录(不能互相自动升级):
  1. quote_ok       原句是否存在(可在原文定位)
  2. support_status 原句是否支持结论(完全 / 部分 / 待逐字核对)
  3. apply_status   结论是否适用于当前客户(默认「待客户确认」)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict

# 来源类型(这份东西**从哪来**)—— 与证据状态(它有多硬)是两件事
SRC_MATERIAL = "客户材料"
SRC_PUBLIC = "公开资料"
SRC_INTERNAL = "内部数据"

# 证据状态(它有多硬)
ST_DIRECT = "直接陈述"
ST_PENDING = "待确认"
ST_INFERRED = "推断"
ST_MEASURED = "已实测"

# 支撑检查
SUP_FULL = "完全支持"
SUP_PART = "部分支持"
SUP_TODO = "待逐字核对"

# 结论适用性
APPLY_PENDING = "待客户确认"
APPLY_YES = "已适用实测"


def _norm(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u3000", " ")
    out = []
    for ch in s:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        elif ch in "“”‘’「」『』\"'":
            continue
        else:
            out.append(ch)
    return re.sub(r"\s+", "", "".join(out))


def _stable_id(text: str, taken: set[str]) -> str:
    """稳定 ID:由事实内容决定,同一句话在多次运行里 ID 不变。
    这样追问引用的、测算引用的、契约引用的是同一个 ID。"""
    h = hashlib.sha1(_norm(text).encode("utf-8")).hexdigest()[:4].upper()
    fid = f"F{h}"
    n = 1
    while fid in taken:
        fid = f"F{h}{n}"
        n += 1
    taken.add(fid)
    return fid


def partial(text: str, quote: str) -> tuple[bool, str]:
    """原句是否完整支持结论。返回 (是否完全支持, 未被原句覆盖的剩余部分)。

    确定性、保守:匹配不上就算「部分支持」,并把没被覆盖的表述留成待验证推断。
    """
    t, q = _norm(text), _norm(quote)
    if not q:
        return False, text
    if t and (t in q or q in t):
        return True, ""
    parts = [p for p in re.split(r"[，,。;；、！!?？\n]", text) if len(_norm(p)) >= 2]
    miss = []
    for p in parts:
        np = _norm(p)
        if np in q:
            continue
        grams = [np[i:i + 3] for i in range(max(1, len(np) - 2))]
        if any(g in q for g in grams):
            continue
        miss.append(p.strip())
    if not miss:
        return True, ""
    return False, "、".join(miss[:3])


@dataclass
class Fact:
    id: str
    text: str
    quote: str = ""
    locator: str = ""
    kind: str = ""
    source_type: str = SRC_MATERIAL
    status: str = ST_PENDING
    quote_ok: bool = False
    support_status: str = SUP_TODO
    remainder: str = ""
    apply_status: str = APPLY_PENDING
    supports: list[str] = field(default_factory=list)   # 这条事实支撑哪些结论键
    confirmed: bool = False                              # 客户/用户确认状态
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def as_fact(obj) -> "Fact | None":
    """把 Fact 或 dict 统一成 Fact 对象(字段过滤;脏数据返回 None)。"""
    if isinstance(obj, Fact):
        return obj
    if isinstance(obj, dict):
        names = set(Fact.__dataclass_fields__)
        try:
            return Fact(**{k: v for k, v in obj.items() if k in names})
        except (TypeError, ValueError):
            return None
    return None


def as_facts(objs) -> list["Fact"]:
    """Fact / dict 混合列表 → Fact 列表。"""
    out = []
    for o in objs or []:
        f = as_fact(o)
        if f is not None:
            out.append(f)
    return out


def coverage(facts: list["Fact"]) -> tuple[int, list[str]]:
    """材料覆盖到几个契约字段(只数,不做结论)。用于证据门槛的 coverage 检查。"""
    sl = slots(facts)
    keys = [k for k in ("who_does_it", "tried_before", "resister", "how_measured")
            if k in sl]
    return len(keys), keys


def _level_to_status(level: str, quote_ok: bool) -> str:
    if not quote_ok:
        return ST_INFERRED
    return {"DIRECT": ST_DIRECT, "CONFIRMED": ST_DIRECT,
            "SINGLE": ST_PENDING, "INFERRED": ST_INFERRED}.get(level, ST_PENDING)


def build(pack: dict | None, supports_map: dict | None = None) -> list[Fact]:
    """把 fde_intake 的 pack(含 result.facts)转成统一事实记录。

    supports_map: {关键词: 结论键} —— 行业/规则提供的「这条事实支撑什么」。
    """
    res = (pack or {}).get("result") or {}
    raw_facts = res.get("facts") or []
    supports_map = supports_map or {}
    taken: set[str] = set()
    out: list[Fact] = []
    for f in raw_facts:
        text = (f.get("text") or "").strip()
        if not text:
            continue
        quote = (f.get("quote") or "").strip()
        qok = bool(f.get("quote_ok", True))
        ok, rem = partial(text, quote)
        if not qok:
            ok, rem = False, text
        st = _level_to_status(f.get("level", ""), qok)
        sup = SUP_TODO if not qok else (SUP_FULL if ok else SUP_PART)
        key = _stable_id(text, taken)
        blob = _norm(text) + _norm(quote)
        supports = [k for kw, k in supports_map.items() if kw and _norm(kw) in blob]
        out.append(Fact(
            id=key, text=text, quote=quote,
            locator=f.get("source", "") or "",
            kind=f.get("kind", ""),
            source_type=SRC_MATERIAL,
            status=st, quote_ok=qok, support_status=sup, remainder=rem,
            apply_status=APPLY_PENDING, supports=supports,
        ))
    return out


# ---------------------------------------------------------------- 确定性槽位映射
# 目标:材料里已经给过的东西,**不再显示「未提供」**。
# 规则是确定性的(关键词),不交给模型 —— 模型只负责抽事实,这里只负责归位。

_SLOT_RULES: dict[str, dict] = {
    "who_does_it": {
        "need_any": ("排班", "班表", "成本", "对账", "算成本", "报表"),
        "need_kw": ("我一个人", "自己", "负责", "我一个人弄", "我来"),
        "extra": ("至少一天", "一周", "每周", "小时", "周一"),
    },
    "tried_before": {
        "need_any": ("软件", "系统", "平台", "工具"),
        "need_kw": ("买过", "采购", "上过", "装过", "用过", "去年", "前年"),
        "fail_kw": ("没人用", "闲置", "用不起来", "放着", "没人看", "看不懂", "最后就"),
    },
    "resister": {
        "need_any": ("怕", "担心", "抵触", "不愿意", "不希望", "顾虑", "反对"),
    },
    "how_measured": {
        "need_any": ("看不出", "没个准数", "没有", "指标", "标准", "口径",
                     "考核", "说不清", "分不出来"),
    },
}


def slots(facts: list[Fact]) -> dict[str, dict]:
    """从事实里**确定性地**归位到契约字段。返回 {字段: {answer, quote, fact_id}}。"""
    out: dict[str, dict] = {}
    for f in facts:
        if not f.quote_ok:
            continue
        blob = _norm(f.text) + _norm(f.quote)
        for key, rule in _SLOT_RULES.items():
            if key in out:
                continue
            need_any = rule.get("need_any")
            if need_any and not any(_norm(k) in blob for k in need_any):
                continue
            need_kw = rule.get("need_kw")
            if need_kw and not any(_norm(k) in blob for k in need_kw):
                continue
            if key == "tried_before":
                fail = rule.get("fail_kw") or ()
                if fail and not any(_norm(k) in blob for k in fail):
                    # 只买到「买过」但没说结局 —— 也算，但标注
                    pass
            out[key] = {"answer": f.text, "quote": f.quote, "fact_id": f.id,
                        "status": f.status}
    # who_does_it 的工时补充
    if "who_does_it" in out:
        for f in facts:
            b = _norm(f.text) + _norm(f.quote)
            if any(_norm(k) in b for k in ("至少一天", "一周", "每周", "周一", "花多久")):
                out["who_does_it"]["answer"] = (
                    f"{out['who_does_it']['answer']} —— {f.text}")
                out["who_does_it"]["extra_fact"] = f.id
                break
    # 甲方原话:取第一条「需求/风险」类里带情绪的原句;没有分类就退而取第一条可定位原句
    for f in facts:
        if f.kind in ("需求", "风险", "约束", "人物") and f.quote_ok and f.quote:
            out["original_words"] = {"answer": f.quote, "quote": f.quote, "fact_id": f.id}
            break
    if "original_words" not in out:
        for f in facts:
            if f.quote_ok and len(f.quote) >= 8:
                out["original_words"] = {"answer": f.quote, "quote": f.quote,
                                         "fact_id": f.id}
                break
    return out


def key_quotes(facts: list[Fact], limit: int = 6) -> str:
    """附录 A 的「关键原话」:优先给能定位、且支持结论的那几条;同一句只出现一次。"""
    picked, _seen = [], set()
    for f in facts:
        if not f.quote_ok or not f.quote:
            continue
        _k = _norm(f.quote)
        if _k in _seen:
            continue
        _seen.add(_k)
        picked.append(f)
        if len(picked) >= limit:
            break
    if not picked:
        return ""
    lines = ["**关键原话(逐字,带回指)**:"]
    for f in picked:
        tag = f"{f.id} · {f.status}"
        lines.append(f"- 「{f.quote}」 —— {tag}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 冲突 vs 线索
_PROCURE = ("买过", "采购", "上过", "装过", "购入", "买了", "去年买", "前年上")
_UNUSED = ("没人用", "没人看", "闲置", "用不起来", "放着", "最后就",
           "看不懂", "不合用", "没人愿意用")
_TOOL = ("软件", "系统", "平台", "工具", "报表")


# ---------------------------------------------------------------- 更正 vs 冲突
# 「同一来源、同一对象、明确说『前面说错了 / 以新值为准』」→ 替代关系:
#   旧值留在历史记录,新值进入当前计算;**不再列为待核实冲突**。
# 「不同来源互相矛盾」或找不到明确更正 → 保留冲突,不擅自覆盖。
_CORRECTION_MARKS = ("更正", "纠正", "说错", "作废", "改口", "修正", "重新说",
                     "为准", "老数据", "过时", "过期")
_CHAT_SPK = re.compile(r"\d{1,2}:\d{2}\s+(\S+)\s*$")


def _unit_pair(units) -> list[tuple[str, str]]:
    """Unit 对象 / dict 都归一成 [(locator, text)]。"""
    out = []
    for u in units or []:
        if isinstance(u, dict):
            out.append((str(u.get("locator") or ""), str(u.get("text") or "")))
        else:
            out.append((str(getattr(u, "locator", "") or ""),
                        str(getattr(u, "text", "") or "")))
    return out


def _speaker(locator: str) -> str:
    m = _CHAT_SPK.search((locator or "").replace("\u3000", " ").strip())
    return m.group(1) if m else ""


def _find_unit(quote: str, pairs: list[tuple[str, str]]) -> int | None:
    q = _norm(quote)
    if not q:
        return None
    for i, (_, t) in enumerate(pairs):
        if q in _norm(t):
            return i
    return None


def _share_token(a: str, b: str) -> bool:
    """轻量「同对象」检查:两句去掉数字后有公共 2 字片段。"""
    na = re.sub(r"\d+", "", _norm(a))
    nb = re.sub(r"\d+", "", _norm(b))
    if len(na) < 2 or len(nb) < 2:
        return False
    return any(na[i:i + 2] in nb for i in range(len(na) - 1))


def _as_correction(c: dict, pairs: list[tuple[str, str]]) -> dict | None:
    """同一来源 + 明确更正表述 → 「已更正(替代关系)」;否则 None(保守保留冲突)。"""
    qa, qb = str(c.get("quote_a") or ""), str(c.get("quote_b") or "")
    ia, ib = _find_unit(qa, pairs), _find_unit(qb, pairs)
    if ia is None or ib is None or ia == ib:
        return None
    sa, sb = _speaker(pairs[ia][0]), _speaker(pairs[ib][0])
    if not sa or sa != sb:                        # 不同来源 → 保留冲突,不擅自覆盖
        return None
    lo, hi = min(ia, ib), max(ia, ib)
    marker = None
    for j in range(lo, min(hi + 2, len(pairs))):
        loc, t = pairs[j]
        if _speaker(loc) == sa and any(k in t for k in _CORRECTION_MARKS):
            marker = t.strip()
            break
    if not marker:                                # 没有明确更正 → 不建立替代关系
        return None
    if not _share_token(qa, qb):                  # 对象存疑 → 保守保留冲突
        return None
    old, new = (c.get("a"), c.get("b")) if ia < ib else (c.get("b"), c.get("a"))
    old_q, new_q = (qa, qb) if ia < ib else (qb, qa)
    return {
        "kind": "已更正(替代关系)",
        "old": str(old or old_q), "new": str(new or new_q),
        "quote_old": old_q, "quote_new": new_q,
        "by": sa, "marker": marker,
    }


def classify(conflicts: list[dict], facts: list[Fact], units=None):
    """兼容入口:只返回 (real, clues);「已更正」见 classify_full。"""
    real, clues, _ = classify_full(conflicts, facts, units)
    return real, clues


def classify_full(conflicts: list[dict], facts: list[Fact],
                  units=None) -> tuple[list[dict], list[dict], list[dict]]:
    """把模型给的 conflicts 拆成三类:
      · 已更正(替代关系) —— 同一来源的明确更正(旧值留历史,新值进计算)
      · 真·待核实冲突   —— 只在**同一对象、同一时间、同一口径**下不能同时成立
      · 落地失败 / 异常线索 —— 时序上的「采购了但没落地」不是矛盾
    """
    pairs = _unit_pair(units)
    real, clues, corrected = [], [], []
    for c in conflicts or []:
        _sup = _as_correction(c, pairs) if pairs else None
        if _sup is not None:
            corrected.append(_sup)
            continue
        a = _norm(str(c.get("a", "")) + str(c.get("quote_a", "")))
        b = _norm(str(c.get("b", "")) + str(c.get("quote_b", "")))
        blob = a + b
        toolish = any(_norm(k) in blob for k in _TOOL)
        proc = any(_norm(k) in a for k in _PROCURE) or any(_norm(k) in b for k in _PROCURE)
        unused = any(_norm(k) in a for k in _UNUSED) or any(_norm(k) in b for k in _UNUSED)
        if toolish and proc and unused:
            clues.append({
                "kind": "落地失败线索",
                "what": c.get("a") or c.get("b") or "工具已采购但未落地",
                "why": "「买了却没用起来」是**时序上的失败经历**,不是互相矛盾的陈述 —— "
                       "把工具闲置当成「异常线索」比当成「事实冲突」更有用。",
                "quote": c.get("quote_a") or c.get("quote_b") or "",
            })
        else:
            real.append({
                **c,
                "scope": "需在同一对象、同一时间、同一口径下当面核实",
            })
    # 再从事实里补一条确定性线索:买过工具且提到不可解释
    for f in facts:
        b = _norm(f.text) + _norm(f.quote)
        if any(_norm(k) in b for k in _TOOL) and any(_norm(k) in b for k in _PROCURE) \
                and any(_norm(k) in b for k in _UNUSED):
            if not any(_norm(f.quote[:12]) in _norm(x.get("quote", "")) for x in clues):
                clues.append({
                    "kind": "落地失败线索",
                    "what": f.text,
                    "why": "既有工具却未采用 —— 通常卡在「结果不可解释」,不是功能不够。",
                    "quote": f.quote,
                })
    return real, clues, corrected


# ---------------------------------------------------------------- 供 UI / 契约使用
def summary_counts(facts: list[Fact], verif: dict | None = None) -> dict:
    """给界面用的一句话统计。措辞按「引用定位」而不是「回指通过」。"""
    total = len(facts)
    located = sum(1 for f in facts if f.quote_ok)
    full = sum(1 for f in facts if f.support_status == SUP_FULL)
    part = sum(1 for f in facts if f.support_status == SUP_PART)
    return {
        "total": total, "located": located,
        "support_full": full, "support_part": part,
        "line": (f"{located}/{total} 条引用可在原文定位;"
                 f"其中 {full} 条原句完整支持结论,{part} 条只有部分支持(余下留作待验证推断)。"
                 if total else "本次没有可从材料定位的引用。"),
    }


def rows(facts: list[Fact]) -> list[dict]:
    """界面表格:每条事实一行,三层校验分开列。"""
    out = []
    for f in facts:
        out.append({
            "ID": f.id,
            "类型": f.kind,
            "事实": f.text,
            "原句": f.quote,
            "材料位置": f.locator,
            "来源": f.source_type,
            "状态": f.status,
            "原句支持": f.support_status,
            "适用于本客户": f.apply_status,
            **({"未覆盖部分": f.remainder} if f.remainder else {}),
        })
    return out
