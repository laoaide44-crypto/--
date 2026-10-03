# -*- coding: utf-8 -*-
"""证据闭环行为测试 —— 覆盖任务书要求的验收行为。

跑法:python test_evidence_closure.py   (退出码 0 = 全过)

B1  原材料已给出的角色/问题/失败经历 → 进入契约,不再显示「未提供」
B2  没有 / 跳过关键证据 → 可看草案,但无确定性收益、无批准状态
B3  引用存在但不支持结论 → 三层分开记录,不升级为已验证
B4  软件已采购且闲置 → 归为落地失败线索,不是事实矛盾
B5  补证据能改变候选问题 / 测算 / 试点范围,且每项变化有依据
B6  数据不足或不支持 → 保留未知 / 输出「暂不建议进行该改造」
B7  页面与导出文档一致(状态 / 来源)
B8  离线链路完整走通(AppTest);实时调用仅在配置可用时验证
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fde_contract as C
import fde_evidence as EV
import fde_facts as FA
import fde_gate as G
import fde_ind_catering as IC
import fde_issues as ISS

FAILS = []


def check(name, cond, extra=""):
    print(f"  [{'OK' if cond else 'FAIL'}] {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        FAILS.append(name)


MATERIAL_LINES = [
    "我真排不过来了,12 家店的班表我一个人弄",
    "至少一天吧，周一基本干不了别的",
    "总部现在也没个准数，每家店到底排得合不合理看不出来",
    "排完了店员老来问为什么这么排，我也说不出个所以然，只能重改",
    "我们去年买过一套排班软件，没人用，最后就放着",
    "还有人说怕以后工时被压",
]

DEFAULT_INPUTS = {"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8}
PREFILLED = {"prefilled_from_material": ["store_count", "rev_per_store", "emp_per_store"]}


def sample_pack():
    return {"result": {"facts": [{"text": x, "quote": x, "quote_ok": True,
                                  "level": "DIRECT"} for x in MATERIAL_LINES],
                       "prefill": {}, "conflicts": [], "unknowns": []}}


def build(i, a, facts=None, flags=None, state=None):
    return IC.build_case(i, a, facts=facts, flags=flags, state=state)


def main():
    print("=== B1 材料里已给出的角色 / 问题 / 失败经历 → 进入草案 ===")
    pack = sample_pack()
    facts = FA.build(pack, ISS.SUPPORTS)
    case = IC.build_case(dict(DEFAULT_INPUTS), {}, facts=facts, state=dict(PREFILLED))
    md = C.render(case, {}, pack)
    check("承担者原句进入契约", "我一个人弄" in md)
    check("失败经历进入契约", "没人用" in md)
    check("现场阻力进入契约", "怕以后工时被压" in md)
    check("01 不再显示「甲方原话待补」", "关键原话待补" not in md)
    check("03/05 不再显示旧的「待补」模板", "目前承担工作的人待补" not in md
          and "过去尝试过未提供" not in md)
    check("「未提供·待补」仅剩图例说明", md.count("〔未提供 · 待补〕") <= 1,
          str(md.count("〔未提供 · 待补〕")))
    check("状态=可设计试点(材料+字段+覆盖+基线齐)", case.gate_state == G.DESIGN_PILOT,
          case.gate_state)

    print("=== B2 无材料 / 空答案 → 草案可见,但无确定性收益、无批准 ===")
    case2 = IC.build_case(dict(DEFAULT_INPUTS), {})
    md2 = C.render(case2, {}, None)
    check("状态=待补证据", case2.gate_state == G.WAIT_EVIDENCE, case2.gate_state)
    check("草案正文完整", "## 02" in md2 and "## 04" in md2)
    check("收益写成「假设情景」", "假设情景" in md2)
    check("批准=未置位", "客户批准:未置位" in md2)
    check("无「已获批准」", "已获批准" not in md2)
    check("无「已签约」", "已签约" not in md2)

    print("=== B3 引用存在但不支持结论 → 三层分开,不升级 ===")
    pack_p = {"result": {"facts": [{
        "text": "排班每年要花掉三百多天的工作量", "quote": "至少一天吧，周一基本干不了别的",
        "quote_ok": True, "level": "DIRECT"}]}}
    f0 = FA.build(pack_p, ISS.SUPPORTS)[0]
    check("原句支持=部分支持", f0.support_status == FA.SUP_PART, f0.support_status)
    check("未覆盖部分保留为待验证推断", bool(f0.remainder))
    check("适用性=待客户确认", f0.apply_status == FA.APPLY_PENDING)
    check("未标成「已验证」", not f0.confirmed)
    pack_bad = {"result": {"facts": [{"text": "买了新系统", "quote": "材料里根本没有这句",
                                      "quote_ok": False, "level": "DIRECT"}]}}
    fb = FA.build(pack_bad, {})[0]
    check("无法定位 → 降级为推断", fb.status == FA.ST_INFERRED, fb.status)
    sc = FA.summary_counts(FA.build(pack_p, {}) + [fb])
    check("统计措辞=引用定位口径", "可在原文定位" in sc["line"] and "部分支持" in sc["line"])

    print("=== B4 「买过软件但没人用」→ 落地失败线索,不是矛盾 ===")
    conflicts = [{"a": "去年买过一套排班软件", "b": "没人用，最后就放着",
                  "why": "看起来像矛盾", "quote_a": "我们去年买过一套排班软件",
                  "quote_b": "没人用，最后就放着"}]
    real, clues = FA.classify(conflicts, facts)
    check("不判为待核实冲突", len(real) == 0)
    check("归为落地失败线索", bool(clues) and clues[0]["kind"] == "落地失败线索")
    conflicts2 = [{"a": "排班每周花一天", "b": "排班每周花两天", "why": "同口径冲突",
                   "quote_a": "至少一天吧", "quote_b": "每周两天"}]
    real2, _ = FA.classify(conflicts2, facts)
    check("真冲突保留 + 核实办法", len(real2) == 1 and "同一对象" in real2[0].get("scope", ""))

    print("=== B5 补证据 → 改决策(S1 / S2) ===")
    r1 = EV.apply_update("S1", dict(DEFAULT_INPUTS), {"part_time_ratio": 0.27},
                         build, "餐饮门店", extra_facts=facts, state=dict(PREFILLED))
    b1 = next(c for c in r1["after"].candidates if c["key"] == "B")
    check("S1:结构判断→停止(反向证据支持)", "停止" in b1["status"], b1["status"])
    check("S1:试点转向排班解释 / 返工", "排班解释" in r1["pilot_scope"])
    check("S1:报告不含 A 的假变化", not any("候选问题 A" in x["what"] for x in r1["report"]))
    check("S1:报告含 B 状态与依据变化", any("候选问题 B" in x["what"] for x in r1["report"]))
    check("S1:测算重算(收窄)", any("可释放工时" in x for x in r1["recalced"]))
    check("S1:旧结论标记失效", len(r1["invalidated"]) >= 1)
    check("S1:每项变化带依据", all(x.get("basis") for x in r1["report"]))

    r2 = EV.apply_update("S2", dict(DEFAULT_INPUTS), {"part_time_ratio": 0.27},
                         build, "餐饮门店", extra_facts=facts, state=dict(PREFILLED))
    b2 = next(c for c in r2["after"].candidates if c["key"] == "B")
    check("S2:保留优化假设(需数据验证)", "需客户数据验证" in b2["status"], b2["status"])
    check("S2:试点=单店验证 + 服务质量约束",
          "单店验证" in r2["pilot_scope"] and "服务质量" in r2["pilot_scope"])
    check("S2:试点范围变化进入报告", any(x["what"] == "试点范围" for x in r2["report"]))
    check("S2:仍列出不确定项", len(r2["unknowns"]) > 0)

    print("=== B6 数据不足 → 保留未知 / 输出「暂不建议」 ===")
    check("B6:S1 场景明确建议不推进", "不再推进" in b1["reason"] and "停止" in b1["status"])
    check("B6:未知项保留", len(case2.unknowns) >= 3)

    print("=== B9 收尾修复:①反向证据进入决策 ②更正 vs 冲突 ===")
    import fde_intake as _I
    def _mk(lines):
        return FA.build({"result": {"facts": [
            {"text": t, "quote": t, "quote_ok": True, "level": "DIRECT"}
            for t in lines]}}, ISS.SUPPORTS)
    _no = IC.build_case(dict(DEFAULT_INPUTS), {}, facts=_mk(["兼职比例大概两成"]))
    _yes = IC.build_case(dict(DEFAULT_INPUTS), {},
                         facts=_mk(["忙时排的人跟客流基本吻合,没有冗余", "兼职比例大概两成"]))
    _b_no = next(x for x in _no.candidates if x["key"] == "B")
    _b_yes = next(x for x in _yes.candidates if x["key"] == "B")
    check("① 只加「没有冗余」→ 状态=存在反向证据,需核实",
          _b_yes["status"] == ISS.S_COUNTER, _b_yes["status"])
    check("① 判断依据随证据变化、带出处",
          "反向证据" in _b_yes["reason"] and "〔" in _b_yes["reason"])
    check("① 无该证据时不出现反向证据判断",
          _b_no["status"] != ISS.S_COUNTER and "反向证据" not in _b_no["reason"])
    check("① 反向证据列入 counter(层级+出处)",
          any("客户陈述" in x and "〔" in x for x in _b_yes["counter"]))
    _syn = [{"id": "U2", "kind": "补充证据",
             "text": "近 4 周复核:没有发现明显的时段冗余,忙时人手上得比较准",
             "quote": "近 4 周复核:没有发现明显的时段冗余,忙时人手上得比较准",
             "locator": "情景一 · 合成材料", "source_type": "内部数据(合成)",
             "status": "已实测", "quote_ok": True, "support_status": "完全支持",
             "apply_status": "已适用实测", "confirmed": True, "note": ""}]
    _cs = IC.build_case(dict(DEFAULT_INPUTS), {"part_time_ratio": 0.62}, facts=_syn)
    _bs = next(x for x in _cs.candidates if x["key"] == "B")
    check("① 数据支持 → 计算允许为零",
          _cs.hours_release_low == 0 and _cs.hours_release_high == 0)
    check("① 数据支持 → 停止建议", "停止" in _bs["status"], _bs["status"])
    check("① 原区间降级为独立假设模拟",
          any("独立假设模拟" in x for x in _cs.revenue_assumptions))

    _m6 = ("许主管\n2026年09月25日 17:00\n先说数:每家店八个人\n\n"
           "许主管\n2026年09月25日 17:05\n更正一下,刚才说的是老数据\n\n"
           "许主管\n2026年09月25日 17:06\n前两个月加了人手,现在每家店是十个人\n\n"
           "罗经理\n2026年09月25日 17:09\n流水和店数呢\n\n"
           "许主管\n2026年09月25日 17:10\n12 家店,单店月流水 30 万左右\n")
    _cf6 = [{"a": "每家店八个人", "b": "现在每家店是十个人", "why": "同一人更正",
             "quote_a": "先说数:每家店八个人",
             "quote_b": "前两个月加了人手,现在每家店是十个人"}]
    _r6, _c6, _k6 = FA.classify_full(_cf6, [], units=_I.split_units(_m6))
    check("② 同人明确更正 → 替代关系(不再列冲突)", len(_k6) == 1 and not _r6)
    check("② 旧值留历史、新值进计算",
          "八个人" in _k6[0]["old"] and "十个人" in _k6[0]["new"])
    _m7 = ("李主管\n2026年09月25日 18:00\n我们单店八个人\n\n"
           "王店长\n2026年09月25日 18:00\n不对吧,明明是十个人(同一天同一个店)\n\n"
           "李主管\n2026年09月25日 18:03\n反正按我的数算就行\n\n"
           "罗经理\n2026年09月25日 18:05\n先别急,门店数多少\n\n"
           "李主管\n2026年09月25日 18:06\n12 家店\n")
    _cf7 = [{"a": "我们单店八个人", "b": "明明是十个人", "why": "两人两个数字",
             "quote_a": "我们单店八个人",
             "quote_b": "不对吧,明明是十个人(同一天同一个店)"}]
    _r7, _c7, _k7 = FA.classify_full(_cf7, [], units=_I.split_units(_m7))
    check("② 不同人矛盾 → 保留待核实冲突", len(_r7) == 1 and not _k7)

    print("=== B7/B8 页面与导出一致 + 离线链路走通(AppTest) ===")
    import fde_bench
    from streamlit.testing.v1 import AppTest

    fde_bench.select_industry("餐饮门店")
    at = AppTest.from_file("app.py", default_timeout=120).run()
    check("B8:冷启动无异常", not list(at.exception))
    next(b for b in at.button if b.label == "丢一份材料进来 →").click().run()
    at.radio[0].set_value("用预跑结果(离线演示)").run()
    next(b for b in at.button if b.label == "载入这份预跑结果 →").click().run()
    at.run()
    check("B8:演示模式有显著标注",
          any("演示模式" in w.value for w in list(at.warning) + list(at.info)))
    next(b for b in at.button if b.label == "带着这份材料继续 →").click().run()
    for _ in range(9):
        sk = next((b for b in at.button if b.label == "跳过"), None)
        if sk is None:
            break
        sk.click().run()
    at.run()
    check("B7:跳过关键问题后仍能走到契约页", "contract_md" in at.session_state)
    md_done = at.session_state.get("contract_md") or ""
    stt = at.session_state["case"].gate_state
    check("B7:导出含同一状态", stt in md_done, stt)
    page = " ".join(m.value for m in at.markdown if isinstance(m.value, str))
    check("B7:页面含同一状态", f"证据状态 · {stt}" in page)
    check("B7:导出含来源标记", "客户材料" in md_done)

    r = next(r for r in at.radio if r.label == "选择一份补充材料")
    r.set_value("S2").run()
    next(b for b in at.button if b.label == "应用这份补充证据 →").click().run()
    check("B8:应用无异常且无错误条", not list(at.exception) and not list(at.error))
    at.run()
    check("B8:变化报告已展示", "evidence_report" in at.session_state)
    md_done2 = at.session_state.get("contract_md") or ""
    check("B7/B8:契约已重生成且含合成标注", "合成演示材料" in md_done2)
    stt2 = at.session_state["case"].gate_state
    check("B8:状态随证据推进到「待验收实测」", stt2 == G.AWAIT_MEASURE, stt2)

    print("=== 实时调用(仅当已配置) ===")
    import fde_intake as I
    import fde_llm
    if fde_llm.available():
        pk = I.run(IC.SAMPLE_MATERIAL, fde_llm.chat)
        check("实时:模型可用且返回结果", pk.get("model_used") is True)
        check("实时:有事实且可定位",
              len(pk["result"]["facts"]) >= 3 and pk["verify"]["ok"] > 0)
        print(f"      (live: facts={len(pk['result']['facts'])} "
              f"verify={pk['verify']['ok']}/{pk['verify']['total']})")
    else:
        print("  [SKIP] 未配置模型 —— 实时链路跳过(离线链路已全走通)")

    print()
    if FAILS:
        print(f"=== 有失败({len(FAILS)}):" + "; ".join(FAILS) + " ===")
        sys.exit(1)
    print("=== 全部通过 ===")


if __name__ == "__main__":
    main()
