"""
公开基准库(第二批已扩充)—— 这个作品的地基。

设计约束(来自产品设计):
  1. 每一个数字都必须带【出处】和【来源等级】,界面上要显示给客户看。
  2. 客户必须能自己核一遍 —— 这是"认可"的唯一来源。
  3. 全部是可公开查证的口径,不含任何客户内部数据。

来源等级:
  PUBLIC     = 公开报道/报告/财报(需标出处,可信度上限:中)
  INTERVIEW  = 现场访谈(只有到场才有)
  INTERNAL   = 客户内部数据(只有客户能给)
  ASSUMPTION = 没有公开数据,我自己的假设(必须显式声明)

⚠️ 口径纪律:不同来源的数字不可混用。例如「灵活用工渗透率」是**企业采用比例**,
   不是「兼职员工占员工总数的比例」—— 两个完全不同的量,混用会算错。
"""

from dataclasses import dataclass

PUBLIC, INTERVIEW, INTERNAL, ASSUMPTION = "PUBLIC", "INTERVIEW", "INTERNAL", "ASSUMPTION"

# ---------------------------------------------------------------- 来源
SRC_LABOR = "《人效提升30%?高效排班是杠杆》· 餐饮老板内参,2026-03-16,腾讯新闻"
SRC_LABOR_URL = "https://news.qq.com/rain/a/20260316A07EKP00"
SRC_LABOR_CAVEAT = "⚠️ 原文为课程招生文章,案例数字带营销属性,未经审计。仅作量级参考。"

SRC_HR = "[蚂蚁HR]《2025年中国餐饮业人力资源白皮书》"
SRC_HR_CAVEAT = "商业机构白皮书,口径自述,未经第三方审计。相对课程招生文更正式。"

SRC_HC = "《2026年中国餐饮行业报告》· 勤策消费研究(数据源:红餐大数据 / 国家统计局)"
SRC_HC_CAVEAT = ""

SRC_SELF = "本作品自定假设,无公开数据支撑"


@dataclass(frozen=True)
class Bench:
    key: str
    label: str
    value: float
    unit: str
    source: str
    tier: str = PUBLIC
    caveat: str = ""
    group: str = "其他"


BENCH: dict[str, Bench] = {}

def _add(b: Bench) -> Bench:
    BENCH[b.key] = b
    return b


# ================================================================ 用工结构
_add(Bench("hours_fulltime", "全职工排班 · 当日总工时(高峰需22人的门店)", 198.0, "工时/日",
           SRC_LABOR, caveat=SRC_LABOR_CAVEAT, group="用工结构"))
_add(Bench("hours_hourly", "小时排班 · 当日总工时(同一门店)", 137.0, "工时/日",
           SRC_LABOR, caveat=SRC_LABOR_CAVEAT, group="用工结构"))
_add(Bench("labor_shrink", "用工结构可释放工时比例(全职→小时排班)", round(1 - 137.0 / 198.0, 4), "比值",
           f"由 137/198 推导 · {SRC_LABOR}",
           caveat="线性推导,非原文直接给出。原文仅给两端点数值。", group="用工结构"))

# ================================================================ 用工成本
_add(Bench("cost_low", "小时用工成本 · 下沿", 25.0, "元/小时", SRC_LABOR,
           caveat=SRC_LABOR_CAVEAT, group="用工成本"))
_add(Bench("cost_mid", "小时用工成本 · 参考", 30.0, "元/小时", SRC_LABOR,
           caveat=SRC_LABOR_CAVEAT, group="用工成本"))
_add(Bench("cost_high", "小时用工成本 · 上沿", 35.0, "元/小时", SRC_LABOR, group="用工成本"))
_add(Bench("hourly_wage_range", "灵活用工时薪区间", 20.0, "元/小时(20–28;一线 28–35)", SRC_HR,
           caveat="白皮书口径。高于此区间说明你的招工价格已溢价。", group="用工成本"))
_add(Bench("daily_wage_parttime", "兼职服务员日薪", 90.0, "元/日(90–180)", SRC_HR, group="用工成本"))
_add(Bench("avg_wage", "餐饮业平均工资", 5100.0, "元/月", SRC_HR,
           caveat="低于全国城镇非私营单位约 50%。", group="用工成本"))
_add(Bench("cost_per_head_tier1", "一线城市单员工综合成本", 6500.0, "元/月(下限)", SRC_HR,
           caveat="含社保等综合成本,非到手工资。", group="用工成本"))
_add(Bench("labor_cost_ratio", "人力成本占营收比例(2024 均值)", 22.20, "%", SRC_HC,
           caveat="同行口径:原料进货 42.10%、房租物业 9.70%。", group="成本结构"))

# ================================================================ 人效
_add(Bench("rev_per_hour_target", "人时营业额 · 行业较好门店标杆", 180.0, "元/小时",
           SRC_LABOR, caveat=SRC_LABOR_CAVEAT, group="人效"))
_add(Bench("rev_per_hour_floor", "人时营业额 · 疑似亏损线", 100.0, "元/小时",
           SRC_LABOR, caveat=SRC_LABOR_CAVEAT, group="人效"))
_add(Bench("output_per_head", "人均产值(行业均值)", 270_000.0, "元/年", SRC_HR,
           caveat="由 2023 年 25.4 万元增至 2024 年约 27 万元。换算约 129 元/小时(27万÷12÷174)。",
           group="人效"))

# ================================================================ 流失与招聘
_add(Bench("turnover_server", "服务员年离职率", 89.47, "%/年", SRC_HR, group="流失与招聘"))
_add(Bench("turnover_manager", "店长年离职率", 30.0, "%/年(30%+)", SRC_HR, group="流失与招聘"))
_add(Bench("hire_cycle_manager", "店长岗位招聘周期", 55.0, "天(55+)", SRC_HR, group="流失与招聘"))
_add(Bench("hire_cost_ratio", "单店招聘成本占月营收", 3.0, "%(3–6)", SRC_HR, group="流失与招聘"))
_add(Bench("talent_gap", "行业年均人才缺口", 1_800_000.0, "人(180–200 万)", SRC_HR, group="流失与招聘"))

# ================================================================ 合规与结构
_add(Bench("compliance_uplift", "社保入税带来的合规成本增幅", 8.0, "%(8–12)", SRC_HR, group="合规与结构"))
_add(Bench("flex_penetration", "灵活用工渗透率(⚠️ 企业采用比例,非人数占比)", 27.0, "%", SRC_HR,
           caveat="⚠️ 口径陷阱:这是「多少企业采用了灵活用工」,不是「兼职员工占员工总数的比例」。"
                  "两者完全不同,不可互相代入。", group="合规与结构"))
_add(Bench("compliance_risk_share", "深陷合规风险的灵活用工企业比例", 40.0, "%", SRC_HR, group="合规与结构"))
_add(Bench("staff_total", "餐饮业从业人员总量", 21_500_000.0, "人(约 2150 万)", SRC_HR, group="合规与结构"))
_add(Bench("chain_rate", "餐饮连锁化率", 23.0, "%", SRC_HR, group="合规与结构"))

# ---------------------------------------------------------------- 月工时
HOURS_PER_MONTH_FULLTIME = 174.0
HOURS_PER_MONTH_SRC = "国家标准口径:月计薪天数 21.75 天 × 8 小时 = 174 小时"

# ---------------------------------------------------------------- 兼容导出
LABOR_SHRINK = BENCH["labor_shrink"].value

# 兼职/小时工占比:未确认时的扫描区间。
# ⚠ 这**没有公开数据**:白皮书只给了「灵活用工渗透率 27%」(企业采用比例),
#   不是「兼职员工人数占比」。所以这个扫描区间必须标 ASSUMPTION。
# 理由:公开报道里出现过「我们不招正式员工,只有以小时计算的长期兼职工」的极端店型,
#      上限取到 60% 以避免区间大到没有信息量。
P_SCAN = (0.10, 0.60)
P_SCAN_NOTE = (
    "公开数据缺口:白皮书只给了「灵活用工渗透率 27%」(企业采用比例),"
    "**不是**兼职员工人数占比。所以这一项必须现场问 —— 这正是必须见面的原因。"
)


def bench_rows(groups: tuple[str, ...] | None = None) -> list[dict]:
    """给界面用的基准表。"""
    out = []
    for b in BENCH.values():
        if groups and b.group not in groups:
            continue
        out.append({
            "分组": b.group,
            "指标": b.label,
            "数值": fmt_value(b),
            "等级": b.tier,
            "备注": b.caveat,
        })
    return out


def fmt_value(b: "Bench") -> str:
    """基准值怎么显示:百分比不留空格、大数给千分位、比值换算成百分数。

    踩过的坑:原来统一写 `f"{b.value:g} {b.unit}"`,同一张表里就同时冒出三种写法 ——
      `22.2 %`(百分号前多一个空格)、`1.8e+06 人`(科学计数法)、
      `0.3081 比值`(整表其它都是百分比,只有它不是)。
    """
    u = (b.unit or "").strip()
    v = b.value
    if u.startswith("%"):
        tail = u[1:].strip()
        return f"{v:g}%" + (tail if tail.startswith("/") else (f" {tail}" if tail else ""))
    if u.startswith("比值"):
        tail = u[2:].strip()
        return f"{v * 100:.1f}%" + (f" {tail}" if tail else "")
    if abs(v) >= 10000:
        return f"{v:,.0f} {u}".strip()
    return f"{v:g} {u}".strip()


def groups() -> list[str]:
    seen: list[str] = []
    for b in BENCH.values():
        if b.group not in seen:
            seen.append(b.group)
    return seen


# ================================================================
# 行业层 —— 让「行业」成为一等公民(数据层)
# ================================================================
# 设计:
#   · 每个行业一套基准(BENCH 形状完全一致)
#   · BENCH 是当前行业的**就地可变视图** —— 用 clear/update 而不是重新赋值,
#     这样其它模块里 `from fde_bench import BENCH` 拿到的是同一个对象,能跟着切。
#   · ⚠️ **数据层支持多行业,不等于模型层支持。** 测算公式仍只有餐饮一份。
#     选了一个还没写模型的行业,`fde_model.analyze()` 会**明确报错**,
#     而不是拿餐饮的公式去套物流的数据 —— 那会算出一个看着像样但其实错的数。

SRC_KDT = "圆通速递 2026 年半年度报告(600233.SH)"
SRC_KDT2 = "申通/韵达/中通 2026 半年报(媒体披露口径)"
SRC_SPB = "国家邮政局 2026 年上半年行业数据"
SRC_OEE = "蒂普泰柯 / LNS Research / Plant Engineering 公开 OEE 统计"
SRC_EXP = "《关于人工智能+邮政快递的实施意见》· 国家邮政局,2026-04"

KDT_CAVEAT = "上市公司财报口径,相对硬;但为 2026 上半年数据,后续会变。"


def _build_logistics() -> dict[str, Bench]:
    """快递物流行业基准(预侦查用,数字均已公开可查)。
    ⚠️ 口径提醒:行业平均单票收入(含顺丰/时效件)与通达系单票收入
    **不是同一个量**,不可互相代入。"""
    b: dict[str, Bench] = {}

    def add(x: Bench) -> None:
        b[x.key] = x

    add(Bench("kdt_cost_per_piece", "单票快递产品成本(圆通 2026H1)", 1.90, "元/票",
              SRC_KDT, caveat=KDT_CAVEAT, group="单票成本"))
    add(Bench("kdt_transport_cost", "单票运输成本(圆通 2026H1)", 0.36, "元/票",
              SRC_KDT, caveat=KDT_CAVEAT, group="单票成本"))
    add(Bench("kdt_hub_cost", "单票中心操作成本(圆通 2026H1)", 0.26, "元/票",
              SRC_KDT, caveat=KDT_CAVEAT, group="单票成本"))
    add(Bench("kdt_rev_per_piece", "单票快递产品收入(圆通 2026H1)", 2.17, "元/票",
              SRC_KDT, caveat=KDT_CAVEAT, group="单票收益"))
    add(Bench("kdt_gross_per_piece", "单票毛利(圆通 2026H1)", 0.27, "元/票",
              SRC_KDT, caveat="同比 +57.11%,受价格修复影响大,波动明显。", group="单票收益"))
    add(Bench("kdt_rev_yd", "单票收入(韵达 2026H1)", 2.13, "元/票", SRC_KDT2, group="单票收益"))
    add(Bench("kdt_rev_st", "单票收入(申通 2026H1)", 2.24, "元/票", SRC_KDT2, group="单票收益"))
    add(Bench("kdt_rev_industry", "行业平均单票收入(2026H1,全行业)", 7.69, "元/票", SRC_SPB,
              caveat="⚠️ **口径陷阱**:含顺丰/时效件与跨境,与通达系 2.17 元**不是同一个量**,不可互相代入。",
              group="单票收益"))

    add(Bench("kdt_ai_transport_saving", "AI 规模化后单票运输成本降幅(圆通,对 2023H1)", 0.11, "元/票",
              SRC_EXP, caveat="企业自述口径。厂方未披露统计方法。", group="AI 降本"))
    add(Bench("kdt_ai_hub_saving", "AI 规模化后单票中心操作成本降幅(圆通,对 2023H1)", 0.04, "元/票",
              SRC_EXP, caveat="企业自述口径。", group="AI 降本"))
    add(Bench("kdt_ai_cs_share", "智能客服可独立闭环的工单占比(中通)", 90.0, "%",
              SRC_EXP, caveat="企业自述;另有「70% 收件用户诉求」另一口径,不可混用。", group="AI 降本"))
    add(Bench("kdt_labor_ratio_drop", "人力成本占收入比降幅(顺丰,同比)", 1.4, "百分点",
              SRC_EXP, caveat="企业自述;归因为业务结构优化 + 智能化/无人化。", group="AI 降本"))

    add(Bench("kdt_oee_world", "OEE 世界级基准(制造业参照)", 85.0, "%", SRC_OEE,
              caveat="来源:TPM/中岛清一,1984。**制造业概念**,此处仅作跨行业参照。", group="跨行业参照"))
    add(Bench("kdt_oee_cn", "中国工厂实际 OEE 区间", 40.0, "%(40–65)", SRC_OEE,
              caveat="⚠️ 该行业**口径不统一**是公开事实(分行业基准 68%–91% 都有),用前必须声明。",
              group="跨行业参照"))
    return b


CATERING_BENCH: dict[str, Bench] = dict(BENCH)
LOGISTICS_BENCH: dict[str, Bench] = _build_logistics()

INDUSTRIES: dict[str, dict[str, Bench]] = {
    "餐饮门店": CATERING_BENCH,
    "快递物流": LOGISTICS_BENCH,
}

# 每个行业有没有对应的测算模型
MODEL_READY: dict[str, bool] = {"餐饮门店": True, "快递物流": True}

_CURRENT = "餐饮门店"


def current() -> str:
    return _CURRENT


def industries() -> list[str]:
    return list(INDUSTRIES)


def select_industry(name: str) -> dict[str, Bench]:
    """切换行业。**就地改** BENCH,保证所有 import 过它的模块都跟着变。"""
    global _CURRENT
    if name not in INDUSTRIES:
        raise KeyError(f"未知行业:{name}")
    BENCH.clear()
    BENCH.update(INDUSTRIES[name])
    _CURRENT = name
    return BENCH


def model_ready(name: str | None = None) -> bool:
    return bool(MODEL_READY.get(name or _CURRENT, False))
