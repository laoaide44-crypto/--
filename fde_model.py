"""
漏损计算模型 —— 全部算术必须客户能自己复算一遍。

诚实性约束:
  · 只用公开基准 + 客户自己给的几个不敏感参数,不假装有内部数据。
  · 两条诊断【不可相加】。它们在机制上部分重叠,加起来会虚高。
  · 主线结论用「用工结构」这条(直接来自公开对比数据,最硬);
    「人时营业额」那条作为交叉验证/上限参考。

术语:
  工时 = 一个人干一小时。月总工时 = 员工数 × 174(国家标准月计薪口径)。
  人时营业额 = 门店营业额 ÷ 月总工时,即"每个员工每小时产出多少钱"。
"""

from dataclasses import dataclass, field, asdict

from fde_bench import (
    INDUSTRIES, LABOR_SHRINK, HOURS_PER_MONTH_FULLTIME, HOURS_PER_MONTH_SRC,
    P_SCAN, P_SCAN_NOTE, PUBLIC, INTERVIEW, ASSUMPTION,
)

# ⚠️ 本模块是**餐饮专用模型**,所以只读餐饮自己的基准。
# 绝不能读 fde_bench.BENCH —— 那是「当前选中行业」的视图,
# 界面一切到别行业,这里的公式就会读到别人的键直接崩。
BENCH = INDUSTRIES["餐饮门店"]

# 已确认后的不确定带(线性插值是近似,不是原来给的数据)
P_CONFIRMED_BAND = 0.15


class NoModelForIndustry(Exception):
    """选中的行业只有数据、没有测算模型。
    宁可报错,也不拿别的行业的公式硬套。"""


@dataclass
class Analysis:
    # 输入
    store_count: int
    rev_per_store: float
    emp_per_store: float
    part_time_ratio: float | None          # **当前**兼职/小时工占比(客户自报)
    target_part_time: float | None = None  # **拟调整后**的占比(客户确认;与当前占比含义不同)

    # 全职占比区间(可释放工时的换算基数)
    full_time_low: float = 0.0
    full_time_high: float = 0.0

    # 派生
    total_stores_rev: float = 0.0
    total_hours: float = 0.0
    rev_per_hour: float = 0.0

    # 主线:用工结构可释放工时
    struct_hours_low: float = 0.0
    struct_hours_high: float = 0.0
    struct_money_low: float = 0.0
    struct_money_mid: float = 0.0
    struct_money_high: float = 0.0

    # 交叉:人效冗余工时
    eff_hours_excess: float = 0.0
    rev_per_hour_flag: str = ""

    # 状态
    p_range: tuple = field(default_factory=lambda: P_SCAN)
    p_confirmed: bool = False
    assumptions: list[str] = field(default_factory=list)
    tiers: dict = field(default_factory=dict)

    @property
    def money_width(self) -> float:
        """区间宽度(元/年)。用来向客户展示"每答一题就窄一点"。"""
        return self.struct_money_high - self.struct_money_low

    def to_dict(self):
        d = asdict(self)
        d["p_range"] = list(self.p_range)
        return d


def _money(hours: float, per_hour: float) -> float:
    return hours * 12.0 * per_hour


def analyze(
    store_count: int,
    rev_per_store: float,
    emp_per_store: float,
    part_time_ratio: float | None = None,
    industry: str | None = None,
    target_part_time: float | None = None,
) -> Analysis:
    """industry 显式指定后就不再依赖全局选中的行业 ——
    适配器可以直接说「我算的是餐饮」,不受界面当前选什么影响。"""
    # ---- 行业闸门:数据就绪 ≠ 模型就绪 ----
    import fde_bench as _b
    _ind = industry or _b.current()
    if not _b.model_ready(_ind):
        raise NoModelForIndustry(
            f"「{_ind}」的基准数据已就绪,但**测算模型还没写**。\n"
            f"现在拿餐饮的公式去套,会算出一个「看着像样、其实错」的数 —— "
            f"那比不算更糟。想用这个行业,先把它的测算逻辑写出来。"
        )
    if store_count <= 0 or rev_per_store <= 0 or emp_per_store <= 0:
        raise ValueError("店数、单店月流水、单店员工数都必须大于 0")

    a = Analysis(
        store_count=int(store_count),
        rev_per_store=float(rev_per_store),
        emp_per_store=float(emp_per_store),
        part_time_ratio=part_time_ratio,
        target_part_time=target_part_time,
    )

    a.total_stores_rev = a.store_count * a.rev_per_store
    a.total_hours = a.store_count * a.emp_per_store * HOURS_PER_MONTH_FULLTIME
    a.rev_per_hour = a.total_stores_rev / a.total_hours

    # ---------- 主线:用工结构 ----------
    if part_time_ratio is None:
        a.p_range = P_SCAN
        a.p_confirmed = False
        a.assumptions.append(
            f"兼职/小时工占比未确认,按 {P_SCAN[0]:.0%}–{P_SCAN[1]:.0%} 扫描。{P_SCAN_NOTE}"
        )
    else:
        p = max(0.0, min(1.0, float(part_time_ratio)))
        lo = max(0.0, p * (1 - P_CONFIRMED_BAND))
        hi = min(1.0, p * (1 + P_CONFIRMED_BAND))
        a.p_range = (lo, hi)
        a.p_confirmed = True
        a.assumptions.append(
            f"已确认**当前**兼职占比 {p:.0%},按 ±{P_CONFIRMED_BAND:.0%} 计不确定带"
        )

    # ⚠️ 方向修正(2026-09-28):可释放的是**当前按全职排的那部分工时**。
    # 所以换算基数是「全职占比 = 1 − 当前兼职占比」,而不是「兼职占比」本身。
    # 方向:当前越偏全职 → 可释放空间越大;已经大量用小时工 → 空间越小。
    lo_p, hi_p = a.p_range
    a.full_time_low = 1.0 - hi_p
    a.full_time_high = 1.0 - lo_p

    a.struct_hours_low = a.total_hours * LABOR_SHRINK * a.full_time_low
    a.struct_hours_high = a.total_hours * LABOR_SHRINK * a.full_time_high
    a.struct_money_low = _money(a.struct_hours_low, BENCH["cost_low"].value)
    a.struct_money_mid = _money(
        a.total_hours * LABOR_SHRINK * (a.full_time_low + a.full_time_high) / 2,
        BENCH["cost_mid"].value,
    )
    a.struct_money_high = _money(a.struct_hours_high, BENCH["cost_high"].value)

    a.assumptions.append(
        "可释放工时的换算基数是「当前全职占比」(= 1 − 当前兼职占比);"
        "「拟调整后的兼职占比」是试点目标,含义不同,不进入本公式 —— 二者不可混用。"
    )
    if target_part_time is not None:
        t = max(0.0, min(1.0, float(target_part_time)))
        a.assumptions.append(
            f"拟调整后兼职占比目标 {t:.0%}(仅作试点目标;方向:占比越高,可释放空间越小)"
        )

    # ---------- 交叉:人效 ----------
    target = BENCH["rev_per_hour_target"].value
    floor = BENCH["rev_per_hour_floor"].value
    hours_needed = a.total_stores_rev / target
    a.eff_hours_excess = max(0.0, a.total_hours - hours_needed)

    if a.rev_per_hour >= target:
        a.rev_per_hour_flag = "at_or_above"
    elif a.rev_per_hour >= floor:
        a.rev_per_hour_flag = "below_target"
    else:
        a.rev_per_hour_flag = "below_floor"

    a.assumptions += [
        f"月总工时 = 店数 × 单店员工数 × {HOURS_PER_MONTH_FULLTIME:.0f} 小时。{HOURS_PER_MONTH_SRC}",
        f"用工结构可释放比例 {LABOR_SHRINK:.1%} = 1 − 137/198,由公开两端点线性推导。",
        "两条诊断机制部分重叠,不可相加。",
    ]

    a.tiers = {
        "store_count": INTERVIEW,
        "rev_per_store": INTERVIEW,
        "emp_per_store": INTERVIEW,
        "part_time_ratio": INTERVIEW,
        "rev_per_hour_target": PUBLIC,
        "labor_shrink": PUBLIC,
        "cost_mid": PUBLIC,
        "output_per_head": PUBLIC,
        "labor_cost_ratio": PUBLIC,
        "turnover_server": PUBLIC,
        "hire_cost_ratio": PUBLIC,
        "p_scan": ASSUMPTION,
    }
    return a


def bench_per_hour_from_output() -> float:
    """把「人均产值 27 万元/年」换算成人时营业额(元/小时),用于交叉对照。
    27万 ÷ 12 月 ÷ 174 小时 ≈ 129 元/小时"""
    return BENCH["output_per_head"].value / 12.0 / HOURS_PER_MONTH_FULLTIME


def position(a: "Analysis") -> dict:
    """客户的人时营业额坐在哪一档。三档全部来自公开口径,可自己核。"""
    target = BENCH["rev_per_hour_target"].value     # 180 优秀标杆
    avg = bench_per_hour_from_output()              # ~129 行业均值
    floor = BENCH["rev_per_hour_floor"].value       # 100 亏损线
    v = a.rev_per_hour

    if v >= target:
        tier, tone = "优于公开标杆", "ok"
    elif v >= avg:
        tier, tone = "高于行业均值、低于优秀标杆", "warn"
    elif v >= floor:
        tier, tone = "低于行业均值", "warn"
    else:
        tier, tone = "低于公开亏损线", "bad"

    return {
        "value": v, "tier": tier, "tone": tone,
        "target": target, "avg": avg, "floor": floor,
        "avg_source": f"由「人均产值 27 万元/年」换算 · {BENCH['output_per_head'].source}",
    }


def money(x: float) -> str:
    """兼容层:真正的实现在 fde_kernel。这里只做再导出,
    保证老的 `M.money` 调用不破。"""
    from fde_kernel import money as _m
    return _m(x)


def headline_band(a: Analysis) -> str:
    """第一屏那句话。"""
    return f"{money(a.struct_money_low)} – {money(a.struct_money_high)} 元/年"


def how_to_check(a: Analysis) -> list[str]:
    """让客户能自己复算的步骤。这是建立认可的核心。"""
    p_lo, p_hi = a.p_range
    return [
        f"① 你的月总工时 = {a.store_count} 店 × {a.emp_per_store:g} 人 × {HOURS_PER_MONTH_FULLTIME:.0f} 小时 "
        f"= {a.total_hours:,.0f} 工时(174 = 21.75 天 × 8 小时,国家标准)",
        f"② 公开基准说:同一家店从全职排班改成小时排班,当日总工时从 198 降到 137,"
        f"即可省下 {LABOR_SHRINK:.1%}",
        f"③ 按你 **当前全职占比** {a.full_time_low:.0%}–{a.full_time_high:.0%}"
        f"(当前兼职占比 {p_lo:.0%}–{p_hi:.0%})计,可释放 "
        f"{a.struct_hours_low:,.0f}–{a.struct_hours_high:,.0f} 工时/月",
        f"④ 乘 12 个月,再乘 {BENCH['cost_low'].value:g}–{BENCH['cost_high'].value:g} 元/小时的用工成本,"
        f"得到上面那个区间",
        "⑤ 任何一步你都可以自己按计算器重算 —— 基准的出处就在页面上,点开能看原文",
    ]
