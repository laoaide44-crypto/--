"""行业注册表 —— 「加一个行业」在代码里的唯一入口。

用途:
  · `app.py` 通过它拿到当前行业模块(界面不再写死 if/else)
  · 测试可以断言**注册表与基准库对得上**(见 `test_shell.py`)

加一个行业的完整动作(4 处,都在清单里):
  1. 新建 `fde_ind_<行业>.py`(带 `INDUSTRY` / `INPUTS` / `HERO` / `build_case`,
     外加界面外壳: `SAMPLE_MATERIAL` / `SAMPLE_CAPTION` / `QUESTIONS` / `TOPICS` / `INTERNAL_ASK`)
  2. `fde_bench.py`:基准进 `INDUSTRIES[行业]`,`MODEL_READY[行业] = True`
  3. 这个文件:import + 加进 `MODULES`
  4. `python test_shell.py` 会替你检查有没有漏
"""

from __future__ import annotations

import fde_ind_catering
import fde_ind_logistics

MODULES = {m.INDUSTRY: m for m in (fde_ind_logistics, fde_ind_catering)}


def get(industry: str):
    """按行业名取模块;没有就是 None(界面据此走行业闸门)。"""
    return MODULES.get(industry)
