"""UI regressions: submit real forms, continue intake, and switch industries."""
from pathlib import Path
import unittest

import fde_bench
from streamlit.testing.v1 import AppTest


APP = Path(__file__).with_name("app.py")


class AppRegressionTests(unittest.TestCase):
    def setUp(self):
        fde_bench.select_industry("餐饮门店")
        self.app = AppTest.from_file(str(APP), default_timeout=30).run()
        self.assert_clean()

    def assert_clean(self):
        self.assertFalse(list(self.app.exception))
        self.assertFalse(list(self.app.error))

    def click(self, label):
        next(b for b in self.app.button if b.label == label).click().run()
        self.assert_clean()

    def switch(self, industry):
        # 按标签找「当前行业」—— 主区里还有别的下拉(候选问题的判断),不能用下标。
        sb = next(s for s in self.app.selectbox if s.label == "当前行业")
        sb.select(industry).run()
        self.assert_clean()

    def test_submit_and_switch_both_directions(self):
        for industry in ("快递物流", "餐饮门店", "快递物流"):
            self.switch(industry)
            self.assertNotIn("case", self.app.session_state)
            self.assertNotIn("inputs", self.app.session_state)
            self.click("我只有三个数,直接算 →")
            self.assertFalse(list(self.app.metric))
            if industry == "快递物流":
                self.app.number_input[0].set_value(40000)
            self.click("算给我看 →")
            self.assertIn("case", self.app.session_state)
            self.assertTrue(list(self.app.metric))
            captions = " ".join(c.value for c in self.app.caption)
            if industry == "快递物流":
                self.assertEqual(self.app.session_state["inputs"]["parcels_per_day"], 40000)
                self.assertIn("圆通速递", captions)
                self.assertNotIn("餐饮业人力资源白皮书", captions)
            else:
                self.assertIn("餐饮业人力资源白皮书", captions)
                self.assertNotIn("parcels_per_day", self.app.session_state["inputs"])

    def test_offline_intake_continue_and_restart(self):
        self.click("丢一份材料进来 →")
        self.app.radio[0].set_value("用预跑结果(离线演示)").run()
        self.click("载入这份预跑结果 →")
        self.assertIn("intake", self.app.session_state)
        self.click("带着这份材料继续 →")
        self.assertTrue(list(self.app.metric))
        self.click("算给我看 →")
        self.click("↺ 重新开始")
        for key in ("case", "inputs", "intake", "qorder", "harvested"):
            self.assertNotIn(key, self.app.session_state)
        self.click("我只有三个数,直接算 →")
        self.assertFalse(list(self.app.metric))


if __name__ == "__main__":
    unittest.main()
