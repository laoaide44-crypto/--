"""
行业模块 · 快递物流 —— 单票成本诊断

与餐饮那套完全不同的算法,但产出同一个 Case 形状。
  餐饮:算「工时冗余 × 小时成本」
  物流:算「单票成本与同行的差距 × 年件量」

⚠️ 口径纪律(这个行业最要紧的三条):
  1. **不重复计算**:「与同行的差距」和「AI 能省多少」在机制上是同一笔钱的两面
     —— 后者是前者的「怎么补上」,不是另加一笔。所以主线只算差额,AI 那条只作路径。
  2. **行业平均单票收入(7.69)与通达系(2.17)不是同一个量**,不可互相代入。
  3. **财报口径 ≠ 网点口径**。上市公司财报是总部口径(含中转、干线),
     一个加盟网点的「综合成本」含不含派费、场地、折旧,差别很大 ——
     所以差额本身要标成「口径待对齐」。
"""

from __future__ import annotations

from fde_ask import ASK, INTERNAL, Topic

import fde_bench as B
from fde_kernel import (ASSUMPTION, INTERVIEW, PUBLIC, Case, Evidence, Input, Metric)

INDUSTRY = "快递物流"

INPUTS: list[Input] = [
    Input("parcels_per_day", "日均件量", "票/日", 30000, 100, 1000,
          "你自己心里有数的数,不用报表"),
    Input("cost_per_parcel", "你的单票综合成本", "元/票", 2.05, 0.5, 0.01,
          "含不含派费都行,但要和你自己平时的口径一致"),
    Input("sites", "网点 / 分拨场站数", "个", 8, 1, 1, "用于把年化金额摊到单个场站"),
]

# 开场文案 —— 行业感知的。
# 设计:H1 用**参照系**让数字显得有分量(一票只赚两毛七),
#       具体多少钱留给第一屏的绝对量。
HERO = {
    "head": "一票快递的毛利,只有两毛七。",
    "lead": "而在这一票上,成本差一毛五 —— <b>就是半票的毛利</b>。",
    "sub": ("一个给快递网点 / 分拨中心的<b>单票成本诊断台</b>。"
            "<b>不用你交任何内部数据</b> —— 只要三个你自己心里有数的数:"
            "日均件量、单票综合成本、几个场站。"),
}

# ---------------- 公开基准(全部来自 fde_bench 的快递物流组)----------------
def _b(key: str) -> float:
    """读**本行业自己的**基准。
    不能用 B.BENCH —— 那是「当前选中行业」的视图,默认是餐饮,
    行业模块不能依赖全局选择状态。"""
    return _MY_BENCH[key].value


_MY_BENCH = B.INDUSTRIES[INDUSTRY]


REF_COST_NOTE = "通达系口径(圆通 2026H1),总部口径,含运输与中心操作"
REF_DELTA = 0.05          # 对公开参照值 ±5% 的口径不确定带(**自定假设**)


# ---------------------------------------------------------------- 界面的行业外壳
# 原来这三样写在 app.py 里(全局一份、餐饮口径)——切到物流时
# 示例材料还是门店群聊、追问还是排班,与「行业感知」自相矛盾。

SAMPLE_CAPTION = "↓ 脱敏后的网点群聊示例(快递)"

SAMPLE_MATERIAL = """刘站长
2026年09月19日 08:41
这个月对账又对到现在,我一个人拉了三天表

财务小陈
2026年09月19日 08:46
单票成本我这边没算过,就一个总数,分不出来贵在哪一段

刘站长
2026年09月19日 08:50
派费、场地这些到底算在哪一档,我自己也说不清

分拨老周
2026年09月19日 09:02
前年上过一套成本分析的系统,报表看不懂,最后就放着没人用了

派件员老赵
2026年09月19日 12:30
就怕又跟去年一样,从派费里往下抠

刘站长
2026年09月19日 14:20
台账在系统里,真要的话得让技术那边弄出来

财务小陈
2026年09月19日 14:26
日均三万票上下,忙的时候四万
"""

# 追问清单(key, 问法, 为什么问, 控件类型)
QUESTIONS = [
    ("cost_basis", "你们现在说的「单票成本」,里面含了哪些?(派费 / 场地租金 / 车辆折旧 / 中转)",
     "这一项直接决定差额有多大 —— 财报是总部口径,合不合得上全看这一问。", "text"),
    ("how_measured", "现在有没有在算单票成本?算的话口径是什么?",
     "如果只是一个总数,那「贵在哪一段」就永远看不见 —— 立口径本身就是价值。", "text"),
    ("internal_data", "能不能给我们一份脱敏的近 30 天件量与成本数据?",
     "这是把结论从「方案设计」推到「可承诺」的唯一途径 —— 有了它,第 04 条的基线才站得住。", "text"),
    ("who_does_it", "算成本这件事,现在是谁在做?一个月大概花多久?",
     "我需要知道「谁」和「多久」—— 没有具体的人和工时,后面全是空话。", "text"),
    ("resister", "如果按这个方向改,谁最不希望?为什么?",
     "这一行的阻力通常不在技术里。这一问答完,契约第 05 条(不压派费)才有依据。", "text"),
    ("tried_before", "以前试过什么办法?为什么没成?",
     "别人踩过的坑,我不想让你再踩一遍。", "text"),
]

# 提问计划用的话题库 —— 物流自己一套,与餐饮不同(没有「兼职占比」这一问)
TOPICS = [
    Topic(
        key="cost_basis",
        question="你们现在说的「单票成本」,里面含了哪些?(派费 / 场地租金 / 车辆折旧 / 中转)",
        why="财报是总部口径,网点口径含不含派费/场地/折旧,直接决定差额大小",
        impact="口径对不上,后面那个区间就是粗的 —— 对齐前不进承诺",
        how=ASK, must_in_person=True, score=100,
        need_kw=["派费", "场地", "折旧", "中转", "口径"],
        need_strong=["含不含", "算不算", "说法都不一样", "算法都不一样",
                     "口径对不上", "对齐口径"],
    ),
    Topic(
        key="how_measured",
        question="现在有没有在算单票成本?算的话口径是什么?",
        why="契约的验收标准必须能判真假;没有基线就没法立标准",
        impact="决定契约第 04 条能不能写出来 —— 写不出就没有可验收的承诺",
        how=ASK, must_in_person=True, score=90,
        need_kw=["指标", "口径", "标准", "算好", "成本", "算过"],
        need_strong=["单票成本算出来", "分开出数", "成本分开算",
                     "每月出一次单票成本"],
    ),
    Topic(
        key="internal_data",
        question="能不能给我们一份脱敏的近 30 天件量与成本数据?",
        why="这是把结论从『方案设计』推到『可承诺』的唯一途径",
        impact="没有它,契约只能停在「可进入方案设计」—— 我们不给承诺",
        how=INTERNAL, must_in_person=True, score=85,
        need_kw=["台账", "导出", "明细", "系统", "报表"],
        need_strong=["近 30 天", "近三十天", "发你", "你拉一份", "数据给你"],
    ),
    Topic(
        key="who_does_it",
        question="算成本这件事,现在是谁在做?一个月大概花多久?",
        why="没有具体的人和工时,后面全是空话",
        impact="决定契约第 03 条(谁受益)和第 08 条(谁提供什么)",
        how=ASK, must_in_person=False, score=70,
        need_kw=["谁做", "负责", "算成本", "对账", "财务"],
        need_strong=["我一个人", "拉了三天", "花了两天", "一个月一次"],
    ),
    Topic(
        key="resister",
        question="如果按这个方向改,谁最不希望?为什么?",
        why="阻力通常不在技术里,而它会决定项目能不能落地",
        impact="决定契约第 05 条(不压派费)和第 09 条(风险登记)",
        how=ASK, must_in_person=True, score=65,
        need_kw=["不希望", "反对", "抵触", "担心", "怕", "不愿意"],
        need_strong=["从派费里往下抠", "压派费", "怕压派费", "担心压派费",
                     "不干了", "没人愿意干"],
    ),
    Topic(
        key="tried_before",
        question="以前试过什么办法?为什么没成?",
        why="别人踩过的坑,不该再踩一遍",
        impact="决定契约第 09 条(风险应对)与试点范围",
        how=ASK, must_in_person=False, score=55,
        need_kw=["试过", "上过", "装过", "以前", "之前", "用过", "系统"],
        need_strong=["上过一套", "没人用", "闲置", "最后就放着", "用不起来"],
    ),
]

# 讨数据那句(写在契约页下一步里)
INTERNAL_ASK = "近 30 天件量与成本原始数据"


def build_case(inputs: dict, ans: dict | None = None, facts=None, flags=None,
               state=None) -> Case:
    ans = ans or {}
    parcels = float(inputs.get("parcels_per_day") or 30000)
    cost = float(inputs.get("cost_per_parcel") or 2.05)
    sites = max(1.0, float(inputs.get("sites") or 1))

    yearly = parcels * 365.0                       # 票/年
    ref = _b("kdt_cost_per_piece")                 # 1.90
    ref_lo, ref_hi = ref * (1 - REF_DELTA), ref * (1 + REF_DELTA)

    gap_mid = cost - ref
    gap_hi = cost - ref_lo                         # 参照取低 → 差额大
    gap_lo = cost - ref_hi                         # 参照取高 → 差额小

    c = Case(industry=INDUSTRY, scale_unit="场站")

    # ---------- 参照系:这个数在快递这个行业里有多大 ----------------
    gross = _b("kdt_gross_per_piece")              # 单票毛利 0.27
    ratio = (gap_mid / gross) if gap_mid > 0 else 0.0
    if gap_mid > 0:
        c.reference_note = (
            f"快递一票的毛利只有 **{gross:.2f} 元**(圆通 2026H1)。"
            f"你比参照高出的 **{gap_mid:.2f} 元**,相当于单票毛利的 **{ratio:.0%}** —— "
            f"在一个薄利行业里,这个量级不是零钱。"
        )
        c.truth_title = "真问题不在件量,在单票成本"
        c.truth_body = (
            f"按你自己的数算,你的单票综合成本 **{cost:.2f} 元**,"
            f"公开参照是 **{ref:.2f} 元**({REF_COST_NOTE})。"
            f"差额 **{gap_mid:.2f} 元/票**,乘上你 **{yearly:,.0f} 票/年**的年件量,"
            f"就是下面这个数。\n\n"
            f"⚠️ **口径待对齐**:财报是总部口径,你的「综合成本」含不含派费/场地/折旧,"
            f"会直接影响差额 —— **这条必须在第一次会上对齐,否则这个数不能签字**。"
        )
    else:
        c.reference_note = (
            f"你的单票综合成本 **{cost:.2f} 元**,已经低于公开参照 **{ref:.2f} 元**。"
            f"**所以你这条线不适用** —— 我们不硬给你造一个缺口。"
        )
        c.truth_title = "单票成本已在参照之下,问题换一个方向"
        c.truth_body = (
            f"你的单票成本低于公开参照 **{abs(gap_mid):.2f} 元/票**。这意味着"
            f"「和同行比」这条线对你没意义 —— 该看的是别的:件量结构、时效与破损的性价比,"
            f"或者把已经做到的成本优势换成价格与份额。\n\n"
            f"**我们不把你比同行好的地方算成一笔「省下的钱」。**"
        )

    # ---------- 主线的钱 ----------
    if gap_mid > 0:
        c.headline_low = max(0.0, gap_lo) * yearly
        c.headline_mid = gap_mid * yearly
        c.headline_high = max(0.0, gap_hi) * yearly
        c.headline_label = "按你的年件量折算,与公开参照的年度成本差距"
    else:
        c.headline_low = c.headline_mid = c.headline_high = 0.0
        c.headline_label = "单票成本低于参照,不产生成本差距(这条线不适用)"

    # ---------- 界面指标 ----------
    c.metrics = [
        Metric("年件量", f"{yearly:,.0f} 票",
               help=f"日均 {parcels:,.0f} 票 × 365 天"),
        Metric("你的单票成本", f"{cost:.2f} 元", delta=f"参照 {ref:.2f}",
               help="你自己报的口径。要和参照比,必须先对齐口径。"),
        Metric("每票高出", f"{max(0.0, gap_mid):.2f} 元",
               help=f"参照区间 {ref_lo:.2f}–{ref_hi:.2f} 元(±{REF_DELTA:.0%} 口径不确定带,自定假设)"),
    ]
    c.plain_line = (
        f"摊到 {sites:.0f} 个场站,平均每个场站每年 "
        f"**{c.headline_low / sites / 10000:.1f} 万 – {c.headline_high / sites / 10000:.1f} 万**。"
    )

    # ---------- 复算步骤(客户自己能按计算器核)----------------
    c.recalc_steps = [
        f"① 你的年件量 = 日均 {parcels:,.0f} 票 × 365 天 = **{yearly:,.0f} 票**",
        f"② 公开参照单票成本 = **{ref:.2f} 元/票**(圆通 2026H1,通达系口径)",
        f"③ 你的单票成本 {cost:.2f} − 参照 {ref:.2f} = **{gap_mid:.2f} 元/票**",
        f"④ 乘上 ①:{gap_mid:.2f} × {yearly:,.0f} = **{c.headline_mid:,.0f} 元/年**",
        f"⑤ 区间来自参照值 ±{REF_DELTA:.0%} 的口径不确定带(自定假设,不是公开数据)",
        "⑥ 任何一步你都可以自己按计算器重算 —— 出处就在下面,能点开看",
    ]

    # ---------- 路径:同行是怎么做到的(⚠️ 不是另一笔钱)----------
    ai_per_parcel = _b("kdt_ai_transport_saving") + _b("kdt_ai_hub_saving")   # 0.11+0.04
    ai_year = ai_per_parcel * yearly
    c.truth_body += (
        f"\n\n**同行是怎么把成本压下来的?** 圆通公开披露:对比 AI 规模化应用之前的 2023H1,"
        f"**单票运输成本降 {_b('kdt_ai_transport_saving'):.2f} 元、中心操作成本降 "
        f"{_b('kdt_ai_hub_saving'):.2f} 元**,合计 **{ai_per_parcel:.2f} 元/票**。"
        f"按你的件量算相当于 **{ai_year:,.0f} 元/年**。\n\n"
        f"⚠️ **注意:这不是第二笔钱。** 它就是上面那个缺口「怎么补上」的一条路径 —— "
        f"两者在机制上是同一笔钱,相加会虚高。而且 {ai_per_parcel:.2f} 元是企业自述口径、"
        f"是 AI 规模化之后的成效,**不是一次就能拿到,更不是我们的承诺**。"
    )

    # ---------- 验收标准(必须能判真假)----------
    target = ref
    c.acceptance = [
        (f"单票综合成本从 {cost:.2f} 元降到 **≤ {target:.2f} 元**(在最近 30 天真实件量与成本数据上测)",
         f"{cost:.2f} 元", INTERVIEW),
        ("单票运输成本与中心操作成本**分开出数**,口径可核", "合并口径", INTERVIEW),
        ("连续 14 天:出件时效与破损率**不劣化**(不允许靠牺牲质量降本)", "待取基线", PUBLIC),
    ]

    c.out_of_scope = [
        "不含面单 / 系统对接改造",
        "不含网点加盟合同与派费政策调整",
        "不含历史数据迁移(只用近 30 天做基线)",
        "**不含压派费**:不从一线的派费里省成本",
    ]

    c.deliverables = [
        "单票成本诊断报告(本契约 + 附录)",
        "成本口径对齐表(你的口径 vs 财报口径)",
        "可复算的测算文件(你改一个数,结果自己变)",
        "验收测试报告(用上面第 04 条的指标实测)",
    ]

    c.milestones = [
        ("D+3", "口径对齐 + 基线复算", "你方运营负责人"),
        ("D+10", "一个场站试跑", "你方运营负责人"),
        ("D+30", "指标复测(第 04 条)", "你方负责人"),
    ]

    c.responsibilities = [
        ("近 30 天件量与成本原始数据(可脱敏)", "诊断与测算人力"),
        ("指定 1 名对接人(具决策权)", "上述全部交付物"),
        ("1 个试点场站", "每周一次进度同步"),
    ]

    c.risks = [
        ("财报口径 ≠ 网点口径,差额可能被口径吃掉",
         "结论站不住", "先做口径对齐表,对齐前这个数不进承诺", "双方"),
        ("把降本做成了压派费", "一线流失、投诉上升",
         "契约第 05 条已明确排除;试点期监控派费与流失", "你方 HR"),
        ("AI 降本幅度是企业自述,不代表你能拿到",
         "预期落差", "把它当目标而非承诺;试点用你自己的数据说话", "双方"),
    ]

    c.unknowns = [
        ("你的「综合成本」含不含派费、场地、折旧?", "直接决定差额大小和可比性", INTERVIEW),
        ("件量结构:电商件 / 时效件 / 跨境各占多少?", "不同结构参照系不同", INTERVIEW),
        ("现在有没有在算单票成本?算的话口径是什么?", "决定基线从哪来", INTERVIEW),
        ("近 30 天的件量与成本原始数据", "把结论从「方案设计」推到「可承诺」", "内部数据"),
    ]

    # ---------- 证据链 ----------
    c.evidence = [
        Evidence("E1", f"年件量 = {parcels:,.0f} × 365 = {yearly:,.0f} 票",
                 "客户自报日均件量 + 常识口径(365 天)", INTERVIEW, "中"),
        Evidence("E2", f"通达系单票成本参照 {ref:.2f} 元",
                 _MY_BENCH["kdt_cost_per_piece"].source, PUBLIC, "中"),
        Evidence("E3", f"单票毛利参照 {gross:.2f} 元(用作参照系)",
                 _MY_BENCH["kdt_gross_per_piece"].source, PUBLIC, "中"),
        Evidence("E4", f"AI 降本参照 {ai_per_parcel:.2f} 元/票",
                 "圆通公开披露(对 2023H1);企业自述口径,未经审计", PUBLIC, "中低"),
        Evidence("E5", f"你的单票综合成本 {cost:.2f} 元(自报)",
                 "客户自报,**口径未对齐**", INTERVIEW, "低—中"),
        Evidence("E6", f"参照 ±{REF_DELTA:.0%} 的不确定带",
                 "本作品自定假设,无公开数据支撑", ASSUMPTION, "低"),
    ]

    # ---------- 输入来源与摘要(与餐饮同口径:材料预填 / 客户自报 / 默认假设)----------
    import fde_gate as _G0
    _inputs_map = {i.key: i.default for i in INPUTS}
    _pre_filled = set((state or {}).get("prefilled_from_material") or [])
    _all_c, _assumed = _G0.fields_from_customer(inputs, _inputs_map)
    c.field_sources = {
        k: ("材料预填" if k in _pre_filled else
            ("默认假设" if k in _assumed else "客户自报"))
        for k in _inputs_map}
    c.inputs_source_label = "、".join(dict.fromkeys(c.field_sources.values()))
    c.inputs_summary = (
        f"日均 {parcels:,.0f} 票 · 单票综合成本 {cost:.2f} 元 · {sites:.0f} 个场站")

    # ---------- 证据门槛(与其他行业同一套规则;状态由可检查条件计算)----------
    import fde_facts as _FA
    import fde_gate as _G
    _raw = facts or []
    _objs = _FA.as_facts(_raw)
    _cov = _FA.coverage(_objs)[0]
    _ans_keys = [k for k in ("who_does_it", "tried_before", "resister",
                             "how_measured") if (ans or {}).get(k)]
    _g = _G.evaluate(_G.GateInput(
        has_material=bool((state or {}).get("has_material",
                         any(f.quote_ok for f in _objs))),
        fields_from_customer=bool((state or {}).get("fields_from_customer", False)),
        baseline_present=bool((state or {}).get("baseline_present", False)),
        caliber_aligned=bool((state or {}).get("caliber_aligned", False)),
        coverage_ok=bool((state or {}).get("coverage_ok", _cov >= 3 or len(_ans_keys) >= 3)),
        pilot_defined=bool((state or {}).get("pilot_defined", False)),
        measured=bool((state or {}).get("measured", False)),
        approved=bool((state or {}).get("approved", False)),
    ))
    _demo_bits = []
    if (state or {}).get("demo_source"):
        _demo_bits.append("预跑结果(离线演示数据)")
    if (state or {}).get("synthetic_applied"):
        _demo_bits.append("合成情景补充证据")
    if _demo_bits:
        _g.reasons.append("⚠️ 本次证据推进包含 " + " + ".join(_demo_bits) +
                          " —— 非真实客户数据,仅用于演示;真实推进需要客户实际数据到位。")
    c.facts = [f.to_dict() if hasattr(f, "to_dict") else f for f in _raw]
    c.gate_state = _g.state
    c.gate_reasons = list(_g.reasons)
    c.gate_missing = list(_g.missing)
    c.gate_can = list(_g.can)
    c.gate_cannot = list(_g.cannot)
    c.approved = _g.approved
    c.gate = _g.state
    c.gate_gap = "；".join(_g.missing) if _g.missing else "无"

    # ---------- 附录 E:基准对照 ----------
    for b in _MY_BENCH.values():
        c.bench_rows.append((b.group, b.label, B.fmt_value(b), b.source))

    c.caveats = [
        "**行业平均单票收入与通达系单票收入不是同一个量** —— "
        "前者含顺丰 / 时效件 / 跨境,不可互相代入。",
        "**财报口径 ≠ 网点口径** —— 上市公司是总部口径(含中转、干线),"
        "你报的「综合成本」含不含派费 / 场地 / 折旧,差别很大。",
        "**「AI 降本幅度」与「与同行的差距」是同一笔钱的两面** —— 相加会虚高。",
    ]
    return c


if __name__ == "__main__":
    case = build_case({"parcels_per_day": 30000, "cost_per_parcel": 2.05, "sites": 8})
    print("行业:", case.industry)
    print("年化差距:", case.money_range())
    print("参照系:", case.reference_note)
    print("人话:", case.plain_line)
