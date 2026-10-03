"""
行业模块 · 餐饮门店 —— 用餐工结构漏损

这是**第二个实现**,它的作用是当对照组:
  餐饮算「工时冗余 × 小时成本」,物流算「单票差额 × 年件量」——
  算法完全不同,**却产出同一个 Case 形状**。这就证明了引擎是结构,不是套壳。

它包的是已有的 `fde_model.analyze()`,不重写逻辑。
"""

from __future__ import annotations

import fde_ask as _ask
import fde_bench as B
import fde_facts as FA
import fde_gate as G
import fde_issues as ISS
import fde_model as M
from fde_kernel import (ASSUMPTION, INTERVIEW, PUBLIC, Case, Evidence, Input, Metric)

INDUSTRY = "餐饮门店"
_MY_BENCH = B.INDUSTRIES[INDUSTRY]

INPUTS: list[Input] = [
    Input("store_count", "门店数", "家", 12, 1, 1, "你自己心里有数的数,不用报表"),
    Input("rev_per_store", "单店月流水", "元", 300000, 10000, 10000, "大概数就行"),
    Input("emp_per_store", "单店员工数", "人", 8, 1, 0.5, "全职 + 兼职都算"),
]

HERO = {
    "head": "同样一间店,你可能每年多付几十万工资。",
    "lead": "而这件事,<b>不用裁掉任何一个人</b>。",
    "sub": ("一个给连锁门店的<b>用工成本诊断台</b>。"
            "<b>不用你交任何内部数据</b> —— 只要三个你自己心里有数的数:"
            "几家店、每家店月流水多少、雇了多少人。"),
}

NEEDS_PART_TIME = True          # 这个行业还要问「兼职 / 小时工占比」

# ---------------------------------------------------------------- 界面的行业外壳
# 这三样原来写在 app.py 里(全局唯一一份,餐饮口径)——
# 换到物流时界面还是拿门店材料 + 排班问题。现在交给行业模块自己带。

SAMPLE_CAPTION = "↓ 脱敏后的门店群聊示例"

SAMPLE_MATERIAL = """王店长
2026年09月18日 09:12
我真排不过来了,12 家店的班表我一个人弄

李主管
2026年09月18日 09:15
你一周要花多久在这上面

王店长
2026年09月18日 09:16
至少一天吧，周一基本干不了别的

李主管
2026年09月18日 09:20
总部现在也没个准数，每家店到底排得合不合理看不出来

王店长
2026年09月18日 09:22
而且排完了店员老来问为什么这么排，我也说不出个所以然，只能重改

店员小张
2026年09月18日 12:40
店长我这个周末能不能不排晚班啊

王店长
2026年09月18日 12:41
我先看看

李主管
2026年09月18日 14:02
我们去年买过一套排班软件，没人用，最后就放着

王店长
2026年09月18日 14:05
主要是那个排出来的班我看不懂它为啥这么排

李主管
2026年09月18日 14:10
单店月流水差不多 30 万左右，一家店八个人

李主管
2026年09月18日 14:12
兼职现在很少，基本上都是全职

王店长
2026年09月18日 15:30
还有人说怕以后工时被压
"""

# 追问清单(key, 问法, 为什么问, 控件类型)
QUESTIONS = [
    ("part_time_ratio", "你们现在兼职 / 小时工大概占多少?",
     "这一项直接决定能不能算出准确的漏损区间 —— 也是唯一一个能把上面那个区间收窄一半的问题。", "slider"),
    ("who_does_it", "排班这件事,现在是谁在做?他一周大概花多久?",
     "我需要知道「谁」和「多久」—— 没有具体的人和小时数,后面全是空话。", "text"),
    ("how_measured", "现在有没有一个数,能证明排班是合理的?",
     "如果答案是「没有」,那正好 —— 立规矩这件事本身就是价值。", "text"),
    ("resister", "谁最不希望这件事被改?为什么?",
     "阻力通常不在技术里。这一问答完,契约第 03 条就能写实。", "text"),
    ("tried_before", "以前试过什么办法?为什么没成?",
     "别人踩过的坑,我不想让你再踩一遍。", "text"),
    ("internal_data", "能不能给我们一份脱敏的原始数据?(例如近 8 周的排班表)",
     "这是把结论从「方案设计」推到「可承诺」的唯一途径 —— 有了它,契约第 4 条的基线才站得住。", "text"),
]

# 提问计划用的话题库(餐饮就是 fde_ask 里那套默认库)
TOPICS = _ask.TOPICS

# 讨数据那句(写在契约页下一步里)
INTERNAL_ASK = "近 8 周排班表"


def _facts_from_answers(ans: dict) -> list:
    """没有材料时的兜底:把回答过的访谈变成**统一事实记录**,
    这样契约不会因为「没材料」而整段显示「未提供」。"""
    taken: set = set()
    out = []
    for key, label in (("who_does_it", "排班由谁承担"), ("tried_before", "过去尝试"),
                       ("resister", "现场阻力"), ("how_measured", "现有判断口径"),
                       ("internal_data", "甲方答复")):
        v = ans.get(key)
        if v in (None, ""):
            continue
        text = f"{label}:{v}"
        out.append(FA.Fact(id=FA._stable_id(text, taken), text=text, quote="",
                           locator="现场访谈", kind="访谈", source_type=FA.SRC_MATERIAL,
                           status=FA.ST_DIRECT, quote_ok=False,
                           support_status=FA.SUP_TODO, remainder=text))
    return out


def build_case(inputs: dict, ans: dict | None = None, facts=None, flags=None,
               state=None) -> Case:
    """inputs 三个数;ans 访谈答案;facts 统一事实记录;flags 证据标志(来自补充证据);
    state 门槛相关开关(baseline_present / caliber_aligned / pilot_defined /
    measured / approved / coverage_ok)。"""
    ans = dict(ans or {})
    flags = dict(flags or {})
    state = dict(state or {})
    facts = list(facts or [])
    if not facts:
        facts = _facts_from_answers(ans)
    facts = [f.to_dict() if hasattr(f, "to_dict") else f for f in facts]
    _objs = FA.as_facts(facts)              # 统一事实记录(槽位 / 覆盖率 / 门槛用)
    _sl = FA.slots(_objs)
    _cov_n, _cov_keys = FA.coverage(_objs)
    _neg_ev = ISS.b_counter_evidence(_objs)   # 「没有冗余」类反向证据(带层级)
    _neg_stop = any(e["level"] != ISS.LV_STMT for e in _neg_ev)

    p = ans.get("part_time_ratio")
    tp = ans.get("target_part_time")
    a = M.analyze(
        int(inputs.get("store_count") or 12),
        float(inputs.get("rev_per_store") or 300000),
        float(inputs.get("emp_per_store") or 8),
        float(p) if p is not None else None,
        industry=INDUSTRY,
        target_part_time=float(tp) if tp is not None else None,
    )

    _hyp_note = ""
    if _neg_stop:
        # 数据支持「无可释放工时」:计算结果允许为零,停止该改造建议;
        # 原来的假设区间降级为**独立假设模拟**(不适用当前客户,不作为推荐收益)。
        _hyp_note = (f"⚠️ 独立假设模拟(不适用于本客户):若不存在该反向证据,原公开基准区间约为 "
                     f"{M.money(a.struct_money_low)} – {M.money(a.struct_money_high)} 元/年 —— "
                     f"仅作对照演示,不作为本客户的推荐收益。")
        a.struct_hours_low = a.struct_hours_high = 0.0
        a.struct_money_low = a.struct_money_mid = a.struct_money_high = 0.0

    c = Case(industry=INDUSTRY, needs_part_time=True, scale_unit="门店")
    c.inputs_summary = (
        f"{a.store_count} 店 · 单店月流水 {M.money(a.rev_per_store)} 元 · 单店 {a.emp_per_store:g} 人"
    )
    c.facts = facts

    # ---------- 参数来源:材料预填 / 客户自报 / 默认假设(必须分得清)----------
    default_map = {i.key: i.default for i in INPUTS}
    _prefilled = set(state.get("prefilled_from_material") or [])
    all_customer, assumed = G.fields_from_customer(inputs, default_map)
    c.field_sources = {
        k: ("材料预填" if k in _prefilled else
            ("默认假设" if k in assumed else "客户自报"))
        for k in default_map}
    c.inputs_source_label = "、".join(dict.fromkeys(c.field_sources.values()))

    # ---------- 钱:工时与现金分开,且明确是「假设情景」----------
    c.revenue_stopped = _neg_stop
    c.revenue_label = ("该改造建议已停止(反向证据支持无可释放工时)"
                       if _neg_stop else "假设情景下的潜在优化空间(用工结构口径)")
    c.headline_low, c.headline_mid, c.headline_high = (
        a.struct_money_low, a.struct_money_mid, a.struct_money_high)
    c.headline_label = c.revenue_label
    c.hours_release_low, c.hours_release_high = a.struct_hours_low, a.struct_hours_high

    pos = M.position(a)
    target = M.BENCH["rev_per_hour_target"].value
    c.reference_note = (
        f"公开标杆是 **{target:.0f} 元/小时**,而行业均值约 **{pos['avg']:.0f} 元/小时**"
        f"(由人均产值 27 万元/年换算)。你现在是 **{a.rev_per_hour:,.0f} 元/小时** —— "
        f"{pos['tier']}。**指标高于标杆只说明人效不低,不能反推存在结构性漏损。**"
    )
    if _neg_stop:
        c.plain_line = ("客户补充的数据支持「无可释放工时」—— 该改造建议已停止;"
                        "原来的金额区间只保留为独立假设模拟,不再作为本客户的收益。")
    else:
        c.plain_line = (
            f"在假设全部当前全职工时都改成小时排班的前提下,平均每家店每年 "
            f"**{M.money(a.struct_money_low / a.store_count)} – "
            f"{M.money(a.struct_money_high / a.store_count)}** —— 这是**情景,不是承诺**。"
        )
    c.revenue_assumptions = [
        f"公开基准:同一家店从全职排班改成小时排班,当日总工时 198 → 137,即省下 "
        f"{M.LABOR_SHRINK:.1%}(由公开两端点线性推导)。**这是别人的店,不是本客户的实测。**",
        f"可释放工时的换算基数是**当前全职占比** {a.full_time_low:.0%}–{a.full_time_high:.0%}。",
        f"小时成本取公开区间 {M.BENCH['cost_low'].value:g}–{M.BENCH['cost_high'].value:g} 元/小时。",
        "月总工时按国家标准口径 174 小时/人计 —— 不是客户的实际工时。",
    ]
    if _hyp_note:
        c.revenue_assumptions.append(_hyp_note)
    c.revenue_conditions = [
        "**可释放工时 ≠ 可减少现金支出**:工时要真的从固定成本变成可变成本(按小时结算、"
        "没有工时下限承诺),换算成现金才成立。",
        "需要客户实际数据(近 8 周排班 + 考勤)把区间收窄,否则只能停在「假设情景」。",
        "算法需要客户确认:分时段没有硬性服务质量约束(如最低在岗人数)。",
        "工时口径 174 小时/人是国标估算,不是客户实际工时 —— 客户实际考勤数据到位后应替换重算。",
    ]
    c.revenue_formula = M.how_to_check(a)

    # ---------- 界面指标 ----------
    c.metrics = [
        Metric("每月付出去的总工时", f"{a.total_hours:,.0f}",
               help="店数 × 单店人数 × 174 小时(174 = 21.75 天 × 8 小时,国家标准口径)"),
        Metric("每人每小时产出", f"{a.rev_per_hour:,.0f} 元", delta=f"标杆 {target:.0f}",
               help="行业里叫「人时营业额」:门店营业额 ÷ 总工时。越高说明人用得越值。"),
        Metric("可释放工时(假设情景)" if not _neg_stop else "可释放工时(已停止)",
               (f"{a.struct_hours_low:,.0f} – {a.struct_hours_high:,.0f}" if not _neg_stop
                else "0"),
               help=("反向证据支持无可释放工时" if _neg_stop
                     else "按公开基准改成小时排班后、假设情景下可释放的工时 —— 不等于已省下的工资")),
    ]

    # ---------- 候选问题(不预设结论)----------
    c.candidates = ISS.build(INDUSTRY, c, _objs, ans, flags, a=a)
    c.candidate_note = ISS.overall(c.candidates)
    _cand_a = next((x for x in c.candidates if x["key"] == "A"), None)
    _cand_b = next((x for x in c.candidates if x["key"] == "B"), None)
    _b_state = (_cand_b or {}).get("status", "待判定")

    # ---------- 真问题:只是候选,不是结论 ----------
    c.truth_title = ("材料直接支持的是「排班耗时 / 解释困难 / 返工」;"
                     "「用工结构」仍只是待验证假设")
    if _b_state == ISS.S_STOP:
        _b_line = ("**反向证据(数据支持)表明无可释放工时** —— 该改造建议已停止,"
                   "不再作为本客户的推荐收益。")
    elif _b_state == ISS.S_COUNTER:
        _b_line = ("**材料里有反向证据(客户陈述)** —— 需先核实;核实前不把"
                   "「用工结构」当成问题,也不推进该改造。")
    elif _b_state == ISS.S_WEAK:
        _b_line = ("**当前证据不支持把「用工结构」当成问题** —— "
                   "建议暂不进行该改造,先把排班解释与返工这条做实。")
    else:
        _b_line = ("「用工结构可能存在优化空间」需要客户自己的分时段数据才能判断 —— "
                   "**指标高于标杆不能反推存在结构性漏损**。")
    c.truth_body = (
        f"这份文件**不预设**你的问题是用工结构。两件事分开说:\n\n"
        f"**A. 排班耗时、解释困难与返工** —— "
        f"{(_cand_a or {}).get('status', '待判定')}。\n\n"
        f"**B. 用工结构可能存在优化空间** —— {_b_state}。{_b_line}\n\n"
        f"{c.reference_note}\n\n"
        f"⚠️ 上半页那个金额是**假设情景下的潜在优化空间**,不是「你正在漏的钱」。\n"
        f"**可释放工时 ≠ 可减少现金支出**,两者不能自动画等号。"
    )

    # ---------- 验收标准(必须能判真假)----------
    def _fk(k: str, default: str = "") -> str:
        """访谈答案 or 材料事实,两个来源都看(材料里有就不显示「未提供」)。"""
        return str(ans.get(k) or (_sl.get(k) or {}).get("answer") or default).strip()

    _tried = _fk("tried_before", "既有排班软件")
    c.acceptance = [
        ("排班结果**可解释**:承担排班的人能对每一次排班当场说明理由(可抽查)",
         _fk("how_measured", "没有可核的排班理由记录"), INTERVIEW),
        (f"人时营业额 **≥ {a.rev_per_hour:,.0f} 元/小时**(不低于当前基线;"
         f"公开优秀标杆 {target:.0f})—— 仅作不劣化约束",
         f"{a.rev_per_hour:,.0f} 元/小时", INTERVIEW),
        ("若进入结构改造:**先在客户实际数据上取到基线**,再写占比目标"
         "(没有基线时不写「占比到多少」)",
         "未取得", INTERVIEW),
        ("门店人时营业额**可月度出数、口径可核**",
         _fk("how_measured", "未提供"), INTERVIEW),
    ]

    c.out_of_scope = [
        "不含薪资核算与考勤机对接",
        "不含跨店调岗审批流",
        f"不含「{_tried}」类方案的重复实施",
        "不含在证据不足时推进用工结构改造",
    ]

    c.deliverables = [
        "候选问题清单与每条的验证动作",
        "用工结构诊断报告(本契约 + 附录)",
        "小时排班模板(适配现有门店结构)",
        "验收测试报告(用第 04 条指标实测)",
        "一页操作说明",
    ]

    c.milestones = [
        ("D+3", "工时段基线 / 口径对齐(先取真实基线)", "运营负责人"),
        ("D+7", "选定 1 家店做试点(按候选问题定范围)", "运营负责人"),
        ("D+14", "指标复测(第 04 条)", "甲方负责人"),
    ]

    c.responsibilities = [
        ("近 8 周排班表 / 考勤原始数据(可脱敏)", "诊断与设计人力"),
        ("指定 1 名对接人(具决策权)", "上述全部交付物"),
        ("1 家试点门店", "每周一次进度同步"),
    ]

    c.risks = [
        (f"过去尝试过「{_tried}」但未成(落地失败线索,不是矛盾)",
         "重复失败", "先复盘上次失败点(通常卡在「不可解释」),再定试点范围", "双方"),
        (f"现场抵触:{_fk('resister') or '一线对排班变化有顾虑'}",
         "指标无法达成", "先做「建议 + 理由」而非「自动排定」", "运营负责人"),
        ("把「假设情景」当成「已确认收益」",
         "过度承诺", "全文标状态;缺基线时只出「试点设计草案」", "乙方"),
        ("工时口径与法定口径不一致", "基线不准", "先对齐 8 周数据口径再算基线", "乙方"),
    ]

    c.unknowns = [
        ("当前兼职 / 小时工占比", "决定可释放工时区间", INTERVIEW),
        ("各门店分时段真实工时与客流", "判断是否真的存在时段冗余", "内部数据"),
        ("一线是否接受小时排班", "采纳率", INTERVIEW),
        ("是否有工时下限的合规要求", "方案合法性", INTERVIEW),
        ("近 8 周排班表 / 考勤原始数据", "把结论从「方案设计」推到「可承诺」", "内部数据"),
    ]
    if p is not None:
        # 已答的参数不再列为「未知项」(避免旧结论残留)
        c.unknowns = [u for u in c.unknowns if u[0] != "当前兼职 / 小时工占比"]

    # ---------- 复算步骤 ----------
    c.recalc_steps = M.how_to_check(a)
    if _neg_stop:
        # 停止态:不展示 0–0 这类残数 —— 复算列改为「为什么停 + 如何重启」
        c.recalc_steps = [
            f"① 月总工时 = {a.store_count} 店 × {a.emp_per_store:g} 人 × {M.HOURS_PER_MONTH_FULLTIME:.0f} 小时 = {a.total_hours:,.0f} 工时(基础量,照旧可复算)",
            f"② 公开基准的 {M.LABOR_SHRINK:.1%} 可释放比例与小时成本,只在「存在冗余」时才适用。",
            "③ 反向证据支持「无可释放工时」—— 该改造建议已停止,不再给出金额区间。",
            "④ 若提供能推翻该反向证据的原始数据,再按原流程重新评估。",
        ]
        c.revenue_formula = list(c.recalc_steps)

    # ---------- 试点范围与停止条件(由候选问题与证据决定,不是写死的)----------
    if _neg_stop:
        c.pilot_scope = ("排班解释与返工试点:不做工时结构改造(反向证据支持无可释放工时),"
                         "只解决「排班可解释 + 减少返工」")
    elif _neg_ev or flags.get("no_space"):
        c.pilot_scope = ("排班解释与返工试点:用工结构改造暂停(反向证据待核实),"
                         "先解决「排班可解释 + 减少返工」")
    elif flags.get("redundancy_supported"):
        c.pilot_scope = ("单店验证:先从午市时段做用工结构试点,并同时观测服务质量约束"
                         "(最低在岗人数、出餐时效、满意度)")
    else:
        c.pilot_scope = "待补证据 —— 暂不定试点范围(缺分时段数据与基线)"
    if state.get("measured"):
        c.pilot_scope += ";已记录实测,可进入验收复核。"
    c.stop_condition = ("出现下列任一情况即停止该改造:①实测显示可释放工时接近 0;"
                       "②服务质量指标劣化;③一线抵触导致试运行无法持续;"
                       "④客户表示不批准/不签约。")

    # ---------- 证据链(重要判断都能回到支持它的那条事实)----------
    _p_now = ans.get("part_time_ratio")
    if _p_now is not None:
        _p_txt = (f"{float(_p_now):.0%}(客户自报;可释放工时的换算基数 = "
                  f"全职占比 {a.full_time_low:.0%}–{a.full_time_high:.0%})")
    else:
        _p_txt = (f"未取得 —— 按假设区间 {a.p_range[0]:.0%}–{a.p_range[1]:.0%} 扫描"
                  f"(换算基数 = 全职占比 {a.full_time_low:.0%}–{a.full_time_high:.0%})")
    c.evidence = [
        Evidence("E1", f"月总工时 = {a.store_count} × {a.emp_per_store:g} × 174 = {a.total_hours:,.0f} 工时",
                 "客户自报参数 + 国家标准月计薪口径", INTERVIEW, "中"),
        Evidence("E2", f"用工结构可释放 {_MY_BENCH['labor_shrink'].value:.1%} 工时",
                 "公开对比数据 198 → 137 工时(线性推导;**别人的店,不是本客户实测**)", PUBLIC, "中"),
        Evidence("E3", f"用工成本 {_MY_BENCH['cost_low'].value:g}–{_MY_BENCH['cost_high'].value:g} 元/小时",
                 _MY_BENCH["cost_mid"].source, PUBLIC, "中"),
        Evidence("E4", f"人时营业额标杆 {target:.0f} 元/小时(仅作定位参照,不能反推漏损)",
                 _MY_BENCH["rev_per_hour_target"].source, PUBLIC, "中"),
        Evidence("E5", f"当前兼职/小时工占比:{_p_txt}",
                 "客户自报" if a.p_confirmed else "未取得 —— 按自定假设区间扫描",
                 INTERVIEW if a.p_confirmed else ASSUMPTION,
                 "中" if a.p_confirmed else "低"),
    ]
    # 材料/访谈已明确的事实:一句话一条,带稳定 ID(契约里可回指到同一份数据)
    for _k, _label in (("who_does_it", "承担者"), ("tried_before", "失败经历"),
                       ("resister", "现场阻力"), ("how_measured", "现有口径")):
        _s = _sl.get(_k)
        if _s:
            c.evidence.append(Evidence(
                str(_s["fact_id"]), f"{_label}:{_s['answer']}",
                f"客户材料 · 原句「{(_s.get('quote') or '')[:48]}」", INTERVIEW, "中"))
    if not _sl.get("tried_before"):
        c.evidence.append(Evidence("E6", "过去尝试过什么:未提供 —— 需向甲方补",
                                   "现场访谈", INTERVIEW, "低"))

    # ---------- 证据门槛:状态是**算出来的**,不由模型或措辞升级 ----------
    _assumed_eff = [k for k in assumed if k not in _prefilled]
    _all_customer = len(_assumed_eff) == 0
    _ans_keys = [k for k in ("who_does_it", "tried_before", "resister",
                             "how_measured") if ans.get(k)]
    _coverage_ok = bool(state.get("coverage_ok",
                      _cov_n >= 3 or len(_ans_keys) >= 3))
    _has_material = bool(state.get("has_material",
                       any(f.get("quote_ok") for f in facts)))
    _g = G.evaluate(G.GateInput(
        has_material=_has_material,
        fields_from_customer=bool(state.get("fields_from_customer", _all_customer)),
        baseline_present=bool(state.get("baseline_present", _all_customer)),
        caliber_aligned=bool(state.get("caliber_aligned", _all_customer)),
        coverage_ok=_coverage_ok,
        pilot_defined=bool(state.get("pilot_defined",
                         bool(flags.get("redundancy_supported") or flags.get("no_space")))),
        measured=bool(state.get("measured", False)),
        approved=bool(state.get("approved", False)),
    ))
    _demo_bits = []
    if state.get("demo_source"):
        _demo_bits.append("预跑结果(离线演示数据)")
    if state.get("synthetic_applied"):
        _demo_bits.append("合成情景补充证据")
    if _demo_bits:
        _g.reasons.append("⚠️ 本次证据推进包含 " + " + ".join(_demo_bits) +
                          " —— 非真实客户数据,仅用于演示;真实推进需要客户实际数据到位。")
    c.gate_state = _g.state
    c.gate_reasons = list(_g.reasons)
    c.gate_missing = list(_g.missing)
    c.gate_can = list(_g.can)
    c.gate_cannot = list(_g.cannot)
    c.approved = _g.approved
    c.gate = _g.state                      # 兼容旧字段:同一份状态
    c.gate_gap = "；".join(_g.missing) if _g.missing else "无"

    # ---------- 附录 E:基准对照 ----------
    for b in _MY_BENCH.values():
        c.bench_rows.append((b.group, b.label, B.fmt_value(b), b.source))

    fp = _MY_BENCH["flex_penetration"]
    c.caveats = [
        f"**「灵活用工渗透率 {fp.value:g}%」不是兼职员工占比。** 它指的是「多少企业采用了灵活用工」,"
        f"与「兼职员工占总员工数的比例」是完全不同的两个量。本契约**没有**用它来估算兼职占比。",
        "**招聘 / 流失成本不能与用工结构漏损相加。** 二者机制不同,能叠加属于两个不同动作的结果。",
    ]
    c.side_title = "另一条线(仅作参考,不计入上面区间)"
    hr = _MY_BENCH["turnover_server"]
    hc = _MY_BENCH["hire_cost_ratio"]
    c.side_line = (
        f"若店长/服务员离职率接近公开均值({hr.value:g}% 服务员 / 30%+ 店长),"
        f"招聘侧还有一笔可计量的成本:单店招聘成本约占月营收 {hc.value:g}%–6%。"
        f"**这笔钱要靠降低离职率来省,不是靠排班 —— 不在本契约范围内。**"
    )
    return c


if __name__ == "__main__":
    case = build_case({"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8},
                      {"part_time_ratio": 0.27})
    print("行业:", case.industry)
    print("年化:", case.money_range())
    print("参照系:", case.reference_note)
    print("人话:", case.plain_line)
    print("证据条数:", len(case.evidence), " / 基准行:", len(case.bench_rows))
