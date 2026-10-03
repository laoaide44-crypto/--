"""
进场包 · 第 2 步:只问该问的

比"少问几个"更进一步 —— 先声明**哪些问题材料已经回答了**(带原句),
再只列**剩下的、真正必须问的**。

设计纪律(不能破):
  · **选哪些问题、怎么排序,由确定性规则决定,不交给模型。**
    模型只负责把问法说成人话 —— 否则"只问该问的"会变成"模型随便想几个问题"。
  · 判定"材料已经回答"是**保守的**:证据不硬就算没回答,宁可多问一句。
  · 每一条都要说清:为什么问 / 答了会改变什么 / 从哪拿 / 是否必须当面问。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 从哪拿
PUBLIC, ASK, INTERNAL = "公开信息", "问客户", "内部数据"


@dataclass
class Topic:
    key: str              # 对应界面上的答案字段
    question: str         # 人话问法
    why: str              # 为什么必须知道
    impact: str           # 答了会改变什么(能量化就量化)
    how: str              # 从哪拿
    must_in_person: bool  # 是否只有当面才能拿到
    score: int            # 排序分(越大越该先问)
    need_kw: list[str] = field(default_factory=list)   # 材料里出现这些词 = 可能已回答
    need_strong: list[str] = field(default_factory=list)  # 更强的信号(带数字/承诺)


TOPICS: list[Topic] = [
    Topic(
        key="part_time_ratio",
        question="你们现在兼职 / 小时工大概占多少?",
        why="这是整条链条上唯一能把区间砍掉一半以上的输入",
        impact="实测:确认后区间宽度收窄 54%–85%(未确认时按 10%–60% 扫描)",
        how=ASK, must_in_person=True, score=100,
        need_kw=["兼职", "小时工", "零工", "全职"],
        need_strong=["兼职占", "小时工占", "全都是兼职", "基本上都是全职", "很少兼职"],
    ),
    Topic(
        key="how_measured",
        question="现在有没有一个数,能证明这件事做得算好?",
        why="契约的验收标准必须是能判真假的;没有基线就没法立标准",
        impact="决定契约第 04 条能不能写出来 —— 写不出就没有可验收的承诺",
        how=ASK, must_in_person=True, score=90,
        need_kw=["指标", "达标", "算好", "考核", "人效", "营业额", "满意度"],
        need_strong=["人时营业额", "每人每小时", "达标线", "考核口径"],
    ),
    Topic(
        key="internal_data",
        question="能不能给我们一份脱敏的原始数据(比如近 8 周的排班表)?",
        why="这是把结论从『方案设计』推到『可承诺』的唯一途径",
        impact="没有它,契约只能停在「可进入方案设计」—— 我们不给承诺",
        how=INTERNAL, must_in_person=True, score=85,
        need_kw=["排班表", "考勤", "台账", "报表", "导出"],
        need_strong=["近 8 周", "近八周", "提供排班表", "发你"],
    ),
    Topic(
        key="who_does_it",
        question="这件事现在是谁在做?他一周大概花多久?",
        why="没有具体的人和小时数,后面全是空话",
        impact="决定契约第 03 条(谁受益)和第 08 条(谁提供什么)",
        how=ASK, must_in_person=False, score=70,
        need_kw=["谁做", "负责", "店长", "主管", "我一个人", "排班"],
        need_strong=["一周", "每周", "小时", "至少一天", "干活"],
    ),
    Topic(
        key="resister",
        question="谁最不希望这件事被改?为什么?",
        why="阻力通常不在技术里,而它会决定项目能不能落地",
        impact="决定契约第 09 条(风险登记)和第 03 条(受影响方)",
        how=ASK, must_in_person=True, score=65,
        need_kw=["不希望", "反对", "抵触", "担心", "怕", "不愿意"],
        need_strong=["怕以后", "会被追责", "被取代", "不信任", "被压"],
    ),
    Topic(
        key="tried_before",
        question="以前试过什么办法?为什么没成?",
        why="别人踩过的坑,不该再踩一遍",
        impact="决定契约第 05 条(不在范围内)和第 09 条(风险应对)",
        how=ASK, must_in_person=False, score=55,
        need_kw=["试过", "买过", "上过", "以前", "之前", "用过", "软件"],
        need_strong=["买过一套", "没人用", "闲置", "最后就放着", "没成"],
    ),
]

# 结论里必须有的参数(缺了就算不出数)。保留这份餐饮口径做默认值/兼容,
# 界面会传当前行业模块的 INPUTS 进来 —— 缺口检查跟着行业走。
PARAM_LABEL = {
    "store_count": "门店数",
    "rev_per_store": "单店月流水",
    "emp_per_store": "单店员工数",
}


def _norm(s: str) -> str:
    return (s or "").replace(" ", "").replace("　", "")


def _search(pack: dict, topic: Topic) -> tuple[bool, str]:
    """在材料里找该主题的证据。返回 (是否已回答, 依据原句)。
    保守判定:必须有 need_strong 里的强信号才算已回答;只有弱词不算。"""
    facts = (pack.get("result") or {}).get("facts") or []
    blob_texts = []
    for f in facts:
        if f.get("quote_ok") is False:
            continue
        blob_texts.append((f.get("text") or "", f.get("quote") or ""))

    # 1) 强信号 + 关键词同时命中 → 算已回答
    for text, quote in blob_texts:
        t = _norm(text)
        if any(_norm(k) in t for k in topic.need_strong):
            if any(_norm(w) in t for w in topic.need_kw):
                return True, quote or text
    # 2) 只有强信号也算(它本身就是明确表述)
    for text, quote in blob_texts:
        t = _norm(text)
        if any(_norm(k) in t for k in topic.need_strong):
            return True, quote or text
    return False, ""


def _params_missing(pack: dict, inputs: list | None = None) -> list[str]:
    """材料里没写清、算数又必须有的输入。

    `inputs` 传当前行业模块的 INPUTS(界面表单就是由它生成的)——
    这样缺口检查跟着行业走,不会拿餐饮的参数去检查物流的材料。"""
    pf = (pack.get("result") or {}).get("prefill") or {}
    pairs = ([(i.key, i.label) for i in inputs] if inputs
             else list(PARAM_LABEL.items()))
    missing = []
    for k, label in pairs:
        v = (pf.get(k) or {}).get("value")
        if v in (None, "", "null"):
            missing.append(label)
    return missing


def plan(pack: dict, topics: list[Topic] | None = None,
         inputs: list | None = None) -> dict:
    """产出提问计划。

    返回:
      asked   —— 材料已经回答了的(带原句),这些不用问
      ask     —— 还必须要问的(按 score 降序),每条带为什么/影响/从哪拿
      missing_params —— 算不出数的缺口参数
      summary —— 一句话结论,给界面直接用

    默认用本模块的 TOPICS(餐饮口径);`topics` 传行业模块自己的一套话题,
    换行业时提问计划就跟着换。
    """
    topics = topics if topics else TOPICS
    asked, ask = [], []

    for t in topics:
        ok, quote = _search(pack, t)
        if ok:
            asked.append({"key": t.key, "question": t.question, "quote": quote})
        else:
            ask.append({
                "key": t.key, "question": t.question, "why": t.why,
                "impact": t.impact, "how": t.how, "must": t.must_in_person,
                "score": t.score,
            })

    ask.sort(key=lambda x: -x["score"])
    missing = _params_missing(pack, inputs)

    # 一句话结论
    total = len(topics)
    n_asked = len(asked)
    if missing:
        summary = (f"材料已经回答了 {n_asked}/{total} 个问题;"
                   f"但有 {len(missing)} 个参数没写清({('、'.join(missing))}),"
                   f"所以还需要 {len(ask)} 个问题。")
    else:
        summary = (f"材料已经回答了 {n_asked}/{total} 个问题。"
                   f"**下面 {len(ask)} 个是真的必须问的** —— 其余都不用开口。")

    return {"asked": asked, "ask": ask, "missing_params": missing, "summary": summary}


def demo() -> None:
    """本地自检:没有材料场景下的计划长什么样。"""
    empty = {"result": {"facts": [], "prefill": {}}}
    p = plan(empty)
    print(p["summary"])
    print("必问:")
    for a in p["ask"]:
        print(f"  [{a['score']:>3}] {a['question']}  ({a['how']})")


if __name__ == "__main__":
    demo()
