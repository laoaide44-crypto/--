"""
契约草稿生成 —— 把一次诊断渲染成一份能签字的文件。

⚠️ 这份模块**不含任何行业逻辑**。
   它只认 `fde_kernel.Case` 这个形状。餐饮也好、物流也好,
   进来都是同一个 Case,出去就是同一份契约 —— 换行业不用改这里一个字。

设计原则(来自 delivery-contract-template.md):
  · 第一页严格一页,给人话;附录沉细节。
  · 每一条都标来源等级 PUBLIC / INTERVIEW / INTERNAL / ASSUMPTION。
  · 拿不到的字段,明确写「未提供 / 待补」,不假装有。
  · **状态一致**:顶部状态、正文措辞、下载文件、摘要用同一份 `gate_state`;
    收到材料 ≠ 证据充分(还要看字段来源 / 口径 / 覆盖 / 基线)。
"""

import fde_facts as FA
from fde_kernel import (ASSUMPTION, INTERNAL, INTERVIEW, LEVEL_LABEL, PUBLIC, Case,
                        money)

UNKNOWN = "**〔未提供 · 待补〕**"
# 加粗 + 下方图例,是**故意的视觉标记**:让人一眼看出这是「填空位」,
# 而不是「这份文件没写完」。用 markdown 粗体而不是 HTML/CSS ——
# 契约要能下载成 .md、还要打印出来手签,加粗在任何阅读器里都在。
DT = "**〔待填〕**"

GATE_ICON = {"待补证据": "⏳", "可设计试点": "🧭",
             "待验收实测": "📏", "已完成试点验证": "✅"}

LEGEND = (
    "\n> 📝 **怎么读**:`PUBLIC / INTERVIEW / INTERNAL / ASSUMPTION` = 每条依据的来源等级;"
    "**〔待填〕** = **现场填写位**(打印后手写,空着是设计);"
    "**〔未提供 · 待补〕** = 目前拿不到,需向甲方索取。\n"
)


def _t(tier: str) -> str:
    return f"`{tier}`"


def _esc(s) -> str:
    """表格里把竖线转义,免得整行被拆断。"""
    return str(s or "").replace("|", "\\|")


def _cited(slot: dict | None, default: str) -> str:
    """槽位 → 「答案〔事实ID〕」;没有就回默认(可能是 UNKNOWN)。"""
    if slot and slot.get("answer"):
        fid = slot.get("fact_id")
        return f"{slot['answer']}〔{fid}〕" if fid else str(slot["answer"])
    return default


def render(case: Case, ans: dict, intake: dict | None = None,
           evidence: dict | None = None) -> str:
    """ans 里的键(现场访谈得到的那几个):
    who_does_it / how_measured / resister / tried_before / internal_data

    evidence:可选的「补证据」报告(带 label 即可)—— 有则注明含合成演示材料。
    """
    ans = dict(ans or {})
    _facts = FA.as_facts(case.facts or [])
    _sl = FA.slots(_facts)

    q_who = ans.get("who_does_it") or _cited(_sl.get("who_does_it"), UNKNOWN)
    q_measure = ans.get("how_measured") or _cited(_sl.get("how_measured"), UNKNOWN)
    q_resist = ans.get("resister") or _cited(_sl.get("resister"), UNKNOWN)
    q_tried = ans.get("tried_before") or _cited(_sl.get("tried_before"), UNKNOWN)
    q_words = ans.get("original_words") or _cited(_sl.get("original_words"), UNKNOWN)

    stt = case.gate_state or "待补证据"
    icon = GATE_ICON.get(stt, "⏳")
    can = "；".join(case.gate_can[:2]) if case.gate_can else "—"
    cannot = "；".join(case.gate_cannot[:2]) if case.gate_cannot else "—"
    appr = "已置位" if getattr(case, "approved", False) else "未置位(批准是独立开关)"

    title = f"{case.industry} · 交付契约(草稿)"
    _istr = case.inputs_source_label or "来源未记录"
    _istier = ASSUMPTION if "默认假设" in _istr else INTERVIEW

    # ---------------- 第一页 ----------------
    md = f"""# {title}

| | |
|---|---|
| **行业** | {case.industry} |
| **甲方** | {DT} |
| **乙方** | {DT} |
| **状态** | **{icon} {stt}** |
| **版本** | v0.1(草稿,由公开基准自动生成) |
| **日期** | {DT} |

> **证据纪律**:结果状态由**可检查的条件**计算(材料 / 字段来源 / 口径 / 覆盖 / 基线),
> **不由模型或措辞自行升级**。**收到材料 ≠ 证据充分**;缺基线时本文件只到「试点设计草案」。
> **实测完成 ≠ 客户批准 ≠ 正式签约。**
>
> {icon} **当前状态 · {stt}** ｜ 可以做:{can} ｜ 不可以做:{cannot}
{LEGEND}"""
    if evidence:
        md += (f"\n> ⚠️ 本文件包含一次**合成演示材料**的补充证据(「{evidence.get('label', '?')}」),"
               f"用于演示「补证据 → 改决策」链路;新增事实已标注来源。\n")

    md += f"""---

## 01 · 问题(甲方原话)

{q_words} {_t(INTERVIEW)}

*原始输入参数({_istr}):{case.inputs_summary or UNKNOWN}* {_t(_istier)}

## 02 · 真问题(我们判定实际要解决的是什么)

**{case.truth_title}**

{case.truth_body}
"""

    # ---------------- 02 附:候选问题与收益口径 ----------------
    if case.candidates:
        md += "\n### 候选问题(每条带支持证据 / 反向证据 / 未知项 / 验证动作)\n\n"
        for cd in case.candidates:
            md += f"**{cd.get('key', '')} · {cd.get('title', '')}** —— **{cd.get('status', '')}**\n\n"
            md += f"- 主张:{cd.get('claim', '')}\n"
            if cd.get("support"):
                md += f"- 支持证据:{'、'.join(str(x) for x in cd['support'])}\n"
            for ct in (cd.get("counter") or []):
                md += f"- 反向证据:{ct}\n"
            for u in (cd.get("unknowns") or []):
                md += f"- 未知项:{u}\n"
            for v in (cd.get("verify") or []):
                md += f"- 建议验证动作:{v}\n"
            if cd.get("note"):
                md += f"- 客户补充:{cd['note']}\n"
            md += f"- 当前依据:{cd.get('reason', '')}\n\n"
        md += f"**整体建议:**{case.candidate_note}\n"

    if getattr(case, "revenue_stopped", False):
        md += ("\n### 收益口径:该改造建议已停止(反向证据支持无可释放工时)\n\n"
               "- **不再给出金额区间,也不再作为本客户的推荐收益。**\n"
               "- 原假设区间只保留为下方「独立假设模拟」,仅作对照,不适用本客户。\n"
               "- 提醒仍然成立:**可释放工时 ≠ 可减少现金支出**;本例连第一步也未成立。\n")
    else:
        md += f"""
### 收益口径:假设情景下的潜在优化空间(与验收分开)

- **{case.revenue_label or '假设情景下的潜在优化空间'}**:{case.money_range()} —— **不是已确认收益,更不是承诺。**
- 第一步(物理量):可释放工时 {case.hours_release_low:,.0f} – {case.hours_release_high:,.0f} 工时/月。
- 第二步(现金口径):**只有**工时可真正从固定成本变成可变成本时才成立 ——
  **可释放工时 ≠ 可减少现金支出**,两者不能自动画等号。
"""
    if case.revenue_assumptions:
        md += "- 假设与来源:\n" + "".join(f"  - {x}\n" for x in case.revenue_assumptions)
    if case.revenue_conditions:
        md += "- 适用条件:\n" + "".join(f"  - {x}\n" for x in case.revenue_conditions)
    md += "- 计算公式:见文末「本契约的算术,你可以自己复算」。\n"

    _money_cell = ("无(该改造建议已停止 —— 反向证据支持无可释放工时)"
                   if getattr(case, "revenue_stopped", False)
                   else f"{case.headline_label} {case.money_range()}")
    md += f"""
## 03 · 谁受益 / 谁受影响

| 受益 | 受影响 · 可能抵触 |
|---|---|
| {q_who}(目前承担此项工作) | {q_resist} {_t(INTERVIEW)} |
| 甲方经营者:{_money_cell} | 〔待补:是否有岗位受影响〕 |

## 04 · 验收标准(必须能判真 / 假)

> 硬规则:出现「提升 / 优化 / 增强」即作废重写。

| # | 标准 | 基线 | 来源 |
|---|---|---|---|
"""
    for i, (std, base, tier) in enumerate(case.acceptance, 1):
        md += f"| {i} | {std} | {base} | {_t(tier)} |\n"
    md += (f"\n**试点范围**(由当前证据与已确认的优先问题决定):"
           f"{case.pilot_scope or '〔待补证据后确定〕'}\n\n"
           f"**停止条件**:{case.stop_condition or '〔待定〕'}\n")

    md += "\n## 05 · 明确不在范围内\n\n"
    for x in case.out_of_scope:
        md += f"- {x}\n"

    md += "\n## 06 · 交付物清单\n\n"
    for x in case.deliverables:
        # ☐ 而不是 markdown 的任务清单 `- [ ]`:后者会被 Streamlit 渲染成真的 checkbox 控件,
        # 在页面里就是 4~5 个**没有无障碍名的 input**(审计 form_control_label 报的那几条),
        # 而且看上去能点、实际点不动。契约本来就是要打印/签字的,☐ 在任何阅读器里都清楚。
        md += f"- ☐ {x}\n"

    md += "\n## 07 · 里程碑\n\n| 时间 | 交付 | 谁验收 |\n|---|---|---|\n"
    for when, what, who in case.milestones:
        md += f"| {when} | {what} | {who} |\n"

    md += "\n## 08 · 双方责任\n\n| 甲方提供 | 乙方提供 |\n|---|---|\n"
    for i, (jia, yi) in enumerate(case.responsibilities):
        extra = ""
        if i == 0:
            extra = f"<br>甲方答复:{ans.get('internal_data') or DT}"
        md += f"| {jia} {_t(INTERNAL)}{extra} | {yi} |\n"

    md += "\n## 09 · 风险登记\n\n| 风险 | 影响 | 应对 | 谁盯 |\n|---|---|---|---|\n"
    for _r in case.risks:
        _r = list(_r) + [DT] * (4 - len(_r))
        md += f"| {_r[0]} | {_r[1]} | {_r[2]} | {_r[3]} |\n"

    md += f"""
## 10 · 生效与重议条件

出现下列任一情况,本契约需重新签署:
① 第 08 条数据未按期到位;② 第 04 条验收口径变更;③ 甲方决策人更换。

## 11 · 签字

甲方(盖章/签字):________________　　日期:________

乙方(签字):________________　　　日期:________

---

# 附录

## 附录 A · 证据链

| 编号 | 结论 | 出处 | 来源等级 | 可信度 |
|---|---|---|---|---|
"""
    for e in case.evidence:
        md += (f"| {_esc(e.id)} | {_esc(e.conclusion)} | {_esc(e.source)} | "
               f"`{e.tier}` | {e.confidence} |\n")

    _kq = ans.get("key_quotes") or FA.key_quotes(_facts)
    if not _kq:
        _kq = "〔关键原话待补 · 逐字记录,这是附录 A 最有力的部分〕"
    md += f"\n{_kq}\n"

    md += "\n## 附录 B · 证据充分度(状态由可检查条件计算)\n\n"
    md += f"- **当前状态:{icon} {stt}** ｜ 客户批准:{appr}\n"
    if case.gate_reasons:
        md += "- 为什么是这个状态:\n" + "".join(f"  - {r}\n" for r in case.gate_reasons)
    md += f"- 缺口:{('；'.join(case.gate_missing) or '无')}\n"
    md += f"- 现在能做:{can}\n"
    md += f"- 现在不能做:{cannot}\n"
    md += "- 纪律:证据不足时停在架构之前,不往下推。\n"

    md += """
## 附录 C · 未知项清单(当 bug 一样追)

| # | 未知项 | 影响 | 从哪拿 | 状态 |
|---|---|---|---|---|
"""
    for i, (what, impact, how) in enumerate(case.unknowns, 1):
        md += f"| U{i} | {what} | {impact} | `{how}` | 未开始 |\n"

    md += f"""
## 附录 D · 变更记录

| 时间 | 变更 | 提出人 | 批复人 |
|---|---|---|---|
| {DT} | 契约 v0.1 由公开基准自动生成 | 系统 | {DT} |

---

## 本契约的算术,你可以自己复算

"""
    for line in case.recalc_steps:
        md += f"{line}\n\n"

    md += "\n## 附录 E · 行业基准对照(供甲方核验)\n\n"
    md += "以下全部为公开口径,甲方可自行查证。**它们没有得到甲方确认,因此不能单独作为承诺依据。**\n\n"
    md += "| 维度 | 指标 | 数值 | 出处 |\n|---|---|---|---|\n"
    for group, label, value, source in case.bench_rows:
        md += f"| {group} | {label} | {value} | {source} |\n"

    if case.caveats:
        md += "\n### ⚠️ 口径陷阱(写在这里以免误用)\n\n"
        for i, cv in enumerate(case.caveats, 1):
            md += f"{i}. {cv}\n"

    if case.side_line:
        md += f"\n### {case.side_title or '另一条线(仅作参考,未计入上面区间)'}\n\n{case.side_line}\n"

    if intake:
        md += _intake_appendix(intake, _facts)
    return md


def _intake_appendix(pack: dict, facts: list | None = None) -> str:
    """附录 F:记下这份结论是从哪份材料、哪些原句推出来的。

    三层校验分开列(不能互相自动升级):
      ① 原句是否存在(引用定位)
      ② 原句是否支持结论
      ③ 结论是否适用于当前客户
    """
    res = pack.get("result") or {}
    sc = pack.get("scan")
    verif = pack.get("verify") or {}
    raw_facts = res.get("facts") or []
    conflicts = res.get("conflicts") or []
    unknowns = res.get("unknowns") or []
    pf = res.get("prefill") or {}
    objs = list(facts or [])

    out = ["\n---\n\n# 附录 F · 客户材料抽取记录\n"]
    out.append("本契约的参数,部分来自甲方提供的原始材料(聊天记录 / 邮件 / 表格等)。"
               "下面把抽取过程和每条依据的原句一并列明。\n")

    if pack.get("demo"):
        out.append(
            f"\n> ⚠️ **本附录来自「演示模式」**:材料抽取结果捕捉于 "
            f"**{pack.get('demo_captured_at', '?')}**(联网环境下跑出的真实结果),"
            f"**不是本次现场实时计算的**。如需实时结果,请在联网环境下重新运行。\n"
        )

    if sc:
        out.append(f"**材料规模**:{sc.n_chars:,} 字,切成 {sc.n_units} 个可定位单元;"
                   f"扫描到金额/数量 {len(sc.money)} 处、百分比 {len(sc.percents)} 处"
                   f"(已遮蔽隐私 {sc.masked} 处)。\n")

    if verif.get("total"):
        if verif.get("fail", 0) == 0:
            out.append(f"**引用定位:{verif['ok']} 条引用均可在原文定位**(共 {verif['total']} 条)。\n")
        else:
            out.append(f"**引用定位:{verif['ok']}/{verif['total']} 条可在原文定位;"
                       f"{verif['fail']} 条无法定位 —— 已降级为「无法回指」,不作为事实使用。**\n")
        out.append("> 三层分开记录:① 原句是否存在(本节);② 原句是否支持结论;"
                   "③ 结论是否适用于当前客户(见 F.2 各列)。"
                   "**原句匹配成功不自动升级为「已验证」。**\n")

    if pf:
        out.append("## F.1 · 参数从哪句话来\n")
        out.append("| 参数 | 采用值 | 原句 |\n|---|---|---|\n")
        label = {"store_count": "门店数", "rev_per_store": "单店月流水(元)",
                 "emp_per_store": "单店员工数(人)",
                 "parcels_per_day": "日均件量(票)", "cost_per_parcel": "单票综合成本(元)",
                 "sites": "场站数"}
        for k, v in pf.items():
            val = v.get("value")
            raw = v.get("value_raw")
            show = f"{val:g}" if isinstance(val, (int, float)) else "未采用"
            if raw and str(raw) != show:
                show += f"(原文「{raw}」)"
            out.append(f"| {label.get(k, k)} | {show} | {v.get('quote') or '—'} |\n")

    if objs:
        out.append("\n## F.2 · 统一事实记录(带稳定 ID;三层校验分开列)\n")
        out.append("| ID | 类型 | 事实 | 原句 | 材料位置 | 来源 | 状态 | 原句支持 | 适用于本客户 |\n")
        out.append("|---|---|---|---|---|---|---|---|---|\n")
        for f in objs:
            out.append(
                f"| {_esc(f.id)} | {_esc(f.kind)} | {_esc(f.text)} | 「{_esc(f.quote)}」 | "
                f"{_esc(f.locator)} | {f.source_type} | {f.status} | "
                f"{f.support_status} | {f.apply_status} |\n")
    elif raw_facts:
        out.append("\n## F.2 · 从材料里抽出的可用事实\n")
        out.append("| 类型 | 事实 | 原句 | 来源等级 |\n|---|---|---|---|\n")
        for f in raw_facts:
            lv = f.get("level", "")
            mark = "⚠ 无法回指" if not f.get("quote_ok", True) else f"`{lv}`"
            txt = _esc(f.get("text") or "")
            qt = _esc(f.get("quote") or "")
            out.append(f"| {f.get('kind', '')} | {txt} | 「{qt}」 | {mark} |\n")

    real, clues, corrected = FA.classify_full(conflicts, objs,
                                              units=(pack.get("units") or []))
    if corrected:
        out.append("\n## F.3a · ✅ 已更正(替代关系 —— 旧值保留在历史,新值进入当前计算)\n")
        for c in corrected:
            out.append(f"- **{c.get('old', '')}** → **{c.get('new', '')}**"
                       f"(同一来源:{c.get('by', '')})\n"
                       f"  - 更正原话:「{c.get('marker', '')}」\n"
                       f"  - 处理:旧值保留在历史记录(F.2 继续列出);当前计算采用新值。\n"
                       f"  - 纪律:更正只建立**替代关系**,不表示新值已核实;来源等级保持原级。\n")
    if real:
        out.append("\n## F.3 · ⚠️ 待核实冲突(同一对象、同一时间、同一口径下不能同时成立)\n")
        for c in real:
            out.append(f"- **{c.get('a', '')}** ↔ **{c.get('b', '')}**\n"
                       f"  - 为什么算冲突:{c.get('why', '')}\n"
                       f"  - 原句:「{c.get('quote_a', '')}」 / 「{c.get('quote_b', '')}」\n"
                       f"  - 核实办法:{c.get('scope', '')}\n")
    if clues:
        out.append("\n## F.3b · 落地失败 / 异常线索(不是矛盾,是经历 —— 值得当面追问)\n")
        for c in clues:
            out.append(f"- **{c.get('kind', '线索')}**:{c.get('what', '')}\n"
                       f"  - 为什么归为线索:{c.get('why', '')}\n"
                       f"  - 原句:「{c.get('quote', '')}」\n")

    if unknowns:
        out.append("\n## F.4 · 材料没说、但决策必须知道的\n")
        out.append("| 还不知道什么 | 为什么必须知道 | 从哪拿 |\n|---|---|---|\n")
        for u in unknowns:
            out.append(f"| {u.get('what', '')} | {u.get('why_needed', '')} | {u.get('how_to_get', '')} |\n")

    out.append("\n> 说明:本附录只记录了**材料里能回指到的内容**。"
               "甲方若发现原句引用有误,以原始材料为准。\n")
    return "".join(out)
