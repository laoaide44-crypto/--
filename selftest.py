"""本地自检:基准库 + 模型 + 契约 + 逐屏渲染。跑法:python selftest.py"""
import sys

import fde_bench as B
import fde_contract as C
import fde_ind_catering as IC
import fde_model as M


def line(t=""):
    print(t)


def test_bench():
    line(f"基准条数: {len(B.BENCH)}   分组: {B.groups()}")
    line(f"分组计数: " + ", ".join(f"{g}={len(B.bench_rows((g,)))}" for g in B.groups()))
    assert len(B.BENCH) >= 20, "基准库太少"
    for b in B.BENCH.values():
        assert b.source, f"{b.key} 缺出处"
        assert b.tier in (B.PUBLIC, B.INTERVIEW, B.INTERNAL, B.ASSUMPTION)
    line("  [OK] 每条基准都有出处和来源等级")


def test_model():
    a0 = M.analyze(12, 300000, 8, None)
    pos = M.position(a0)
    line()
    line(f"未确认兼职占比")
    line(f"  月总工时     {a0.total_hours:,.0f}")
    line(f"  人时营业额   {pos['value']:,.0f} 元/时")
    line(f"  行业均值换算 {pos['avg']:.0f} 元/时  (27万/12/174)")
    line(f"  优秀标杆     {pos['target']:.0f} 元/时")
    line(f"  亏损线       {pos['floor']:.0f} 元/时")
    line(f"  定位         {pos['tier']}")
    line(f"  第一屏       {M.headline_band(a0)}   宽度 {M.money(a0.money_width)}")

    line()
    line("确认兼职占比后(应逐档收窄)")
    for p in (0.15, 0.27, 0.45):
        a = M.analyze(12, 300000, 8, p)
        cut = 1 - a.money_width / a0.money_width
        line(f"  {p:.0%}: {M.headline_band(a)}   宽度 {M.money(a.money_width)}   收窄 {cut:.0%}")
        assert a.money_width < a0.money_width, f"{p} 没有收窄,逻辑有问题"
    line("  [OK] 收窄逻辑正确")

    line()
    line("复算步骤:")
    for l in M.how_to_check(M.analyze(12, 300000, 8, 0.27)):
        line("  " + l)


def test_contract():
    case = IC.build_case({"store_count": 12, "rev_per_store": 300000, "emp_per_store": 8},
                         {"part_time_ratio": 0.27})
    md = C.render(case, {
        "who_does_it": "店长自己在 Excel 里排",
        "how_measured": "没有",
        "resister": "店长担心失去裁量权",
        "tried_before": "买过一套排班软件,没人用",
    })
    with open("契约-草稿.md", "w", encoding="utf-8") as f:
        f.write(md)
    line()
    line(f"契约字符数: {len(md)}  已写出 契约-草稿.md")
    for k in ("附录 E", "口径陷阱", "另一条线", "店长岗位招聘周期", "人均产值"):
        line(f"  包含「{k}」: {k in md}")
        assert k in md, f"契约缺少 {k}"
    # 物流也要能渲染同一份契约
    import fde_ind_logistics as IL
    lcase = IL.build_case({"parcels_per_day": 30000, "cost_per_parcel": 2.05, "sites": 8})
    lmd = C.render(lcase, {"how_measured": "没有", "resister": "一线担心工时"})
    assert lcase.industry in lmd and "单票" in lmd, "物流契约渲染异常"
    line(f"  物流契约也能渲染: {len(lmd)} 字符  含行业名与单票口径 ✅")


def test_screens():
    from streamlit.testing.v1 import AppTest
    line()
    line("逐屏渲染检查:")

    def check(name, mutate=None):
        at = AppTest.from_file("app.py", default_timeout=60)
        at.run()
        if at.exception:
            print(f"  FAIL {name}: {at.exception}")
            return False
        if mutate:
            mutate(at)
            at.run()
            if at.exception:
                print(f"  FAIL {name}: {at.exception}")
                return False
        print(f"  OK   {name}")
        return True

    def _mkcase(part=None):
        return IC.build_case({"store_count": 12, "rev_per_store": 300000,
                              "emp_per_store": 8},
                             {"part_time_ratio": part} if part is not None else {})

    def to_report(at):
        at.session_state["screen"] = "app"
        _c = _mkcase()
        at.session_state["case"] = _c
        at.session_state["inputs"] = {"store_count": 12, "rev_per_store": 300000,
                                     "emp_per_store": 8}
        at.session_state["width_before"] = _c.headline_high - _c.headline_low
        at.session_state["step"] = "report"
        at.session_state["answers"] = {}
        at.session_state["qIndex"] = 0
        at.session_state["summary"] = None

    def to_ask(at):
        to_report(at)
        at.run()
        at.session_state["step"] = "ask"

    def to_input(at):
        at.session_state["screen"] = "app"

    def to_intake(at):
        at.session_state["screen"] = "intake"

    def to_ask2(at):
        to_ask(at)
        at.run()
        at.session_state["answers"] = {"part_time_ratio": 0.27}
        at.session_state["case"] = _mkcase(0.27)
        at.session_state["qIndex"] = 1

    def to_done(at):
        to_ask2(at)
        at.run()
        at.session_state["step"] = "done"
        at.session_state["answers"] = {
            "part_time_ratio": 0.27, "who_does_it": "店长",
            "how_measured": "没有", "resister": "店长", "tried_before": "软件"}

    ok = True
    ok &= check("① 开场页(主张 + 两个入口 + 三条可信机制)")
    ok &= check("①b 输入页", to_input)
    ok &= check("①c 丢材料页", to_intake)
    ok &= check("② 第一屏(含参照系与基准对照)", to_report)
    ok &= check("③ 追问第一题(滑块)", to_ask)
    ok &= check("③ 追问第二题(文本)", to_ask2)
    ok &= check("④ 契约页", to_done)
    return ok


if __name__ == "__main__":
    test_bench()
    test_model()
    test_contract()
    ok = test_screens()
    line()
    line("=== 全部通过 ===" if ok else "=== 有失败 ===")
    sys.exit(0 if ok else 1)
