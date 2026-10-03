"""
交付契约台 · XiHack 2026 · AI 软件应用赛道

一句话:企业给几个不敏感的参数 → 三分钟看到「你一年在漏多少钱」→
AI 一次只追问一件事 → 契约自动生成。

设计原则(见 projects/xihack-product-design.md):
  · 先给价值,再要信息。入口只要他自己心里有数的数。
  · 认可来自"他能验证你" —— 所以每一步都要可自查、标来源。
  · 把方法论做成看得见的界面(证据等级 / Gate / 未知项),而不是藏在按钮后。

跑法:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

import fde_ask
import fde_bench
import fde_demo
import fde_evidence
import fde_facts
import fde_gate
import fde_ind_catering
import fde_ind_logistics
import fde_intake
import fde_issues
import fde_llm
import fde_registry
import fde_reuse
import fde_schedule
from fde_bench import BENCH, bench_rows
from fde_contract import render
from fde_kernel import money
# (界面不再直接依赖餐饮模型 —— 行业逻辑全在 fde_ind_catering / fde_ind_logistics 里)


# 行业注册表 —— 「加一个行业」在界面上的唯一改动在 `fde_registry.py` 里
_MODULES = fde_registry.MODULES


def current_module():
    """按侧栏选中的行业返回对应的行业模块。
    行业逻辑全在模块里,**界面不碰任何行业细节**。

    ⚠️ 选了「只有基准数据、没有测算模型」的行业 → 停住并说明,**不拿别的行业的公式硬算**。
    这就是行业闸门(见 `12-新增行业的操作手册.md`)。"""
    mod = fde_registry.get(fde_bench.current())
    if mod is None:
        st.error(
            f"⚠️ 「{fde_bench.current()}」的**基准数据已就绪,但测算模型还没写** —— 这是故意的闸门。\n\n"
            "现在拿别的行业的公式去套,会算出一个「看着像样、其实错」的数 —— **那比不算更糟**。\n\n"
            "请切回已完成的行业,或者按 `12-新增行业的操作手册` 给它写一个行业模块。"
        )
        st.stop()
    return mod


def make_case(inputs: dict, ans: dict | None = None):
    """带上当前流的统一事实 / 证据标志 / 门槛开关 ——
    让追问、测算与契约引用**同一份数据**。"""
    ss = st.session_state
    return current_module().build_case(
        inputs, ans, facts=ss.get("facts"), flags=ss.get("flags"),
        state=ss.get("gate_inputs"))


def _on_verdict(key: str) -> None:
    """候选问题的客户判断(确认/否定/补充)→ flags;重算 case,
    状态、整体建议与试点范围都会跟着变。"""
    ss = st.session_state
    choice = ss.get(f"verdict_{key}") or "维持建议"
    note = (ss.get(f"vnote_{key}") or "").strip()
    fl = dict(ss.get("flags") or {})
    fl[f"rejected_{key}"] = (choice == "否定这条")
    if note:
        fl[f"note_{key}"] = note
    ss["flags"] = fl
    ss["case"] = make_case(ss.get("inputs") or {}, ss.get("answers") or {})


def _money_range(case) -> str:
    """钞票区间怎么读才顺:「60.2 万 – 268.3 万元」而不是「60.2 万 – 268.3 万 元」。"""
    lo, hi = money(case.headline_low), money(case.headline_high)
    if hi.endswith("万"):
        return f"{lo} – {hi}元"
    return f"{lo} – {hi} 元"


def current_inputs():
    """当前行业的输入项(表单和「要抽哪些参数」都由它生成)。"""
    return current_module().INPUTS


def prefill_fields() -> dict:
    """从材料里要预填的参数 = 当前行业的输入项。不再写死门店那三个。"""
    return {i.key: i.label for i in current_inputs()}


def current_topics():
    """当前行业的提问话题库(变行业时追问清单也跟着变)。"""
    return getattr(current_module(), "TOPICS", None)


st.set_page_config(page_title="交付契约台 · FDE", page_icon="📐", layout="wide")

# ---------------------------------------------------------------- 视觉
st.markdown("""
<style>
  /* ==========================================================================
     视觉单一来源:所有颜色、字级、间距都只在这里定义。
     .streamlit/config.toml 的 [theme] 只管 Streamlit 自己控件的配色,
     两边的 --accent / --paper / --ink 必须同名同值,改一个记得改另一个。
     审计命令:python design_audit.py http://127.0.0.1:8501/ --ignore "..."
     ========================================================================== */
  :root{
    /* ---- 色:「冷灰 + 靖蓝」一套(2026-09-27 选定)。每条都得有角色消费者 ---- */
    --ink:#14181c;      /* 正文 */
    --ink2:#3f474f;     /* 次级正文 */
    --ink3:#5f6874;     /* 弱化文字:在 --paper 上 5.65:1、在 --app-bg 上 4.98:1 */
    --rule:#dbe1e8;     /* 结构线:分隔 / 边框 */
    --rule-strong:#c3ccd6; /* 结构线加强:hover / 表头下沿 */
    --accent:#1f4e79;   /* 强调:"可交互 + 主行动",仅此一个含义(Lab H=269°) */
    --accent-strong:#173b5c; /* 强调的深端:hover / 按下 */
    --accent-tint:#eef3f9;   /* 强调的浅端:提示条底色 */
    --paper:#ffffff;    /* 组件底:卡片 */
    --paper-2:#f3f6f8;  /* 页面次级底:侧栏(= config.toml 的 secondaryBackgroundColor) */
    --app-bg:#eef1f4;   /* 页底 */
    --focus:#0b57d0;    /* 焦点环:留给键盘可达性,不参与配色 */
    /* 来源等级徽章:四色各一语义,浅底 + 同色相深字(实测 5.3–7.4:1) */
    --lv-public-bg:#eef0f3;     --lv-public-fg:#47515c;
    --lv-interview-bg:#fdf1e7;  --lv-interview-fg:#8a5a1c;
    --lv-internal-bg:#eaf3ed;   --lv-internal-fg:#2f6b4f;
    --lv-assumption-bg:#f1eff7; --lv-assumption-fg:#5b4a86;
    /* 2026-09-27 换色时只动了 PUBLIC:靖蓝 accent 是 269°,和它原本的蓝(266°)撞色,
       所以 PUBLIC 改成低彩石板灰;其余三个徒章色相离 accent 都 ≥35°,不动。 */

    /* ---- 字体:正文只有一个家族,层级靠字重 + 字号 ---- */
    --font-sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",
                "Microsoft YaHei","PingFang SC","Hiragino Sans GB",
                "Source Han Sans SC","Noto Sans SC",sans-serif;

    /* ---- 字级(6 级,别再随手加新尺寸) ---- */
    --fs-1:44px; --fs-2:19px; --fs-3:15px; --fs-4:13.5px; --fs-5:12px; --fs-6:11px;
    /* 行高按角色,用无单位值 */
    --lh-tight:1.15; --lh-body:1.6;
    /* ---- 间距(4 的倍数) ---- */
    --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-5:22px; --sp-6:34px;

    /* ---- 圆角:同心 —— 嵌套时 内层 = 外层 − padding 的视觉差 ---- */
    --r-1:2px;   /* 徽章 / 细线端点 */
    --r-2:7px;   /* 控件:按钮、输入、下拉 */
    --r-3:10px;  /* 面:卡片、提示条、展开器 */

    /* ---- 高度:阴影做深度,边框做结构(不再为深度画边框)。
       阴影色跟中性色同色调 —— 冷底不用暖黑,否则阴影会发脏黄。 ---- */
    --sh-1:0 1px 2px rgba(20,24,28,.05);
    --sh-2:0 1px 2px rgba(20,24,28,.05), 0 6px 18px rgba(20,24,28,.07);
    --sh-3:0 2px 4px rgba(20,24,28,.07), 0 14px 40px rgba(20,24,28,.11);
    --maxw:1080px;

    /* ---- 动效(数值取自 references/interaction-motion.md:高频反馈 ≤150ms、到达 200–280ms) ---- */
    --dur-fast:150ms; --dur-in:240ms; --dur-out:150ms;
    --ease-out:cubic-bezier(.23,1,.32,1);
    /* 旧名保留成别名,免得漏改的地方静默失效 */
    --r:var(--r-1); --shadow:var(--sh-2);
  }
  html{ color-scheme:light; }
  /* 字体只挂在 html/body/.stApp 这三个根上(不是 p/span 之类的全局元素选择器),
     框架控件都从 body 继承,所以一处生效、不影响任何收缩盒子。 */
  html, body, .stApp, [data-testid="stAppViewContainer"]{ font-family:var(--font-sans); }
  .stApp{ background:var(--app-bg); }
  body{ line-height:var(--lh-body); }
  section.main > div, [data-testid="stMain"] > div{ max-width:var(--maxw); }

  /* ---------- 卡片与排版 ---------- */
  .paper{
    background:var(--paper); border:1px solid var(--rule); border-radius:var(--r-3);
    padding:var(--sp-5) var(--sp-6); margin-bottom:var(--sp-4);
    box-shadow:var(--sh-2);
  }
  .kicker{ font-size:var(--fs-6); letter-spacing:.2em; color:var(--ink3); text-transform:uppercase; }
  .big{ font-size:var(--fs-1); font-weight:800; letter-spacing:-.03em; line-height:var(--lh-tight);
        color:var(--accent); font-variant-numeric:tabular-nums; }
  .bigsub{ font-size:var(--fs-4); color:var(--ink3); margin-top:var(--sp-1);
           font-variant-numeric:tabular-nums; }
  .lvl{ display:inline-block; font-size:var(--fs-6); font-weight:700; letter-spacing:.06em;
        padding:1px var(--sp-1); border-radius:var(--r-1); margin-left:var(--sp-1); vertical-align:1px; }
  .lvl-PUBLIC{ background:var(--lv-public-bg); color:var(--lv-public-fg); }
  .lvl-INTERVIEW{ background:var(--lv-interview-bg); color:var(--lv-interview-fg); }
  .lvl-INTERNAL{ background:var(--lv-internal-bg); color:var(--lv-internal-fg); }
  .lvl-ASSUMPTION{ background:var(--lv-assumption-bg); color:var(--lv-assumption-fg); }
  .gate{ border-left:3px solid var(--accent); background:var(--accent-tint);
         padding:var(--sp-3) var(--sp-4); border-radius:0 var(--r-3) var(--r-3) 0;
         font-size:var(--fs-4); }
  .hero{ padding:var(--sp-6) 0 var(--sp-3); }
  .hero h1{ font-size:var(--fs-1); font-weight:800; letter-spacing:-.03em; line-height:var(--lh-tight);
            margin:var(--sp-3) 0 var(--sp-4); color:var(--ink); text-wrap:balance; }
  .hero .sub{ font-size:var(--fs-3); color:var(--ink2); line-height:var(--lh-body); margin:0; max-width:42em; }
  .hero .lead{ font-size:var(--fs-2); font-weight:700; color:var(--accent); margin:0 0 var(--sp-3); }
  .cred{ border-top:2px solid var(--accent); padding:var(--sp-3) 0 0; }
  .cred-t{ font-size:var(--fs-4); font-weight:700; color:var(--ink); }
  .cred-d{ font-size:var(--fs-5); color:var(--ink3); margin-top:var(--sp-1); line-height:1.6; }
  .step{ font-size:var(--fs-6); letter-spacing:.16em; color:var(--ink3); text-transform:uppercase; }

  /* ---------- 主区标题:压掉 Streamlit 默认的大字号与下划线,让 h1→h2→h3 有真层级 ---------- */
  section.main h2, [data-testid="stMain"] h2{
    font-size:var(--fs-2); font-weight:800; letter-spacing:-.01em;
    padding:0; border:0; margin:var(--sp-5) 0 var(--sp-3); text-wrap:balance;
  }
  section.main h3, [data-testid="stMain"] h3{
    font-size:var(--fs-3); font-weight:700; margin:var(--sp-4) 0 var(--sp-2);
  }
  section[data-testid="stSidebar"] h3{
    font-size:var(--fs-5); letter-spacing:.14em; text-transform:uppercase;
    color:var(--ink3); font-weight:700;
  }
  /* ⚠️ 千万别写成 `p, li{ text-wrap: pretty }`(这里踩过):
     它会改掉「绝对定位 + 收缩盒子」的固有宽度 —— Streamlit 滑块那个数字标签
     被从 29px 压到 12px,不管拖到哪里都只看得见一位数字。
     text-wrap 只给自己写的文案加。 */
  .paper p, .hero p, .gate, .cred-d, .cred-t{ text-wrap: pretty; }
  /* 防御:滑块/刻度标签永远保持单行、不参与 text-wrap */
  [data-testid="stSliderThumbValue"] p, [data-testid="stSliderTickBar"] p{
    text-wrap: normal; white-space: nowrap;
  }

  /* ---------- 提示条:Streamlit 默认绿字在浅底上只有 4.09:1 ---------- */
  [data-testid="stAlertContainer"], [data-testid="stAlertContainer"] p{ color:var(--ink); }

  /* ---------- 无障碍:可见焦点 + 触控目标 ≥ 44×44 ---------- */
  a:focus-visible, button:focus-visible, input:focus-visible,
  select:focus-visible, textarea:focus-visible, [tabindex]:focus-visible{
    outline:3px solid var(--focus); outline-offset:2px; border-radius:var(--r);
  }
  .stApp button, .stApp input, .stApp textarea, [data-baseweb="select"] > div{
    min-height:44px; touch-action:manipulation;
  }
  .stApp button{ min-width:44px; }
  .stButton > button, [data-testid="stBaseButton-primary"],
  [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button{
    padding:0 var(--sp-4); font-weight:600; border-radius:var(--r-2);
  }

  /* ---------- 控件与组件:形状 / 深度 / 状态分开负责 ----------
     实心强调色一屏只给一个主行动(填充色给背景,不给文字)。
     下拉 / 输入统一圆角与结构边框;聚焦交给上面的 :focus-visible。 */
  .stApp button, .stApp input, .stApp textarea, [data-baseweb="select"] > div{
    border-radius:var(--r-2);
  }
  [data-testid="stBaseButton-secondary"]{
    background:var(--paper); border:1px solid var(--rule); color:var(--ink);
  }
  [data-testid="stBaseButton-primary"]{ box-shadow:var(--sh-1); }
  [data-testid="stBaseButton-primary"]:hover{ background:var(--accent-strong); }
  [data-testid="stBaseButton-secondary"]:hover{ border-color:var(--rule-strong); }
  .stApp button:disabled{ opacity:.5; }
  .stApp input, .stApp textarea{ background:var(--paper); }

  /* 表格:表头用次级底、行用结构线;不用斑马纹(那是凑密度的) */
  [data-testid="stMarkdownContainer"] table{
    width:100%; border-collapse:collapse; font-size:var(--fs-3);
  }
  [data-testid="stMarkdownContainer"] th{
    text-align:left; font-weight:700; background:var(--paper-2);
    border-bottom:1px solid var(--rule-strong);
  }
  [data-testid="stMarkdownContainer"] th,
  [data-testid="stMarkdownContainer"] td{
    padding:var(--sp-2) var(--sp-3); border-top:1px solid var(--rule); vertical-align:top;
  }

  /* 分隔线:用真的 hr,不要拿空 div 撑高度 */
  [data-testid="stMarkdownContainer"] hr{
    border:0; border-top:1px solid var(--rule); margin:var(--sp-5) 0;
  }

  /* 说明文字:弱化色(在 --paper 上 6.2:1、在 --app-bg 上 4.9:1) */
  [data-testid="stCaptionContainer"] p, [data-testid="stCaptionContainer"]{ color:var(--ink3); }

  /* 指标:标签小一号、数值重一档 */
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p{
    font-size:var(--fs-5); color:var(--ink3);
  }
  [data-testid="stMetricValue"], [data-testid="stMetricValue"] p{
    font-size:var(--fs-2); font-weight:800;
  }

  /* 行内 code:跟字阶对齐(框架默认 0.75em,正文一改就掉到 11.25px 这种非 token 值) */
  [data-testid="stMarkdownContainer"] code{
    font-size:var(--fs-5); padding:1px var(--sp-1); border-radius:var(--r-1);
    background:var(--paper-2); color:var(--ink2);
  }

  /* 展开器:它是一个面,不是一个裸 details */
  [data-testid="stExpander"] > details{
    border:1px solid var(--rule); border-radius:var(--r-3); background:var(--paper);
    box-shadow:var(--sh-1); overflow:hidden;
  }
  [data-testid="stExpander"] summary:hover{ background:var(--paper-2); }

  /* 提示条:只改形状,不动语义色(颜色是状态的,不能统一成强调色) */
  [data-testid="stAlertContainer"]{ border-radius:var(--r-3); }

  /* 侧栏:次级底 + 一条结构线,不再跟卡片抢同一个白 */
  [data-testid="stSidebar"], [data-testid="stSidebarContent"]{
    background:var(--paper-2);
  }
  [data-testid="stSidebar"]{ border-right:1px solid var(--rule); }

  /* 移动端输入框 ≥16px,否则 iOS Safari 会整页缩放 */
  @media (max-width:768px){
    .stApp input, .stApp textarea, [data-baseweb="select"] input{ font-size:16px; }
  }
  [data-testid="stSidebar"]{ overflow-x:hidden; }

  /* ---------- 正文收敛到字阶 token ----------
     Streamlit 默认正文 16px、说明文字 14px —— 两个都不在 6 级字阶里。
     实测(CDP 量 computed style):我之前用 :where() 压特异性 → **没生效**,
     展开器里的段落仍是 16px;而直接写 `[data-testid="stMarkdownContainer"] p`
     既能盖掉 Streamlit 默认,又盖不掉 .hero .sub / .hero .lead(那两个是 (0,2,0))。 */
  [data-testid="stMarkdownContainer"] p,
  [data-testid="stMarkdownContainer"] li{ font-size:var(--fs-3); }
  [data-testid="stCaptionContainer"] p,
  [data-testid="stCaptionContainer"]{ font-size:var(--fs-4); }

  /* ---------- 长文行宽封顶 ----------
     32em ≈ 中文 32 字 / 拉丁 64 字符,落在舒适区(参考 visual-craft.md)。
     长度不限的段落会一行排到 90+ 字符,眼睛找不回下一行。 */
  [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p{
    max-width:32em;
  }

  /* ---------- 交互:按下反馈 + 逐属性过渡(可打断,不用 keyframes)---------- */
  .stApp button{
    transition: transform var(--dur-fast) var(--ease-out),
                background-color var(--dur-fast) var(--ease-out),
                border-color var(--dur-fast) var(--ease-out),
                color var(--dur-fast) var(--ease-out);
  }
  .stApp button:active:not(:disabled){ transform: scale(.96); }
  /* 会变的值用等宽数字,免得跨屏切换时数字在抖 */
  [data-testid="stMetricValue"], [data-testid="stMetricDelta"]{ font-variant-numeric: tabular-nums; }

  /* ---------- 尊重系统减弱动效 ---------- */
  @media (prefers-reduced-motion: reduce){
    *, *::before, *::after{ transition-duration:.01ms !important; animation-duration:.01ms !important; }
  }
</style>
""", unsafe_allow_html=True)


def lvl(t: str) -> str:
    return f'<span class="lvl lvl-{t}">{t}</span>'


_GATE_ICON = {"待补证据": "⏳", "可设计试点": "🧭",
              "待验收实测": "📏", "已完成试点验证": "✅"}


def gate_box(case) -> str:
    """结果顶部的状态条:状态是算出来的,同时写清「能做什么 / 不能做什么」。"""
    stt = getattr(case, "gate_state", "") or fde_gate.WAIT_EVIDENCE
    ic = _GATE_ICON.get(stt, "⏳")
    can = "；".join((case.gate_can or [])[:2]) or "—"
    cannot = "；".join((case.gate_cannot or [])[:2]) or "—"
    miss = len(case.gate_missing or [])
    m = (f'<div class="gate"><b>{ic} 证据状态 · {stt}</b>'
         f'<br>可以:{can}<br>不可以:{cannot}')
    if miss:
        m += f'<br>缺口 {miss} 项(展开下方「为什么是这个状态」查看)'
    return m + "</div>"


# ---------------------------------------------------------------- 开场
# 开场文案已改为**行业感知**(从行业模块的 HERO 取),见 fde_ind_*.py
CREDIBILITY = [
    ("每个数字都能自己复算", "全部算术摊开,你按计算器就能验"),
    ("每条依据都标了来源等级", "公开 / 你说的 / 内部数据 / 假设,分得清清楚楚"),
    ("证据不足就不给承诺", "缺你的内部数据,这份文件就只到「方案设计」"),
]


def render_hero() -> None:
    """开场文案是**行业感知**的 —— 从当前行业模块取。换行业,开场跟着变。"""
    _h = current_module().HERO
    st.markdown(
        f'<div class="hero"><div class="kicker">XiHack 2026 · AI 软件应用赛道 · 离线可运行</div>'
        f'<h1>{_h["head"]}</h1>'
        f'<p class="lead">{_h["lead"]}</p>'
        f'<p class="sub">{_h["sub"]}</p></div>',
        unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    if c1.button("丢一份材料进来 →", type="primary", width="stretch"):
        _start("intake")
    if c2.button("我只有三个数,直接算 →", width="stretch"):
        _start("self")
    st.caption("材料可以是:聊天记录、邮件、需求文档、表格导出 —— 乱七八糟的都行。"
               "没有材料也能用三个数直接算。")

    cols = st.columns(3)
    for col, (title, desc) in zip(cols, CREDIBILITY):
        col.markdown(
            f'<div class="cred"><div class="cred-t">{title}</div>'
            f'<div class="cred-d">{desc}</div></div>', unsafe_allow_html=True)

    with st.expander("这个作品在做什么(给评审看的一段话)"):
        st.markdown(
            f"**这是一套可复用的交付诊断引擎 —— 当前行业是 `{fde_bench.current()}`。**\n\n"
            "**做法**:不先索取内部数据 —— 用公开基准 + 三个不敏感参数先算出钱区间,并摊开全部算术;"
            "再把结论写成一份标了证据等级的交付契约。每答一个问题,区间就窄一点。\n\n"
            "**完整闭环**:丢材料 → 抽事实(每条引文可回原文定位)→ 只问该问的 → 可自查测算 → "
            "可签字契约 → 沉淀可复用资产。**无需联网也能跑完。**\n\n"
            "**可复用的证明**:换一个行业,只换基准库和测算模型,**契约与界面一个字不改** —— "
            "侧栏切一下就能看到两个行业各跑一遍。"
        )


def _start(kind: str) -> None:
    """kind: 'intake' 丢材料 / 'self' 三个数 / 'example' 看例子"""
    ss = st.session_state
    for k in ("facts", "flags", "gate_inputs", "evidence_report", "contract_md",
              "verdicts"):
        ss.pop(k, None)
    if kind == "example":
        _d = {i.key: i.default for i in current_module().INPUTS}
        _c0 = make_case(_d, {})
        ss["case"] = _c0
        ss["inputs"] = _d
        ss["width_before"] = _c0.headline_high - _c0.headline_low
        ss["step"] = "report"
        ss["answers"] = {}
        ss["qIndex"] = 0
        ss["summary"] = None
        ss["example"] = True
        ss.pop("qorder", None)
        ss["screen"] = "app"
    elif kind == "intake":
        ss["screen"] = "intake"
    else:
        ss.pop("qorder", None)
        ss["screen"] = "app"
    st.rerun()


def _render_schedule_result(result) -> None:
    """Render stage-1 validation only; no evidence application or versioning."""
    st.markdown("---")
    st.markdown("### 排班表校验结果")
    status = getattr(result, "status", "待校验")
    if status == "有阻断问题":
        st.error(f"校验状态：{status}")
    elif status == "结构校验通过":
        st.success(f"校验状态：{status}")
    else:
        st.info(f"校验状态：{status}")
    st.caption("文件导入 ≠ 真实性已验证；本结果仅按 CSV 内容做结构校验。")

    actual = getattr(result, "actual_range", {}) or {}
    st.markdown("**文件实际包含范围**")
    st.json({
        "门店": actual.get("stores", []),
        "起始日期": actual.get("start_date"),
        "结束日期": actual.get("end_date"),
        "员工数": actual.get("staff_count", 0),
        "班次数": actual.get("shift_count", 0),
    })
    if getattr(result, "declared_range", None) is not None:
        st.markdown("**用户声明范围**")
        st.json(result.declared_range)
    if getattr(result, "coverage_gaps", None):
        st.warning("范围覆盖缺口：" + "；".join(result.coverage_gaps))

    issues = []
    for issue in list(getattr(result, "errors", []) or []) + list(getattr(result, "warnings", []) or []):
        issues.append({
            "级别": "阻断" if issue.level == "error" else "提示",
            "行号": issue.row or "文件",
            "字段": issue.field or "表头/记录",
            "规则": issue.code,
            "值": issue.value,
            "原因": issue.message,
        })
    st.markdown("**问题清单（行号 · 字段 · 规则 · 值）**")
    if issues:
        st.table(issues)
    else:
        st.caption("未发现字段或记录问题。")

    duplicates = [row for row in (getattr(result, "rows", []) or []) if row.duplicate_of]
    if duplicates:
        st.markdown("**重复行映射**")
        st.table([{"重复行": row.row_number, "重复于": row.duplicate_of, "处理": "已标记，保留原始行号"} for row in duplicates])
    conflicts = getattr(result, "conflicts", []) or []
    if conflicts:
        st.markdown("**未解决重叠冲突（含跨门店）**")
        st.table(conflicts)


# ---------------------------------------------------------------- 进场:丢材料
def render_intake() -> None:
    st.markdown('<div class="step">丢材料 · 越乱越好</div>', unsafe_allow_html=True)
    st.markdown("## 不用说清楚。把原始材料贴进来就行 —— 越乱越好。")

    MODES = ["粘贴文本", "上传文件", "用示例材料", "用预跑结果(离线演示)"]
    mode = st.radio("材料从哪来", MODES, horizontal=True, label_visibility="collapsed")
    raw = None
    if mode == "粘贴文本":
        raw = st.text_area("粘贴内容", height=200,
                           placeholder="聊天记录 / 邮件 / 需求文档 / 工单导出……直接粘,不用整理")
    elif mode == "上传文件":
        upload_mode = st.radio("上传文件用途", ["作为文本分析", "作为排班表校验"], horizontal=True)
        up = st.file_uploader("选择文件", type=["txt", "md", "csv", "log", "json"])
        if up is not None:
            payload = up.read()
            if upload_mode == "作为排班表校验":
                if not up.name.lower().endswith(".csv"):
                    st.error("排班表校验仅支持 UTF-8 CSV 文件。")
                elif st.button("校验排班表", type="primary"):
                    st.session_state["schedule_result"] = fde_schedule.parse_schedule_csv(payload)
                    st.rerun()
            else:
                raw = payload.decode("utf-8", errors="replace")
    elif mode == "用示例材料":
        _m = current_module()
        raw = _m.SAMPLE_MATERIAL
        st.caption(_m.SAMPLE_CAPTION)
        st.code(_m.SAMPLE_MATERIAL, language=None)
    else:
        # 离线演示:载入一份**真实跑过**的预跑结果
        info = fde_demo.info(fde_bench.current())
        if not info:
            st.warning("还没有预跑结果。先在联网环境下运行 `python capture_demo.py` 生成。")
        else:
            v = info.get("verify") or {}
            st.info(
                f"这份结果是 **{info['captured_at']}** 在联网环境下**真跑出来的**:"
                f"含 **{info['facts']}** 条事实,引用定位 {v.get('ok')}/{v.get('total')}"
                f"(每条引用都能在材料里找到)。\n\n"
                "载入后界面会**明确标注它不是现在现算的** —— 不标注就是造假,标注了就只是「提前跑过一遍」。"
            )
            if st.button("载入这份预跑结果 →", type="primary"):
                p = fde_demo.load(fde_bench.current())
                if p:
                    st.session_state["intake"] = p
                    st.session_state["facts"] = fde_facts.build(p, fde_issues.SUPPORTS)
                    st.rerun()
                else:
                    st.error("缓存读取失败,请重新运行 capture_demo.py。")

    schedule_result = st.session_state.get("schedule_result")
    if schedule_result is not None:
        _render_schedule_result(schedule_result)

    c1, c2 = st.columns([1, 3])
    run_it = False
    if mode != "用预跑结果(离线演示)":
        run_it = c1.button("抽取事实 →", type="primary", width="stretch")
    if c2.button("返回", width="content"):
        st.session_state["screen"] = "hero"
        st.rerun()

    if run_it:
        if not raw or not raw.strip():
            st.warning("还没有材料。贴一段、传个文件,或者用示例都行。")
        else:
            with st.spinner("正在抽取,并逐条回原文校验……"):
                _pk = fde_intake.run(
                    raw, fde_llm.chat if fde_llm.available() else None,
                    prefill_fields())
            st.session_state["intake"] = _pk
            st.session_state["facts"] = fde_facts.build(_pk, fde_issues.SUPPORTS)
            st.rerun()

    pack = st.session_state.get("intake")
    if not pack:
        st.info("抽取完之后,这里会出现:事实清单、人物、时间线、**互相矛盾的地方**、未知项 ——"
                "每一条都带原文出处,而且我会回原文校验一遍。")
        return

    sc = pack["scan"]
    verif = pack["verify"]
    res = pack["result"]

    st.markdown("---")
    st.markdown('<div class="step">抽取结果</div>', unsafe_allow_html=True)

    if pack.get("demo"):
        _dind = pack.get("demo_industry")
        st.warning(
            f"⚠️ **演示模式** —— 下面这份抽取结果捕捉于 **{pack.get('demo_captured_at', '?')}**"
            f"(联网环境下跑出的**真实**结果),**不是现在现算的**。\n\n"
            "这不是造假:它是真跑出来的,只是不是刚才。要拿实时结果,请在联网环境下重新抽取。"
        )
        if _dind and _dind != fde_bench.current():
            st.error(f"⚠️ 这份预跑结果属于「{_dind}」,与当前选择的「{fde_bench.current()}」不一致 —— "
                     "现场演示时别用错材料。")

    a, b, c, d = st.columns(4)
    a.metric("材料规模", f"{sc.n_chars:,} 字", help=f"切成 {sc.n_units} 个可定位单元")
    b.metric("扫到金额/数量", len(sc.money))
    c.metric("扫到百分比", len(sc.percents))
    d.metric("已遮蔽隐私", sc.masked, help="手机号 / 身份证 / 长串卡号")

    _fobjs = fde_facts.build(pack, fde_issues.SUPPORTS)
    _fc = fde_facts.summary_counts(_fobjs)
    if verif["total"]:
        if verif["fail"] == 0:
            st.success(f"**引用定位:{verif['ok']} 条引用均可在原文定位**(共 {verif['total']} 条)。")
        else:
            st.warning(f"**引用定位:{verif['ok']}/{verif['total']} 条可在原文定位;"
                       f"{verif['fail']} 条找不到原句** —— 那几条已降级为「无法回指」,"
                       "不作为事实使用。")
            with st.expander("看看是哪几条没定位到"):
                for p, q in verif["details"]:
                    st.markdown(f"- `{p}` → 「{q}…」")
        st.caption("⚠️ 能在原文找到 ≠ 已核实为事实 —— "
                   "「原句是否存在」「原句是否支持结论」「是否适用于本客户」"
                   "是三件事,分开记录(见下表)。")
    else:
        st.info("本次没有可校验的引用片段。" +
                (f"({pack['error']})" if pack.get("error") else ""))

    if not pack["model_used"]:
        st.warning(f"未走模型抽取({pack.get('error') or '未配置模型'}),"
                   "下面只有确定性扫描结果。配好 `.env.local` 后能力会完整很多。")
        if fde_demo.info(fde_bench.current()):
            st.markdown("**当前离线/模型不通 —— 可以先用预跑结果把演示走完:**")
            if st.button("改用「预跑结果」继续演示 →"):
                p = fde_demo.load(fde_bench.current())
                if p:
                    st.session_state["intake"] = p
                    st.session_state["facts"] = fde_facts.build(p, fde_issues.SUPPORTS)
                    st.rerun()
    if pack.get("truncated"):
        st.caption("⚠️ 材料太长,只取了前一部分送模型。")

    facts = res.get("facts") or []
    if _fobjs:
        st.markdown("### 统一事实记录(带稳定 ID;三层校验分开列)")
        st.dataframe(fde_facts.rows(_fobjs), width="stretch", hide_index=True)
        st.caption(_fc["line"])
    elif facts:
        st.markdown("### 事实清单(每条带出处与等级)")
        rows = []
        for f in facts:
            lv = f.get("level", "")
            mark = fde_intake.LEVEL_LABEL.get(lv, lv)
            if not f.get("quote_ok", True):
                mark = "⚠ 无法回指"
            rows.append({"类型": f.get("kind", ""), "内容": f.get("text", ""),
                         "原文": f.get("quote", ""), "等级": mark})
        st.dataframe(rows, width="stretch", hide_index=True)

    for title, key, cols in (("人物", "people", [("name", "姓名"), ("role", "材料里的说法"), ("quote", "原句")]),
                             ("时间线", "timeline", [("when", "时间"), ("what", "发生了什么"), ("quote", "原句")])):
        items = res.get(key) or []
        if items:
            with st.expander(f"{title}({len(items)})", expanded=(title == "时间线")):
                st.dataframe([{zh: it.get(k, "") for k, zh in cols} for it in items],
                             width="stretch", hide_index=True)

    conflicts = res.get("conflicts") or []
    _real_cf, _clues, _done_cf = fde_facts.classify_full(
        conflicts, _fobjs, units=pack.get("units"))
    if _done_cf:
        st.markdown("### ✅ 已更正(替代关系)—— 旧值保留在历史,新值进入当前计算")
        for cf in _done_cf:
            st.markdown(f"- **{cf.get('old', '')}** → **{cf.get('new', '')}**"
                        f"(同一来源:{cf.get('by', '')})\n"
                        f"  更正原话:「{cf.get('marker', '')}」\n"
                        f"  更正只建立替代关系,不等于新值已核实;来源等级保持原级。")
    if _real_cf:
        st.markdown("### ⚠️ 待核实冲突 —— 同一对象、同一时间、同一口径下不能同时成立")
        for cf in _real_cf:
            st.markdown(f"- **{cf.get('a','')}** ↔ **{cf.get('b','')}**\n"
                        f"  为什么算冲突:{cf.get('why','')}\n"
                        f"  原句:「{cf.get('quote_a','')}」 / 「{cf.get('quote_b','')}」\n"
                        f"  核实办法:{cf.get('scope','')}")
    if _clues:
        st.markdown("### 落地失败 / 异常线索(不是矛盾,是经历 —— 值得当面追问)")
        for cf in _clues:
            st.markdown(f"- **{cf.get('kind','线索')}**:{cf.get('what','')}\n"
                        f"  为什么归为线索:{cf.get('why','')}\n"
                        f"  原句:「{cf.get('quote','')}」")

    unknowns = res.get("unknowns") or []
    if unknowns:
        st.markdown("### 还不知道的(按来源分好了该去哪拿)")
        st.dataframe([{"还不知道": u.get("what", ""),
                       "为什么必须知道": u.get("why_needed", ""),
                       "从哪拿": u.get("how_to_get", "")} for u in unknowns],
                     width="stretch", hide_index=True)

    # ---------------- 第 2 步:只问该问的 ----------------
    pl = fde_ask.plan(pack, topics=current_topics(), inputs=current_inputs())
    st.markdown("---")
    st.markdown('<div class="step">只问该问的</div>', unsafe_allow_html=True)
    st.markdown(f"## {pl['summary']}")

    if pl["asked"]:
        with st.expander(f"✅ 材料已经回答了的({len(pl['asked'])} 个)—— 这些不用问", expanded=True):
            for a in pl["asked"]:
                st.markdown(f"**{a['question']}**")
                st.caption(f"依据:「{(a['quote'] or '')[:80]}」")

    if pl["ask"]:
        st.markdown(f"### 还必须要问的({len(pl['ask'])} 个)")
        for i, a in enumerate(pl["ask"], 1):
            tail = "  · **只有当面才能拿到**" if a["must"] else "  · 可以顺手问"
            st.markdown(
                f"**{i}. {a['question']}**"
                f"\n\n　　· 为什么必须知道:{a['why']}"
                f"\n\n　　· 答了会改变什么:{a['impact']}"
                f"\n\n　　· 从哪拿:`{a['how']}`{tail}"
            )
    else:
        st.success("材料已经把该回答的都回答了 —— 可以直接进入测算。")

    if pl["missing_params"]:
        st.warning(f"⚠️ 但有 {len(pl['missing_params'])} 个参数材料里没写清:"
                   f"{'、'.join(pl['missing_params'])}—— 这几个要在界面上手动填。")

    # ---------------- 第 5 步(上半):资产库先给假设 ----------------
    _st = fde_reuse.stats()
    _hits = fde_reuse.suggest(pack, industry=fde_bench.current())
    if _hits:
        st.markdown("---")
        st.markdown('<div class="step">资产库 · 上一个项目留下的东西</div>', unsafe_allow_html=True)
        st.markdown(f"库里已有 **{_st['total']}** 条资产。根据这份材料的内容,"
                    f"**先拿这 {len(_hits)} 条当假设**:")
        for h in _hits:
            tag = f"({h.samples} 个样本)" if h.samples > 1 else "(1 个样本)"
            st.markdown(f"- **[{h.kind}]** {tag} {h.text}")
            if h.note:
                st.caption(f"　　备注:{h.note}")
        st.warning("⚠️ 这些是**待验证的假设,不是事实** —— "
                   "它们来自上一个客户。**必须用这份材料重新验一遍**,验不了就不能当依据用。")
    elif _st["total"]:
        st.info(f"资产库里已有 {_st['total']} 条,但这份材料没有匹配到可用的 —— 不影响,继续。")

    st.markdown("---")
    if st.button("带着这份材料继续 →", type="primary", width="stretch"):
        pf = res.get("prefill") or {}

        def g(k, default):
            v = (pf.get(k) or {}).get("value")
            try:
                return float(v) if v not in (None, "", "null") else default
            except (TypeError, ValueError):
                return default

        ss = st.session_state
        _inputs = {i.key: g(i.key, i.default) for i in current_module().INPUTS}
        ss["gate_inputs"] = {
            "prefilled_from_material": [
                k for k in _inputs
                if ((pf.get(k) or {}).get("value") not in (None, "", "null"))],
        }
        if (pack or {}).get("demo"):
            ss["gate_inputs"]["demo_source"] = True
        if not ss.get("facts"):
            ss["facts"] = fde_facts.build(pack, fde_issues.SUPPORTS)
        _c = make_case(_inputs, {})
        ss["case"] = _c
        ss["inputs"] = _inputs
        ss["width_before"] = _c.headline_high - _c.headline_low
        ss["step"] = "report"
        ss["answers"] = {}
        ss["qIndex"] = 0
        ss["summary"] = None
        ss["qorder"] = [x["key"] for x in pl["ask"]]     # 只问该问的
        ss["screen"] = "app"
        st.rerun()


# ---------------------------------------------------------------- 状态
for k, v in {
    "a": None, "step": "input", "answers": {}, "qIndex": 0, "summary": None,
}.items():
    st.session_state.setdefault(k, v)

def reset_flow() -> None:
    """清理当前诊断，避免换行业或重新开始时复用旧结果和材料。"""
    for key in ("a", "case", "inputs", "step", "answers", "qIndex", "summary",
                "width_before", "example", "qorder", "intake", "harvested",
                "facts", "flags", "gate_inputs", "evidence_report", "contract_md",
                "verdicts", "ev_cur", "ev_backup", "ev_fact_ids", "ev_flag_keys"):
        st.session_state.pop(key, None)
    st.session_state["screen"] = "hero"


def active_questions() -> list:
    """按第 2 步的提问计划决定问哪些、按什么顺序。
    没设过计划 → 该行业模块自带的默认清单;显式设成空列表 → 一个都不问。
    ⚠️ 清单是**行业模块自己带的** —— 切到物流就不会再问排班了。"""
    qs = current_module().QUESTIONS
    if "qorder" not in st.session_state:
        return qs
    order = st.session_state.get("qorder") or []
    by_key = {q[0]: q for q in qs}
    return [by_key[k] for k in order if k in by_key]


# ---------------------------------------------------------------- 侧栏
with st.sidebar:
    st.markdown("### 交付契约台")
    st.caption("FDE · 先把钱算给你看,再问你要信息。")

    # ---- 行业切换(数据层是一等的,模型层还不是)----
    _inds = fde_bench.industries()
    _ind = st.selectbox("当前行业", _inds, index=_inds.index(fde_bench.current()), placeholder="选择行业…")
    if _ind != fde_bench.current():
        fde_bench.select_industry(_ind)
        reset_flow()
        st.rerun()
    if fde_bench.model_ready():
        st.caption(f"基准 {len(fde_bench.BENCH)} 条 · 测算模型已就绪")
    else:
        st.warning(f"「{_ind}」的基准数据已就绪({len(fde_bench.BENCH)} 条),"
                   "但**测算模型还没写**。\n\n选它去算会**明确报错** —— "
                   "我们宁可报错,也不拿别的行业的公式硬套。")
    st.divider()
    st.markdown("**公开基准库(可核对原文)**")
    _grp = {
        "人效": "人效",
        "用工结构": "用工结构",
        "用工成本": "用工成本",
        "成本结构": "成本结构",
        "流失与招聘": "流失与招聘",
        "合规与结构": "合规与结构",
    }
    for g in fde_bench.groups():
        rows = fde_bench.bench_rows((g,))
        if not rows:
            continue
        with st.expander(f"{g}({len(rows)})", expanded=(g in ("人效", "用工结构"))):
            for r in rows:
                st.markdown(f"**{r['指标']}**  \n{r['数值']}  {lvl(r['等级'])}",
                            unsafe_allow_html=True)
                if r["备注"]:
                    st.caption(r["备注"])
    _sources = dict.fromkeys(b.source for b in fde_bench.BENCH.values())
    st.caption("数据源:" + "、".join(_sources))
    st.divider()
    st.markdown("**来源等级**")
    st.markdown(f"- {lvl('PUBLIC')} 公开可查,需标出处", unsafe_allow_html=True)
    st.markdown(f"- {lvl('INTERVIEW')} 现场访谈才有", unsafe_allow_html=True)
    st.markdown(f"- {lvl('INTERNAL')} 只有你能给", unsafe_allow_html=True)
    st.markdown(f"- {lvl('ASSUMPTION')} 假设值,说明写在旁边", unsafe_allow_html=True)
    st.divider()
    _llm = fde_llm.status()
    if _llm["configured"]:
        st.success(f"LLM 已接入 · {_llm['model']}", icon="🤖")
        st.caption(f"模型来源:{_llm['source']}")
    else:
        st.info("LLM 未接入 —— 走本地模板,不影响完整演示", icon="📝")
        st.caption("要接:复制 .env.local.example 为 .env.local,填 key")
    if st.button("↺ 重新开始"):
        reset_flow()
        st.rerun()


# ---------------------------------------------------------------- 开场拦截
st.session_state.setdefault("screen", "hero")
if st.session_state["screen"] == "hero":
    render_hero()
    st.stop()

if st.session_state["screen"] == "intake":
    render_intake()
    st.stop()

# (多行业路由已接上,临时护栅已移除)

if st.session_state.pop("example", False):
    st.info("示例模式:用的是公开基准 + 一组示意参数(12 店 / 单店月流水 30 万 / 每店 8 人)。"
            "想用你自己的数,点左下角「↺ 重新开始」。")


# ---------------------------------------------------------------- ① 输入
# 表单由**行业模块的 INPUTS** 生成 —— 界面不知道任何行业细节
_mod = current_module()
_ins = _mod.INPUTS
st.markdown('<div class="step">三个数 · 你自己心里都有</div>', unsafe_allow_html=True)

with st.form("inputs_form"):
    st.markdown("## 不需要任何内部数据,不需要给我报表")
    _cols = st.columns(len(_ins))
    _vals = {}
    for _col, _inp in zip(_cols, _ins):
        _lab = f"{_inp.label}({_inp.unit})" if _inp.unit else _inp.label
        if float(_inp.step).is_integer() and float(_inp.default).is_integer():
            _vals[_inp.key] = _col.number_input(
                _lab, min_value=int(_inp.minimum), value=int(_inp.default),
                step=int(_inp.step), help=_inp.hint or None)
        else:
            _vals[_inp.key] = _col.number_input(
                _lab, min_value=float(_inp.minimum), value=float(_inp.default),
                step=float(_inp.step), help=_inp.hint or None)
    go = st.form_submit_button("算给我看 →", type="primary", width="stretch")

if go:
    try:
        _c0 = make_case(_vals, {})
        st.session_state["case"] = _c0
        st.session_state["inputs"] = _vals
        st.session_state["width_before"] = _c0.headline_high - _c0.headline_low
        st.session_state["step"] = "report"
        st.session_state["answers"] = {}
        st.session_state["qIndex"] = 0
        st.session_state["summary"] = None
    except Exception as e:
        st.error(str(e))

case = st.session_state.get("case")

if case is None:
    st.markdown(
        '<div class="paper"><div class="kicker">为什么只要这几个数</div>'
        '这些不是机密,你自己天天在算。先算给你看 —— 你觉得数对,我们再往下聊。'
        f'{lvl("INTERVIEW")}</div>', unsafe_allow_html=True)
    st.stop()


# ---------------------------------------------------------------- ② 第一屏
# 全部从 Case 渲染 —— 换行业不用改这里一个字
if st.session_state["step"] in ("report", "ask", "done"):
    _demo_flags = []
    if (st.session_state.get("intake") or {}).get("demo"):
        _demo_flags.append("预跑结果(离线演示)")
    if st.session_state.get("ev_cur"):
        _demo_flags.append("合成情景补充证据")
    if _demo_flags:
        st.warning("⚠️ **演示数据在场**:本页包含 " + " + ".join(_demo_flags) +
                   " —— 非真实客户数据;由此产生的状态推进与结论变化**仅用于演示**,真实推进需要客户实际数据到位。")
    st.markdown(gate_box(case), unsafe_allow_html=True)
    with st.expander("为什么是这个状态(由可检查的条件计算)"):
        for _r in (case.gate_reasons or []):
            st.markdown(f"- {_r}")
        if case.gate_missing:
            st.markdown("**缺口:**")
            for _mi in case.gate_missing:
                st.markdown(f"- {_mi}")
        st.caption("状态由代码按条件计算,模型不能升级状态;实测完成 ≠ 客户批准 ≠ 正式签约。")
    st.markdown('<div class="step">假设情景 · 潜在优化空间(不是已确认的漏损)</div>',
                unsafe_allow_html=True)
    if getattr(case, "revenue_stopped", False):
        st.markdown(
            f'<div class="paper">'
            f'<div class="kicker">{case.headline_label}</div>'
            f'<div class="big">已停止</div>'
            f'<div class="bigsub">{case.plain_line}</div>'
            f'<div class="bigsub">原假设区间仅在下方「收益口径」的独立假设模拟中保留,'
            f'不作为本客户的收益。数字怎么来的,下面每一步你都能自己按计算器重算。</div>'
            f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="paper">'
            f'<div class="kicker">{case.headline_label}</div>'
            f'<div class="big">{_money_range(case)}/年</div>'
            f'<div class="bigsub">{case.plain_line}</div>'
            f'<div class="bigsub">这是区间,不是承诺;补一个参数不会让它变「准」,'
            f'其他不确定性照旧展示。数字怎么来的,下面每一步你都能自己按计算器重算。</div>'
            f'</div>', unsafe_allow_html=True)

    _mcols = st.columns(len(case.metrics))
    for _col, _m in zip(_mcols, case.metrics):
        if _m.delta:
            _col.metric(_m.label, _m.value, delta=_m.delta, delta_color="off",
                        help=_m.help or None)
        else:
            _col.metric(_m.label, _m.value, help=_m.help or None)

    if case.candidates:
        with st.expander("候选问题(不预设结论 · 支持证据 / 反向证据 / 未知项 / 验证动作)",
                         expanded=True):
            for cd in case.candidates:
                st.markdown(f"**{cd.get('key','')} · {cd.get('title','')}**"
                            f" —— {cd.get('status','')}")
                st.caption(cd.get("claim", ""))
                if cd.get("support"):
                    st.caption("支持证据:" + "、".join(str(x) for x in cd["support"]))
                for _ct in (cd.get("counter") or []):
                    st.caption("反向证据:" + _ct)
                for _u in (cd.get("unknowns") or []):
                    st.caption("未知项:" + _u)
                for _v in (cd.get("verify") or []):
                    st.caption("建议验证动作:" + _v)
                if cd.get("note"):
                    st.caption("客户补充:" + str(cd["note"]))
                _cc1, _cc2 = st.columns([2, 3])
                _cc1.selectbox("你的判断", ["维持建议", "否定这条", "待定"],
                               key=f"verdict_{cd['key']}",
                               on_change=_on_verdict, args=(cd["key"],))
                _cc2.text_input("补充说明(可选,会写进契约)", key=f"vnote_{cd['key']}",
                                on_change=_on_verdict, args=(cd["key"],))
                st.divider()

    with st.expander("🔍 你自己复算一遍(这是关键)", expanded=True):
        for _line in case.recalc_steps:
            st.markdown(_line)

    with st.expander("参照系:为什么这个数不算小", expanded=True):
        st.markdown(case.reference_note)

    if case.revenue_assumptions or case.revenue_conditions:
        with st.expander("收益口径:输入 / 来源 / 假设 / 适用条件 / 公式"):
            if getattr(case, "revenue_stopped", False):
                st.markdown("**该改造建议已停止** —— 反向证据支持「无可释放工时」;"
                            "不再给出金额区间,原区间仅存于下方独立假设模拟。")
            else:
                st.markdown(f"**{case.revenue_label or '假设情景下的潜在优化空间'}**"
                            f" — {case.money_range()}")
                st.markdown(f"- 可释放工时(第一步,物理量):"
                            f"{case.hours_release_low:,.0f} – {case.hours_release_high:,.0f} 工时/月")
            st.markdown("- 可减少现金支出(第二步):需满足下列条件才成立 —— "
                        "**两者不能自动画等号**")
            _lblmap = {i.key: i.label for i in current_module().INPUTS}
            _src = "| 参数 | 来源 |\n|---|---|\n"
            for _k2, _v2 in (case.field_sources or {}).items():
                _src += f"| {_lblmap.get(_k2, _k2)} | {_v2} |\n"
            st.markdown("**输入与来源(客户给的 vs 默认假设,分得清):**\n\n" + _src)
            if case.revenue_assumptions:
                st.markdown("**假设:**")
                for _x in case.revenue_assumptions:
                    st.markdown(f"- {_x}")
            if case.revenue_conditions:
                st.markdown("**适用条件:**")
                for _x in case.revenue_conditions:
                    st.markdown(f"- {_x}")
            st.markdown("**计算公式:**")
            for _x in (case.revenue_formula or []):
                st.markdown(f"- {_x}")

    with st.expander(f"公开基准对照({len(case.bench_rows)} 条,都带出处)"):
        for _g, _lb, _v, _src in case.bench_rows:
            st.markdown(f"**{_lb}** — {_v}")
            st.caption(f"{_g} · {_src}")

    with st.expander("证据链与未知项(Gate)"):
        _rows = "".join(f"| {e.id} | {e.conclusion} | `{e.tier}` | {e.confidence} |\n"
                        for e in case.evidence)
        st.markdown(f"| # | 结论 | 来源等级 | 可信度 |\n|---|---|---|---|\n{_rows}")
        st.markdown(f'<div class="gate"><b>证据状态 · {case.gate_state or "待补证据"}</b>'
                    f'<br>{case.gate_gap or "无"}</div>',
                    unsafe_allow_html=True)


# ---------------------------------------------------------------- ③ 渐进追问
if st.session_state["step"] == "report":
    st.session_state["step"] = "ask"

if st.session_state["step"] == "ask":
    idx = st.session_state["qIndex"]
    QS = active_questions()
    st.markdown('<div class="step">一次只问一件事</div>', unsafe_allow_html=True)

    if idx < len(QS):
        key, q, why, kind = QS[idx]
        st.markdown(f'<div class="paper"><div class="kicker">问题 {idx+1} / {len(QS)}</div>'
                    f'<b style="font-size:var(--fs-2)">{q}</b>'
                    f'<div class="bigsub">{why} {lvl("INTERVIEW")}</div></div>',
                    unsafe_allow_html=True)

        with st.form(f"q_{key}"):
            if kind == "slider":
                val = st.slider("兼职 / 小时工占比", 0, 100, 20, 1, format="%d%%") / 100.0
            else:
                val = st.text_input("你的回答", placeholder="一句话就行,不用准确数字…")
            c1, c2 = st.columns([1, 1])
            ok = c1.form_submit_button("回答 →", type="primary", width="stretch")
            skip = c2.form_submit_button("跳过", width="stretch")

        if ok:
            st.session_state["answers"][key] = val
            st.session_state["qIndex"] = idx + 1
            if key == "part_time_ratio":
                _ans2 = dict(st.session_state["answers"])
                _ans2["part_time_ratio"] = float(val)
                st.session_state["case"] = make_case(
                    st.session_state.get("inputs") or {}, _ans2)
            st.rerun()
        if skip:
            st.session_state["qIndex"] = idx + 1
            st.rerun()

        if st.session_state["answers"]:
            st.caption("已答:" + " · ".join(
                f"{k}={v}" for k, v in st.session_state["answers"].items()))
    else:
        # 五问都过完(答或跳过)→ 进契约
        st.session_state["step"] = "done"
        st.rerun()


# ---------------------------------------------------------------- ④ 契约
if st.session_state["step"] == "done":
    ans = st.session_state["answers"]
    st.markdown(gate_box(case), unsafe_allow_html=True)
    st.markdown('<div class="step">契约草稿已生成</div>', unsafe_allow_html=True)

    if st.session_state.get("summary") is None:
        text, src = fde_llm.case_summary(case)
        st.session_state["summary"] = (text, src)

    text, src = st.session_state["summary"]
    st.markdown(
        f'<div class="paper"><div class="kicker">给老板看的结论'
        f'{"(模型生成)" if src == "llm" else "(本地模板)"}</div>'
        f'<div style="font-size:var(--fs-3);line-height:1.8">{text}</div></div>',
        unsafe_allow_html=True)

    _p = ans.get("part_time_ratio")
    if _p is not None and not getattr(case, "revenue_stopped", False):
        _now = case.headline_high - case.headline_low
        before = st.session_state.get("width_before") or _now
        cut = max(0.0, 1 - _now / before) if before else 0.0
        st.info(
            f"区间已收窄:兼职占比 {float(_p):.0%} → 假设情景区间 "
            f"{_money_range(case)}。"
            f"**区间宽度从 {money(before)} 收窄到 {money(_now)}(−{cut:.0%})**。"
            "注意:中心点会随你给的新信息移动 —— 窄了,不是原来那个数固定不动;"
            "补一个参数也不会让估算变「准」,工时口径与成本区间等不确定性照旧展示。"
        )

    md = render(case, ans, st.session_state.get("intake"),
                evidence=st.session_state.get("evidence_report"))
    st.session_state["contract_md"] = md
    st.download_button("⬇ 下载契约草稿(.md)", md,
                       file_name="交付契约-草稿.md", mime="text/markdown",
                       width="stretch")
    st.caption("下载的文件与页面上的状态、来源、数字一致(同一份内容渲染)。")
    with st.expander("查看契约全文", expanded=True):
        st.markdown(md)

    st.markdown(
        f'<div class="gate"><b>下一步(现场用)</b><br>'
        f'① 把 <code>INTERVIEW</code> 字段用访谈卡补齐(兜里那张 A5);<br>'
        f'② 向对方索取 <code>INTERNAL</code>:{current_module().INTERNAL_ASK} —— '
        f'<b>拿到并核对口径后,证据才算补到位</b>;<br>'
        f'③ 第 04 条能判真假、双方确认试点范围后,才进入签字环节'
        f'(实测完成 ≠ 客户批准 ≠ 正式签约)。</div>',
        unsafe_allow_html=True)

    # ---------------- 补证据 · 改决策(合成演示) ----------------
    st.markdown("---")
    st.markdown('<div class="step">补证据 · 改决策</div>', unsafe_allow_html=True)
    st.caption(fde_evidence.SYNTHETIC_NOTE +
               " 结论不硬编码:变的是证据,判断与范围由现有规则和计算重新算出来。")
    _keys = list(fde_evidence.SCENARIOS)
    _pick = st.radio("选择一份补充材料", _keys,
                     format_func=lambda k: fde_evidence.SCENARIOS[k]["label"],
                     key="ev_pick")
    with st.expander("查看这份合成材料原文", expanded=False):
        st.code(fde_evidence.SCENARIOS[_pick]["material"], language=None)
    if st.button("应用这份补充证据 →", type="primary", key="ev_apply"):
        ss = st.session_state
        # 情景切换是「替换」不是「叠加」:首次应用前留一份快照(供撤回)
        if not ss.get("ev_backup"):
            ss["ev_backup"] = {
                "facts": list(ss.get("facts") or []),
                "flags": dict(ss.get("flags") or {}),
                "answers": dict(ss.get("answers") or {}),
                "evidence_report": ss.get("evidence_report"),
                "gate_inputs": dict(ss.get("gate_inputs") or {}),
            }
        try:
            _res = fde_evidence.apply_update(
                _pick,
                ss.get("inputs") or {},
                ss.get("answers") or {},
                build_case=lambda i, a, facts=None, flags=None, state=None: current_module().build_case(
                    i, a, facts=facts, flags=flags, state=state),
                industry=fde_bench.current(),
                extra_facts=ss.get("facts"),
                base_flags=ss.get("flags"),
                state=dict(ss.get("gate_inputs") or {}),
                strip_fact_ids=ss.get("ev_fact_ids"),
                strip_flag_keys=ss.get("ev_flag_keys"))
        except Exception as e:  # 失败要明确报错,不静默
            st.error(f"应用失败:{type(e).__name__}: {e}")
        else:
            ss["inputs"] = _res["new_inputs"]
            _a2 = dict(ss.get("answers") or {})
            _a2.update(_res["new_ans"])
            ss["answers"] = _a2
            # 标志:先剔掉旧情景的键,再并入新情景(与事实同一套替换语义)
            _strip_keys = set(ss.get("ev_flag_keys") or [])
            _fl = {k: v for k, v in (ss.get("flags") or {}).items()
                   if k not in _strip_keys}
            _fl.update(_res["flags"])
            ss["flags"] = _fl
            _strip_ids = set(ss.get("ev_fact_ids") or [])
            _fnow = [f for f in fde_facts.as_facts(ss.get("facts") or [])
                     if f.id not in _strip_ids]
            ss["facts"] = _fnow + fde_facts.as_facts(_res["facts"])
            _gi = ss.setdefault("gate_inputs", {})
            _gi["baseline_present"] = True      # 客户补充的实际数据 = 基线到位
            _gi["caliber_aligned"] = True
            _gi["synthetic_applied"] = True     # 演示来源:报告区与门槛原因会明示
            ss["ev_cur"] = _pick
            ss["ev_fact_ids"] = [f["id"] for f in _res["facts"]]
            ss["ev_flag_keys"] = sorted(_res["flags"].keys())
            ss["case"] = make_case(ss["inputs"], ss["answers"])
            ss["evidence_report"] = {
                "label": _res["label"],
                "report": _res["report"],
                "invalidated": _res["invalidated"],
                "recalced": _res["recalced"],
                "pilot_before": _res["before"].pilot_scope,
                "pilot_after": _res["pilot_scope"],
                "unknowns": _res["unknowns"],
            }
            ss["summary"] = None
            st.rerun()

    # 撤回:回到补证据前的状态(只有应用过情景时才出现)
    if st.session_state.get("ev_cur"):
        if st.button("↩ 撤回补充证据(回到补前状态)", key="ev_undo"):
            ss = st.session_state
            _b = ss.get("ev_backup") or {}
            ss["facts"] = _b.get("facts") or []
            ss["flags"] = _b.get("flags") or {}
            ss["answers"] = _b.get("answers") or {}
            ss["evidence_report"] = _b.get("evidence_report")
            ss["gate_inputs"] = _b.get("gate_inputs") or {}
            for _k in ("ev_cur", "ev_backup", "ev_fact_ids", "ev_flag_keys"):
                ss.pop(_k, None)
            ss["case"] = make_case(ss.get("inputs") or {}, ss.get("answers") or {})
            ss["summary"] = None
            st.toast("已撤回补充证据,回到补前状态")
            st.rerun()

    _er = st.session_state.get("evidence_report")
    if _er:
        st.success(f"已应用:{_er['label']} —— 每一项变化都带依据。")
        if _er["report"]:
            _tbl = "| 变化 | 之前 | 之后 | 依据 |\n|---|---|---|---|\n"
            for _rw in _er["report"]:
                _tbl += (f"| {_rw['what']} | {_rw['before']} | {_rw['after']} | "
                         f"{_rw['basis']} |\n")
            st.markdown(_tbl)
        else:
            st.info("本次应用没有改变任何判断或测算参数。")
        if _er["invalidated"]:
            st.warning("旧结论失效:" + ";".join(_er["invalidated"]))
        if _er["recalced"]:
            st.markdown("**重算:**" + "; ".join(_er["recalced"]))
        st.markdown(f"**试点范围:**{_er['pilot_before'] or '未定'} → **{_er['pilot_after']}**")
        if _er["unknowns"]:
            st.markdown("**仍然不确定:**" + "；".join(_er["unknowns"]))
        st.caption("依据:参数来自合成材料的结构化解析;状态与范围由规则重算。")

    # ---------------- 第 5 步(下半):沉淀可复用资产 ----------------
    st.markdown("---")
    st.markdown('<div class="step">把这次学到的东西留下来</div>', unsafe_allow_html=True)
    _st = fde_reuse.stats()
    st.caption(f"资产库现有 {_st['total']} 条。沉淀下来, 下一个客户就不用从头开始 —— "
               f"但**留下的是「假设」,不是「事实」**。")

    if st.button("把这次的经验沉淀成资产 →", width="stretch"):
        _srcs = {x.source for x in fde_reuse.load()}
        _code = f"P{len(_srcs) + 1}"
        _new = fde_reuse.harvest(case, ans, st.session_state.get("intake") or {}, project=_code)
        _added = fde_reuse.add(_new)
        st.session_state["harvested"] = {
            "code": _code, "added": _added, "total": len(_new),
            "items": [{"kind": x.kind, "text": x.text, "note": x.note} for x in _new],
        }
        st.rerun()

    _hv = st.session_state.get("harvested")
    if _hv:
        st.success(f"已沉淀 **{_hv['added']}** 条新资产(本次共抽出 {_hv['total']} 条,重复的已合并)"
                   f"—— 来源代号 `{_hv['code']}`(不含任何客户名)。")
        for it in _hv["items"]:
            st.markdown(f"- **[{it['kind']}]** {it['text']}")
            if it["note"]:
                st.caption(f"　　备注:{it['note']}")
        st.caption("下次再有材料进来, 这些会先以「待验证的假设」形式出现。")
