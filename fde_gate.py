"""
证据门槛 —— 结果顶部的状态**由可检查的条件计算**,模型不能自行升级。

四个状态(顺序即升级路径,只能靠条件满足往上走):
  待补证据      → 可设计试点 → 待验收实测 → 已完成试点验证

纪律:
  · 状态是**算出来的**,不是模型写的、也不是谁点一下就升的。
  · **收到文件 ≠ 证据充分** —— 还要检查:相关字段是否真的由客户给出(不是默认值)、
    口径是否对齐、覆盖范围是否够。
  · **缺少基线** → 只允许生成「试点设计草案」,不允许生成确定性收益承诺。
  · **实测完成 ≠ 客户批准**,更 ≠ 正式签约 —— 批准是另一个独立开关,永远不自动置位。
"""

from __future__ import annotations

from dataclasses import dataclass, field

WAIT_EVIDENCE = "待补证据"
DESIGN_PILOT = "可设计试点"
AWAIT_MEASURE = "待验收实测"
PILOT_VERIFIED = "已完成试点验证"

ORDER = [WAIT_EVIDENCE, DESIGN_PILOT, AWAIT_MEASURE, PILOT_VERIFIED]

# 每个状态允许说什么、不允许说什么(界面/契约/下载/摘要都必须用同一份)
ALLOW = {
    WAIT_EVIDENCE: {
        "can": ["可以出「试点设计草案」", "可以列出候选问题与验证动作"],
        "cannot": ["不能给确定性收益", "不能进入承诺", "不能声称客户批准或签约"],
    },
    DESIGN_PILOT: {
        "can": ["可以确定试点范围与验收办法", "可以约定停止条件"],
        "cannot": ["不能给确定性收益", "不能声称客户批准或签约"],
    },
    AWAIT_MEASURE: {
        "can": ["可以按验收办法实测", "可以记录实测结果"],
        "cannot": ["实测前不得声称收益已实现", "不能声称客户批准或签约"],
    },
    PILOT_VERIFIED: {
        "can": ["可以引用实测结果", "可以据此谈扩大范围"],
        "cannot": ["实测完成不等于客户批准", "不等于正式签约 —— 批准是独立开关"],
    },
}


@dataclass
class GateInput:
    has_material: bool = False        # 有没有客户材料
    fields_from_customer: bool = False  # 关键参数是不是客户给的(不是默认假设)
    baseline_present: bool = False    # 有没有可判真假的基线
    caliber_aligned: bool = False     # 口径对齐了没有
    coverage_ok: bool = False         # 材料覆盖到决策需要的字段了没有
    pilot_defined: bool = False       # 试点范围与验收办法定了没有
    measured: bool = False            # 实测做完了没有
    approved: bool = False            # 客户批准(独立,永不自动)
    notes: list[str] = field(default_factory=list)


@dataclass
class GateResult:
    state: str
    reasons: list[str]
    missing: list[str]
    can: list[str]
    cannot: list[str]
    approved: bool = False

    @property
    def allows_commitment(self) -> bool:
        return False          # 本产品任何状态下都不由系统直接给「承诺」

    @property
    def allows_cash_claim(self) -> bool:
        """能不能声称「确定收益」。只有实测完成之后才允许引用实测收益。"""
        return self.state == PILOT_VERIFIED

    def badge(self) -> str:
        icon = {WAIT_EVIDENCE: "⏳", DESIGN_PILOT: "🧭",
                AWAIT_MEASURE: "📏", PILOT_VERIFIED: "✅"}[self.state]
        return f"{icon} {self.state}"


def evaluate(g: GateInput) -> GateResult:
    """纯函数:同样的输入永远得到同样的状态。"""
    reasons: list[str] = []
    missing: list[str] = []

    evidence_ok = True
    if not g.has_material:
        evidence_ok = False
        missing.append("客户材料(聊天记录 / 邮件 / 文档等)")
        reasons.append("没有材料 —— 只能凭默认假设,证据链为空")
    if not g.fields_from_customer:
        evidence_ok = False
        missing.append("关键参数要由客户给出(现在用的是默认假设,标 ASSUMPTION)")
        reasons.append("关键参数仍是默认值 —— 默认值只是假设,不能当客户回答")
    if not g.coverage_ok:
        evidence_ok = False
        missing.append("材料要覆盖到决策需要的字段(角色 / 问题 / 失败经历 / 口径)")
        reasons.append("材料没覆盖到决策需要的字段")
    if not g.baseline_present:
        evidence_ok = False
        missing.append("一个可判真假的基线(现在的口径是什么)")
        reasons.append("没有基线 —— 没有基线就只能出「试点设计草案」")
    if not g.caliber_aligned:
        evidence_ok = False
        missing.append("口径对齐(客户口径 vs 公开口径含义一致)")
        reasons.append("口径未对齐 —— 数会算错,不能作为依据")

    if not evidence_ok:
        state = WAIT_EVIDENCE
    elif not g.pilot_defined:
        state = DESIGN_PILOT
        reasons.append("证据已够设计试点 —— 但试点范围与验收办法还没定")
    elif not g.measured:
        state = AWAIT_MEASURE
        reasons.append("试点已定义 —— 等实测")
    else:
        state = PILOT_VERIFIED
        reasons.append("实测已完成 —— 注意:这不等于客户批准,也不等于正式签约")

    if g.approved:
        reasons.append("客户批准:已置位(独立开关,不由实测自动触发)")
    else:
        reasons.append("客户批准:未置位")

    return GateResult(state=state, reasons=reasons, missing=missing,
                      can=ALLOW[state]["can"], cannot=ALLOW[state]["cannot"],
                      approved=g.approved)


def fields_from_customer(values: dict, defaults: dict) -> tuple[bool, list[str]]:
    """判定关键参数是「客户给的」还是「默认假设」。

    确定性规则:值等于默认值 → 视为未改动,按假设处理(宁可保守)。
    返回 (是否全部由客户给出, 哪些还是假设)。
    """
    assumed = []
    for k, dv in defaults.items():
        v = values.get(k)
        try:
            same = v is not None and abs(float(v) - float(dv)) < 1e-9
        except (TypeError, ValueError):
            same = v in (None, "")
        if same:
            assumed.append(k)
    return (len(assumed) == 0, assumed)
