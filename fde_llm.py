"""
可选 LLM 层 —— 有 key 就用,没有就走模板,绝不因为缺 key 而崩。

刻意不依赖任何 SDK:只用标准库 urllib 打 OpenAI 兼容的 /chat/completions,
这样在没有网络、没有 key 的机器上照样能演示。

密钥怎么给(二选一,**都不经过对话**):
  1) 同目录下建 `.env.local`,写一行:  OPENAI_API_KEY=你的key
     (可用 OPENAI_BASE_URL / OPENAI_MODEL 覆盖默认值)
  2) 自己设用户级环境变量 OPENAI_API_KEY

⚠️ 本模块**从不**打印密钥,也不会把它写进任何日志。
   `.env.local` 已在 .gitignore 里。
"""

from __future__ import annotations

import json
import os
import urllib.request

from fde_model import Analysis, money

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")
DEFAULT_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"
# 部分中转站/网关(经 Cloudflare)会对不带 User-Agent 的请求直接回 403,urllib 默认不发 UA。
USER_AGENT = "xihack-fde/1.0"

# 接受的键名(兼容不同供应商的习惯叫法)
KEY_NAMES = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "API_KEY")
# 占位符 —— 填了这些等于没填
PLACEHOLDERS = {"***", "your-key", "YOUR_KEY", "sk-xxx", "<key>", ""}

_LAST_LOAD: dict = {"found": [], "chosen": None, "placeholder": False, "error": None}


def _parse(text: str) -> list[tuple[str, str]]:
    """只做解析,不做任何输出。"""
    out: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        k, v = line.split("=", 1)
        k = k.strip().lstrip("\ufeff")
        v = v.strip().strip('"').strip("'").strip()
        if k:
            out.append((k, v))
    return out


def _load_env_file() -> None:
    """每次调用时读一遍,这样放好 key 后不用重启进程。
    已存在的真实环境变量优先,文件不覆盖它。

    容错:UTF-8 / UTF-8-BOM / UTF-16 / GBK 都能读;键名带 BOM、带引号、
    带 export 前缀都能认。**从不记录或输出值本身**,只记录键名。
    """
    diag = {"found": [], "chosen": None, "placeholder": False, "error": None}
    text = None
    for enc in ("utf-8-sig", "utf-8", "utf-16", "gbk"):
        try:
            with open(ENV_FILE, encoding=enc) as f:
                text = f.read()
            break
        except FileNotFoundError:
            _LAST_LOAD.update(diag)
            return
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError as e:
            diag["error"] = type(e).__name__
            _LAST_LOAD.update(diag)
            return

    if text is None:
        diag["error"] = "无法解码(试过 utf-8-sig/utf-8/utf-16/gbk)"
        _LAST_LOAD.update(diag)
        return

    pairs = _parse(text)
    diag["found"] = [k for k, _ in pairs]

    chosen = None
    for name in KEY_NAMES:
        for k, v in pairs:
            if k == name:
                chosen = (k, v)
                break
        if chosen:
            break
    if chosen is None:
        # 宽容一点:只有一个以 API_KEY 结尾的键时就用它
        cands = [(k, v) for k, v in pairs if k.upper().endswith("API_KEY")]
        if len(cands) == 1:
            chosen = cands[0]

    if chosen:
        k, v = chosen
        diag["chosen"] = k
        if v in PLACEHOLDERS:
            diag["placeholder"] = True
        elif not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = v

    # 端点/模型也允许写在文件里
    for k, v in pairs:
        if k in ("OPENAI_BASE_URL", "OPENAI_MODEL") and v and not os.environ.get(k):
            os.environ[k] = v

    _LAST_LOAD.update(diag)


def available() -> bool:
    _load_env_file()
    return bool(os.environ.get("OPENAI_API_KEY"))


def status() -> dict:
    """给界面看的。只报键名与状态,绝不回报值。"""
    ok = available()
    return {
        "configured": ok,
        "base": os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE),
        "model": os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        "source": (".env.local" if os.path.exists(ENV_FILE) else "环境变量") if ok else "未配置",
        "file_exists": os.path.exists(ENV_FILE),
        "vars_found": _LAST_LOAD["found"],
        "key_picked": _LAST_LOAD["chosen"],
        "is_placeholder": _LAST_LOAD["placeholder"],
        "error": _LAST_LOAD["error"],
    }

SYSTEM = (
    "你是一名前沿部署工程师(FDE),正在给一位门店老板当面解释一份用工诊断。要求:\n"
    "1. 说人话,不用术语,不吹牛,不分点,总共不超过 120 字。\n"
    "2. 第一句:直接给那个假设情景下的潜在优化空间区间(用给定的数字和单位),不得写成已确认的漏损。\n"
    "3. 第二句:说这钱怎么来的。**只能照抄【推导链】里的原话,不许自己发明因果。**\n"
    "   特别注意:这笔钱 = 可释放工时 × 每小时用工成本。**与人时营业额无关,不得拿它当解释。**\n"
    "4. 第三句:问一个具体问题,把我们还缺的那一个信息要过来。\n"
    "5. 只能使用给定的数字。**一个新增数字都不许出现。**\n"
    "6. 禁止出现“提升 / 优化 / 增强 / 赋能”这类空词。"
)


def _prompt(a: Analysis) -> str:
    from fde_model import how_to_check

    chain = "\n".join(how_to_check(a))
    return (
        f"【诊断结论】年漏损区间 {money(a.struct_money_low)} – {money(a.struct_money_high)} 元/年。\n"
        f"【推导链】\n{chain}\n"
        f"【门店基本情况】{a.store_count} 家店;单店月流水 {a.rev_per_store:,.0f} 元;"
        f"单店 {a.emp_per_store:g} 人;月总工时 {a.total_hours:,.0f}。\n"
        f"【已知的人效定位】人时营业额 {a.rev_per_hour:,.0f} 元/小时(仅作背景,不得用作漏损的解释)。\n"
        f"【还缺的信息】兼职/小时工占比 —— "
        f"{'已确认 ' + format(a.part_time_ratio, '.0%') if a.p_confirmed else '尚未取得'}。"
    )


def _template(a: Analysis) -> str:
    return (
        f"按你自己给的几个数算,假设情景下的潜在优化空间是 {money(a.struct_money_low)} 到 "
        f"{money(a.struct_money_high)} 元/年的用工成本。"
        f"这个数来自一个公开对比:同一家店从全职排班改成小时排班,当日总工时从 198 小时降到 137 小时。"
        f"要把它算准,我还需要知道一件事——你们现在兼职/小时工大概占多少?"
    )


def chat(system: str, user: str, timeout: int = 90, max_tokens: int = 3000) -> str | None:
    """通用调用。返回文本,失败或未配置返回 None。**绝不打印密钥。**"""
    if not available():
        return None
    base = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE).rstrip("/")
    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "User-Agent": USER_AGENT,
                 "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return (data["choices"][0]["message"]["content"] or "").strip() or None
    except Exception:
        return None


CASE_SYSTEM = (
    "你是一名前沿部署工程师(FDE),正在给客户当面解释一份诊断。要求:\n"
    "1. 说人话,不用术语,不吹牛,不分点,总共不超过 120 字。\n"
    "2. 第一句:直接给那个年度区间(用给定的数字和单位)。\n"
    "3. 第二句:说这钱怎么来的。**只能照抄【推导链】里的原话,不许自己发明因果。**\n"
    "4. 第三句:用一句话把【我们还缺的那一个信息】要过来。\n"
    "5. 只能使用给定的数字。**一个新增数字都不许出现。**\n"
    "6. ⚠️ 数字一律写**阿拉伯数字**(如 60.2 万、2.05 元、1,095 万票),"
    "**不许写成中文数字**(不要写“六十点二万”)。\n"
    "7. 禁止出现“提升 / 优化 / 增强 / 赋能”这类空词。\n"
    "8. 收益一律称「假设情景下的潜在优化空间」,不得写成已确认的漏损或多付;"
    "不得声称获得批准或完成签约。\n"
    "9. 第一句必须先报当前证据状态(见【当前证据状态】)。"
)


def case_summary(case, timeout: int = 25) -> tuple[str, str]:
    """**通用版**:任何行业的 Case 都能用。返回 (文本, 来源)。
    行业无关 —— 因为 Case 已经是统一的形状。"""
    from fde_kernel import money

    if getattr(case, "revenue_stopped", False):
        # 停止态不走模型(避免把「已停止」写成 0–0 这类残数);给确定性文案。
        return _case_template(case), "template"

    chain = "\n".join(case.recalc_steps)
    _unknown = (case.unknowns[0][0] if case.unknowns else "未标注")
    if getattr(case, "revenue_stopped", False):
        _concl = (f"{case.headline_label}:该改造建议已停止 —— "
                  f"反向证据支持无可释放工时,不再给出金额区间。")
    else:
        _concl = (f"{case.headline_label}:{money(case.headline_low)} – "
                  f"{money(case.headline_high)} 元/年。")
    user = (
        f"【行业】{case.industry}\n"
        f"【当前证据状态】{getattr(case, 'gate_state', '') or '待补证据'}\n"
        f"【诊断结论】{_concl}\n"
        f"【参照系】{case.reference_note}\n"
        f"【推导链】\n{chain}\n"
        f"【我们还缺的那一个信息】{_unknown}\n"
        f"【客户基本情况】{case.inputs_summary or '未提供'}"
    )
    if not available():
        return _case_template(case), "template"

    base = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE).rstrip("/")
    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": CASE_SYSTEM},
                     {"role": "user", "content": user}],
        "temperature": 0.3,
        "max_tokens": 300,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "User-Agent": USER_AGENT,
                 "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = (data["choices"][0]["message"]["content"] or "").strip()
        return (text or _case_template(case)), "llm"
    except Exception as e:
        return _case_template(case) + f"\n\n(模型调用失败,已退回本地模板:{type(e).__name__})", "template"


def _case_template(case) -> str:
    """本地模板(断网/模型不通时的退路)—— 在屏幕上会真被人看到,所以句子必须是完整的。
    ❀ 旧版直接 `reference_note[:60]` 硬截,把句子从中间切断(出现过“……相当于单票毛利的 要把它算准……”)。"""
    from fde_kernel import money
    _stt = getattr(case, "gate_state", "") or "待补证据"
    if getattr(case, "revenue_stopped", False):
        return (f"先说状态:{_stt}。反向证据支持「无可释放工时」—— 该改造建议已停止,"
                f"不再给出金额区间;若能提供推翻该证据的原始数据,可再重新评估。")
    head = (f"先说状态:{_stt}。按你自己给的数算,"
            f"假设情景下的潜在优化空间是 {money(case.headline_low)} 到 "
            f"{money(case.headline_high)} 元/年。")
    ref = (case.reference_note or "").strip().replace("\n", " ")
    for sep in ("。", "——"):          # 取到第一句/第一个破折号为止,不切句子
        if sep in ref:
            ref = ref.split(sep)[0].strip() + "。"
            break
    if len(ref) > 120:
        ref = ref[:120] + "…"
    return f"{head}{ref}要把它算准,我还需要你材料里没说清楚的那几个数。"


def client_summary(a: Analysis, timeout: int = 25) -> tuple[str, str]:
    """返回 (文本, 来源)。来源 = 'llm' 或 'template'。"""
    if not available():
        return _template(a), "template"

    base = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE).rstrip("/")
    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _prompt(a)},
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        return (text or _template(a)), "llm"
    except Exception as e:  # 网络/额度/格式任何问题都退化为模板
        return _template(a) + f"\n\n(模型调用失败,已退回本地模板:{type(e).__name__})", "template"
