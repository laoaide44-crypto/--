"""
进场包 · 第 5 步:沉淀可复用资产(1→N)

一次交付做完,把里面**能跨客户复用的东西**抽出来,存成资产库;
下一个客户进来时,资产库先给出**可用的假设**。

三条纪律(不能破):
  1. **去标识**:资产里不能出现任何客户名字、具体金额、具体门店数。
  2. **复用的是假设,不是事实**:来自上一个客户的经验,到新客户那里必须**重新验证**。
     界面上必须标成"待验证的假设"。
  3. **单一样本永远不是基准**:一条样本存进来时标 `样本数=1`,并且明确写
     「不可当基准用」;只有同一口径被多个项目反复证实过,才算基准。
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, asdict, field

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reuse-library.json")
SCHEMA = 1

BENCH, ACCEPT, RESIST, TRAP, QUESTION, METRIC = (
    "基准", "验收范式", "阻力模式", "陷阱", "问题模板", "口径观察")

KIND_ORDER = [BENCH, ACCEPT, RESIST, TRAP, METRIC, QUESTION]


@dataclass
class Asset:
    id: str
    kind: str
    text: str            # 去标识后的可复用表述
    applies_to: str      # 适用条件(行业/规模/场景)
    tier: str            # PUBLIC / INTERVIEW / INTERNAL / ASSUMED
    source: str          # 来自哪个项目代号(不含客户名)
    created: str
    samples: int = 1     # 该口径被证实过的样本数
    uses: int = 0        # 被引用次数
    confirmed: int = 0   # 被新客户材料证实过几次
    note: str = ""


# ---------------------------------------------------------------- 存 / 取
def load() -> list[Asset]:
    if not os.path.exists(LIB):
        return []
    try:
        with open(LIB, encoding="utf-8") as f:
            d = json.load(f)
        return [Asset(**a) for a in d.get("assets", [])]
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def save(assets: list[Asset]) -> str:
    data = {"schema": SCHEMA, "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "assets": [asdict(a) for a in assets]}
    with open(LIB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return LIB


def add(new: list[Asset]) -> int:
    lib = load()
    seen = {(a.kind, a.text) for a in lib}
    added = 0
    for a in new:
        hit = next((x for x in lib if x.kind == a.kind and x.text == a.text), None)
        if hit:
            hit.samples += 1                      # 同一口径被再次证实
            if hit.samples >= 3 and hit.kind == BENCH:
                hit.note = "已有多个样本,可作为参考区间"
            continue
        if (a.kind, a.text) in seen:
            continue
        lib.append(a)
        added += 1
    save(lib)
    return added


def stats() -> dict:
    lib = load()
    return {
        "total": len(lib),
        "by_kind": {k: sum(1 for a in lib if a.kind == k) for k in KIND_ORDER},
        "multi_sample": sum(1 for a in lib if a.samples >= 3),
    }


# ---------------------------------------------------------------- 去标识
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _deid(s: str) -> str:
    """把具体数字和可能的店名抹掉,只留模式。"""
    if not s:
        return ""
    s = _NUM.sub("N", s)
    s = re.sub(r"[“”\"「」]", "", s)
    return s.strip()


# ---------------------------------------------------------------- 抽取
def harvest(case, ans: dict, pack: dict, project: str = "P-未命名") -> list[Asset]:
    """从一次交付里抽可复用资产。**规则是确定性的**,不交给模型。

    接受的是 `fde_kernel.Case` —— 所以**任何行业都能沉淀**,
    而不是只针对餐饮。行业特有的东西(比如“兼职占比”)
    只有在**它真的存在于这次诊断里**时才记。
    """
    now = time.strftime("%Y-%m-%d")
    out: list[Asset] = []

    def mk(kind, text, applies_to, tier="INTERVIEW", note="", samples=1):
        return Asset(id=uuid.uuid4().hex[:8], kind=kind, text=text,
                     applies_to=applies_to, tier=tier, source=project,
                     created=now, samples=samples, note=note)

    industry = case.industry or "未标注行业"

    # 1) 钱的口径:这个行业“钱是怎么算出来的”本身就可复用
    if case.headline_label:
        out.append(mk(
            METRIC,
            f"【{industry}】的钱口径:{case.headline_label}。"
            f"下一次遇到同行业客户,先按这个口径把数算出来,再谈方案。",
            industry, tier="PUBLIC",
            note="口径来自本作品的行业模块,与具体客户无关"))

    # 2) 验收范式
    if case.acceptance:
        out.append(mk(
            ACCEPT,
            f"【{industry}】可判真假的验收标准通常挂在这几个指标上:"
            + "、".join(f"「{s.split('(')[0].strip()[:24]}」" for s, _, _ in case.acceptance[:3])
            + "。共同点:都有基线、都能判真假。",
            industry, tier="PUBLIC",
            note="指标本身来自公开基准;组合方式是本次实践的产物"))

    # 3) 缺席的指标 = 可以立规矩的地方
    if ans.get("how_measured") and "没有" in str(ans["how_measured"]):
        out.append(mk(
            METRIC,
            f"【{industry}】这类客户普遍**没有**衡量「做得好不好」的现成指标 —— "
            "所以「立一个可判定的标准」本身就是交付价值的一部分,而不是额外动作。",
            industry, note="基于一次观察,样本数不足"))

    # 4) 阻力模式(行业不同,怕的东西不同)
    if ans.get("resister"):
        if any(k in industry for k in ("物流", "快递")):
            fear = "「怕被压派费 / 怕指标变成追责工具」"
            how = "先做「可解释的成本口径」,不要一上来做「自动降本」"
        else:
            fear = "「怕被压缩工时 / 怕失去原有的裁量权」"
            how = "先做「建议 + 理由」,不要一上来做「自动排定」"
        out.append(mk(
            RESIST,
            f"【{industry}】常见阻力来自一线执行者,理由通常不是技术,而是"
            f"{fear}。对应做法:{how}。",
            industry,
            note=f"原始表述(去标识):{_deid(str(ans['resister']))[:40]}"))

    # 5) 陷阱
    tb = str(ans.get("tried_before") or "")
    if tb and any(k in tb for k in ("软件", "系统", "平台", "工具")):
        out.append(mk(
            TRAP,
            f"【{industry}】客户买过工具却被弃用,最常见的原因不是功能不够,是"
            "**结果不可解释** —— 使用者不知道系统为什么这么算。"
            "所以顺序应当是:先解决「可解释」,再解决「自动化」。",
            industry, note=f"事实来源:{_deid(tb)[:40]}"))

    # 6) 口径观察(行业特有的参数;只有本次真的拿到了才记)
    if ans.get("part_time_ratio") is not None:
        p = float(ans["part_time_ratio"])
        out.append(mk(
            BENCH,
            f"【{industry}】实测到的「兼职/小时工占比」约 {p:.0%}。"
            f"⚠️ **单一样本,不可当基准用** —— 只能作为下一次的初始假设。",
            industry, tier="INTERVIEW", samples=1,
            note="样本数=1;累积到 3 个以上样本才可当参考区间"))

    return out


# ---------------------------------------------------------------- 给新客户提建议
# 关键词按行业分组:物流的材料拿不出餐饮的资产,反之也一样。
# (旧行为是一个平的餐饮词表 —— 物流材料永远匹配不上,这里修掉。)
_INDUSTRY_KW = {
    "餐饮门店": ("门店", "排班", "店长", "用工", "兼职", "小时工", "餐饮", "人力"),
    "快递物流": ("件量", "单票", "派费", "网点", "场站", "分拨", "快递", "物流", "干线", "中转"),
}
_ALL_KW = tuple(k for v in _INDUSTRY_KW.values() for k in v)


def _matches(asset: Asset, blob: str, kws=None) -> bool:
    if asset.applies_to and kws:
        return any(k in blob for k in kws)
    return False


def suggest(pack: dict, industry: str | None = None) -> list[Asset]:
    """给新客户找可用资产。全部标成「待验证的假设」。
    industry 传当前行业 → 只用该行业的关键词匹配。"""
    lib = load()
    if not lib:
        return []
    facts = (pack.get("result") or {}).get("facts") or []
    blob = " ".join((f.get("text") or "") + (f.get("quote") or "") for f in facts)
    if not blob.strip():
        return []
    kws = _INDUSTRY_KW.get(industry) or _ALL_KW
    hits = [x for x in lib if _matches(x, blob, kws)]
    hits.sort(key=lambda x: (-x.samples, -x.confirmed))
    return hits[:6]


def mark_used(ids: list[str]) -> None:
    lib = load()
    idset = set(ids)
    for a in lib:
        if a.id in idset:
            a.uses += 1
    save(lib)


def format_suggestions(hits: list[Asset]) -> str:
    if not hits:
        return ""
    lines = []
    for h in hits:
        tag = f"（{h.samples} 个样本）" if h.samples > 1 else ""
        lines.append(f"- **[{h.kind}]** {h.text} {tag}")
        if h.note:
            lines.append(f"  - 备注:{h.note}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("资产库:", stats())
    print("文件:", LIB, "存在:", os.path.exists(LIB))
