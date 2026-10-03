"""
内核:一次诊断的**通用结构**。

为什么要有它:
  契约、界面、资产库现在都写死在餐饮的字段上(总工时 / 人时营业额 / 可释放工时……)。
  每换一个行业,它们全都要改 —— 那不叫可复用。

  所以把「一次诊断」抽象成 Case:**不管哪个行业,产出的都是同一个形状的东西**。
  行业模块只负责「填内容」,契约/界面/资产库只负责「渲染形状」。

纪律:
  · Case 里的每一个钱数,都必须能指回 evidence 里的某一条(带出处 + 来源等级)。
  · 行业模块不许自己拼文案模板 —— 文案在 fde_contract 里,只有一份。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

# 来源等级(与 fde_bench 保持一致)
PUBLIC, INTERVIEW, INTERNAL, ASSUMPTION = "PUBLIC", "INTERVIEW", "INTERNAL", "ASSUMPTION"
LEVEL_LABEL = {
    PUBLIC: "公开可查", INTERVIEW: "现场访谈", INTERNAL: "客户内部", ASSUMPTION: "自定假设",
}


@dataclass
class Metric:
    """界面上那排指标卡里的一个。"""
    label: str
    value: str
    help: str = ""
    delta: str = ""
    plain: str = ""          # 翻成人话的那一句


@dataclass
class Evidence:
    """证据链里的一条。"""
    id: str
    conclusion: str
    source: str
    tier: str = PUBLIC
    confidence: str = "中"


@dataclass
class Input:
    """一个行业需要客户给的输入项(界面据此生成表单)。"""
    key: str
    label: str
    unit: str = ""
    default: float = 0.0
    minimum: float = 0.0
    step: float = 1.0
    hint: str = ""


@dataclass
class Case:
    """一次完整诊断。契约、界面、资产库都只认这个。"""

    industry: str = ""
    # ---- 钱(元/年)----
    headline_low: float = 0.0
    headline_mid: float = 0.0
    headline_high: float = 0.0
    headline_label: str = ""            # 这个钱是什么钱,一句话
    reference_note: str = ""            # 参照系:为什么这个数不小(本行业专用尺子)

    # ---- 界面 ----
    metrics: list[Metric] = field(default_factory=list)
    recalc_steps: list[str] = field(default_factory=list)
    plain_line: str = ""                # 「翻成人话」

    # ---- 契约正文(11 块里需要内容的那几块)----
    truth_title: str = ""               # ② 真问题
    truth_body: str = ""
    acceptance: list[tuple] = field(default_factory=list)   # (标准, 基线, 等级)
    out_of_scope: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    milestones: list[tuple] = field(default_factory=list)   # (时间, 交付, 谁验收)
    responsibilities: list[tuple] = field(default_factory=list)  # (甲方, 乙方)
    risks: list[tuple] = field(default_factory=list)        # (风险, 影响, 应对, 谁盯)
    unknowns: list[tuple] = field(default_factory=list)     # (未知项, 影响, 怎么拿)

    # ---- 证据 ----
    evidence: list[Evidence] = field(default_factory=list)
    gate: str = ""                      # 证据充分度结论(旧字段,保留兼容)
    gate_gap: str = ""                  # 缺什么

    # ---- 证据闭环(新增)----
    gate_state: str = ""                 # 待补证据 / 可设计试点 / 待验收实测 / 已完成试点验证
    gate_reasons: list[str] = field(default_factory=list)
    gate_missing: list[str] = field(default_factory=list)
    gate_can: list[str] = field(default_factory=list)
    gate_cannot: list[str] = field(default_factory=list)
    approved: bool = False               # 客户批准(独立开关,不由实测自动置位)
    facts: list[dict] = field(default_factory=list)       # 统一事实记录(带稳定 ID)
    candidates: list[dict] = field(default_factory=list)  # 候选问题
    candidate_note: str = ""             # 整体建议
    # 收益表达:工时与现金分开,且明确是「假设情景」
    revenue_label: str = ""              # 这笔钱在契约里的准确叫法
    revenue_stopped: bool = False        # 反向证据支持「无可释放工时」→ 停止建议、不给区间
    hours_release_low: float = 0.0       # 可释放工时(小时/月)
    hours_release_high: float = 0.0
    revenue_assumptions: list[str] = field(default_factory=list)
    revenue_conditions: list[str] = field(default_factory=list)
    revenue_formula: list[str] = field(default_factory=list)
    pilot_scope: str = ""
    stop_condition: str = ""             # 停止条件
    field_sources: dict = field(default_factory=dict)  # 参数来源:客户自报 / 默认假设

    # ---- 附录用的 ----
    inputs_summary: str = ""            # ① 客户自报的原始输入
    inputs_source_label: str = ""       # 输入来源一句话(材料预填 / 客户自报 / 默认假设)
    bench_rows: list[tuple] = field(default_factory=list)   # (维度,指标,数值,出处)
    caveats: list[str] = field(default_factory=list)        # 口径陷阱
    side_line: str = ""                 # 「另一条线(仅作参考,不计入上面区间)」
    side_title: str = ""
    needs_part_time: bool = False       # 这个行业要不要问「兼职占比」
    scale_unit: str = ""                # 摊到单个单元叫什么(场站/门店)  ""

    def money_range(self) -> str:
        if getattr(self, "revenue_stopped", False):
            return "已停止 —— 反向证据支持无可释放工时"
        return f"{money(self.headline_low)} – {money(self.headline_high)} 元/年"

    def to_dict(self) -> dict:
        return asdict(self)


def band(mid: float, lo_ratio: float = 0.7, hi_ratio: float = 1.3) -> tuple[float, float, float]:
    """从一个参考值生成区间。比拍一个数更诚实 —— 明确它是估的。"""
    return mid * lo_ratio, mid, mid * hi_ratio


def money(x: float) -> str:
    """¥1,234,567 → '123.5 万'。全项目只此一份,不许各写各的。"""
    if abs(x) >= 10000:
        return f"{x / 10000:,.1f} 万"
    return f"{x:,.0f}"
