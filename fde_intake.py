"""
进场包 · 第 1 步:丢材料进来 → 抽事实

设计原则(这三条是产品的根基,不能破):
  1. 每条结论都必须带【出处】,而且出处要能一键回到原材料。
  2. 抽取结果按【来源等级】分级:DIRECT / CONFIRMED / SINGLE / INFERRED。
  3. **模型给的每一条 quote,都要在原文里逐字校验** —— 校验不过的标红,不装作有效。
     (这是防幻觉的硬机制,也是"可自查"能成立的前提。)

分工:
  · 确定性层(不依赖模型):切分材料、扫数字/金额/百分比、遮蔽隐私
  · 模型层:读材料,输出**严格 JSON**,每条必须附原文片段
  · 校验层:拿模型给的片段回原文里找,找不到就判定为"无法回指"
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------- 正则
TS_LINE = re.compile(r"^(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})日?\s*(\d{1,2}):(\d{2})")
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
IDCARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
BANKCARD = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
MONEY = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(万|亿|千|元|块)")
PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
DATE = re.compile(r"\d{2,4}\s*[年\-/]\s*\d{1,2}\s*(?:[月\-/]\s*\d{1,2}\s*日?)?")

# 来源等级
DIRECT, CONFIRMED, SINGLE, INFERRED = "DIRECT", "CONFIRMED", "SINGLE", "INFERRED"

LEVEL_LABEL = {
    DIRECT: "原文直述",
    CONFIRMED: "多处互相印证",
    SINGLE: "仅一处提及",
    INFERRED: "模型推断(非原文)",
}


def mask(s: str) -> str:
    """遮蔽隐私串。返回 (文本, 遮蔽次数)。"""
    n = 0
    for rx, tag in ((PHONE, "[手机号]"), (IDCARD, "[身份证]"), (BANKCARD, "[卡号]")):
        s, k = rx.subn(tag, s)
        n += k
    return s, n


# ---------------------------------------------------------------- 切分
@dataclass
class Unit:
    idx: int
    locator: str
    text: str


def split_units(raw: str, wechat_threshold: int = 5) -> list[Unit]:
    """把材料切成带定位的单元。
    识别群聊/聊天记录格式就按 '时间 + 发言人' 切;否则按空行分段。"""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    ts_idx = [i for i, l in enumerate(lines) if TS_LINE.match(l.strip())]
    units: list[Unit] = []

    if len(ts_idx) >= wechat_threshold:
        # 聊天记录格式:昵称行 + 时间行 + 内容行
        i = 0
        n = 0
        while i < len(lines):
            name = lines[i].strip()
            if name and i + 1 < len(lines) and TS_LINE.match(lines[i + 1].strip()):
                ts = lines[i + 1].strip()
                body = []
                j = i + 2
                while j < len(lines):
                    if lines[j].strip() == "" and j + 2 < len(lines) and TS_LINE.match(lines[j + 2].strip()):
                        break
                    body.append(lines[j])
                    j += 1
                txt = "\n".join(body).strip()
                if txt:
                    units.append(Unit(n, f"{ts} {name}", txt))
                    n += 1
                i = j
            else:
                i += 1
    else:
        # 普通文本:按空行分段,过长的再按行切
        n = 0
        for block in re.split(r"\n\s*\n", text):
            block = block.strip()
            if not block:
                continue
            if len(block) > 800:
                for k, chunk in enumerate(re.split(r"\n", block)):
                    chunk = chunk.strip()
                    if chunk:
                        units.append(Unit(n, f"第 {n+1} 段第 {k+1} 行", chunk))
                        n += 1
            else:
                units.append(Unit(n, f"第 {n+1} 段", block))
                n += 1
    return units


# ---------------------------------------------------------------- 确定性扫描
@dataclass
class Scan:
    n_units: int = 0
    n_chars: int = 0
    masked: int = 0
    money: list = field(default_factory=list)
    percents: list = field(default_factory=list)
    dates: list = field(default_factory=list)
    locators: list = field(default_factory=list)


def scan(raw: str, units: list[Unit]) -> Scan:
    _, masked = mask(raw)
    return Scan(
        n_units=len(units),
        n_chars=len(raw),
        masked=masked,
        money=sorted({m.group(0) for m in MONEY.finditer(raw)}),
        percents=sorted({m.group(0) for m in PCT.finditer(raw)}),
        dates=sorted({m.group(0) for m in DATE.finditer(raw)})[:30],
        locators=[u.locator for u in units[:5]],
    )


# ---------------------------------------------------------------- 模型层
_SYSTEM_HEAD = (
    "你是一名前沿部署工程师(FDE),正在处理客户给来的一份杂乱材料(聊天记录、邮件、表格导出等)。\n"
    "你的任务不是总结,是**抽取可以用的事实**,并且为每一条提供原文出处。\n\n"
    "硬性要求:\n"
    "1. 只输出一个 JSON 对象,不要任何解释文字、不要 markdown 代码块标记。\n"
    "2. **每一条都必须带 quote 字段,内容必须是从材料里逐字复制的片段(不超过 60 字)**。\n"
    "   如果材料里找不到支撑某条结论的原句,就不要写这一条。\n"
    "3. 不要推断材料里没有的事实。宁可少写,不可编造。\n"
    "4. confidence 只能取 high / medium / low:\n"
    "   high = 原文直述且含具体数字或明确承诺;\n"
    "   medium = 原文直述但不具体,或多处说法略有出入;\n"
    "   low  = 仅一处提及,或带情绪/口语转述。\n"
    "5. 涉及人名只写材料里出现的称呼,不要猜测真实身份。\n\n"
    "输出结构(严格遵守,空的话给空数组):\n"
    "{\n"
    '  "facts":     [{"kind":"需求|约束|数字|人物|时间|风险|其他","text":"...","quote":"...","source":"...","confidence":"high|medium|low"}],\n'
    '  "people":    [{"name":"...","role":"材料里的说法","quote":"..."}],\n'
    '  "timeline":  [{"when":"...","what":"...","quote":"..."}],\n'
    '  "conflicts": [{"a":"...","b":"...","why":"为什么算矛盾","quote_a":"...","quote_b":"..."}],\n'
    '  "unknowns":  [{"what":"还不知道什么","why_needed":"为什么这个必须知道","how_to_get":"公开信息|问客户|内部数据"}],\n'
)


# 默认要抽的参数(餐饮口径)。界面会按当前行业模块的 INPUTS 传一套进来 ——
# 换行业时「从材料里预填哪些数」也跟着换,不会拿门店数去套物流的材料。
DEFAULT_PREFILL_FIELDS = {
    "store_count": "几家店",
    "rev_per_store": "单店月流水",
    "emp_per_store": "单店员工数",
}


def system_prompt(prefill_fields: dict | None = None) -> str:
    """按行业拼 system 提示。prefill_fields = {参数键: 中文说法}。"""
    fields = prefill_fields or DEFAULT_PREFILL_FIELDS
    prefill_json = ",".join(f'"{k}":{{"value":null,"quote":""}}' for k in fields)
    labels = " / ".join(fields.values())
    return (
        _SYSTEM_HEAD
        + f'  "prefill":   {{{prefill_json}}}\n'
        + "}\n\n"
        + f"关于 prefill:只有材料里**明确出现**「{labels}」时才填,并附原句;否则 value 给 null。"
    )


SYSTEM = system_prompt()          # 默认餐饮口径(兼容既有调用与 check 脚本)


def build_user_prompt(units: list[Unit], max_chars: int = 14000) -> tuple[str, bool]:
    """把材料拼成带定位的文本。返回 (文本, 是否被截断)。"""
    parts, total, cut = [], 0, False
    for u in units:
        seg = f"[{u.locator}]\n{u.text}\n"
        if total + len(seg) > max_chars:
            cut = True
            break
        parts.append(seg)
        total += len(seg)
    return "\n".join(parts), cut


def parse_json(text: str) -> dict:
    """模型偶尔会带代码块或前后废话,这里宽容解析。"""
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}
    return {}


CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
UNIT_MULT = {"亿": 100_000_000, "万": 10_000, "千": 1_000, "百": 100}


def _cn_arabic(s: str) -> str:
    """中文数字 → 阿拉伯数字(含「三十」这类复合)。保守:只处理常见形态。"""
    def tens(m):
        a, b = m.group(1), m.group(2)
        t = (CN_DIGIT.get(a, 1) if a else 1) * 10
        o = CN_DIGIT.get(b, 0) if b else 0
        return str(t + o)
    s = re.sub(r"([一二两三四五六七八九])?十([一二两三四五六七八九])?", tens, s)
    return re.sub(r"[零一二两三四五六七八九]", lambda m: str(CN_DIGIT.get(m.group(0), m.group(0))), s)


def to_number(v):
    """把“约 30 万/月”“八个人”“30万”“一个月三十万”这类说法转成数字。转不了返回 None。
    不猜单位含义 —— 只做量的换算,不管它是月还是年。

    修正(2026-09-28 验收):旧版取「第一个数字 + 任意位置的单位」,
    「一个月三十万上下」会被算成 1 × 万 = 10000。现在:
      ① 先折叠中文数字(三十→30);
      ② 数字与单位就近绑定,优先取最后一个「数字+单位」;
      ③ 区间取小值。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    s2 = _cn_arabic(s)

    # ① 区间:「10-20万」「30万-40万」→ 取小的那个数(单位可能跟在后一个数上)
    m2 = re.search(r"(\d+(?:\.\d+)?)\s*(亿|万|千|百)?\s*[-~到至]\s*(\d+(?:\.\d+)?)\s*(亿|万|千|百)?", s2)
    if m2:
        lo, hi = float(m2.group(1)), float(m2.group(3))
        mult = UNIT_MULT.get(m2.group(4) or m2.group(2) or "", 1)
        return min(lo, hi) * mult

    # ② 数字与单位就近绑定,取最后一个(金额通常写在描述尾部;避免「一个月」的 1 抢跑)
    hits = list(re.finditer(r"(\d+(?:\.\d+)?)\s*(亿|万|千|百)", s2))
    if hits:
        h = hits[-1]
        return float(h.group(1)) * UNIT_MULT[h.group(2)]

    # ③ 没有单位:取第一个数
    m = re.search(r"(\d+(?:\.\d+)?)", s2)
    if not m:
        return None
    return float(m.group(1))


def normalize_prefill(prefill: dict) -> dict:
    """把 prefill 里的文本值换成数字,保留原文本备查。"""
    out = {}
    for k, v in (prefill or {}).items():
        if not isinstance(v, dict):
            continue
        raw = v.get("value")
        out[k] = {"value": to_number(raw), "value_raw": raw, "quote": v.get("quote", "")}
    return out


def empty_result() -> dict:
    return {"facts": [], "people": [], "timeline": [], "conflicts": [],
            "unknowns": [], "prefill": {}}


# ---------------------------------------------------------------- 校验层
def _norm(s: str) -> str:
    """归一化:去空白、全角转半角、去掉各类引号,提高回指命中率。"""
    if not s:
        return ""
    s = s.replace("\u3000", " ")
    out = []
    for ch in s:
        o = ord(ch)
        if o == 0x3000:
            out.append(" ")
        elif 0xFF01 <= o <= 0xFF5E:          # 全角 → 半角
            out.append(chr(o - 0xFEE0))
        elif ch in "“”‘’「」『』\"'":
            continue
        else:
            out.append(ch)
    return re.sub(r"\s+", "", "".join(out))


def verify_quotes(result: dict, raw: str) -> dict:
    """回指校验:模型给的每条 quote,能不能在原材料里逐字找到。
    这是防幻觉的硬闸门。"""
    hay = _norm(mask(raw)[0])
    stats = {"total": 0, "ok": 0, "fail": 0, "details": []}

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
        elif isinstance(obj, str) and (path.endswith("quote") or path.endswith("quote_a") or path.endswith("quote_b")):
            q = obj.strip()
            if not q:
                return
            stats["total"] += 1
            ok = _norm(q) in hay
            if ok:
                stats["ok"] += 1
            else:
                stats["fail"] += 1
                if len(stats["details"]) < 12:
                    stats["details"].append((path, q[:60]))

    walk(result)
    return stats


def apply_levels(facts: list[dict], verif: dict) -> list[dict]:
    """给每条 fact 定级:回指失败的直接降级并打标。"""
    failed = {p for p, _ in verif["details"]}
    out = []
    for i, f in enumerate(facts):
        f = dict(f)
        p = f"facts[{i}].quote"
        q_ok = p not in failed
        conf = (f.get("confidence") or "medium").lower()
        if not q_ok:
            f["level"] = INFERRED
            f["quote_ok"] = False
        else:
            f["quote_ok"] = True
            f["level"] = {"high": DIRECT, "medium": CONFIRMED, "low": SINGLE}.get(conf, CONFIRMED)
        out.append(f)
    return out


# ---------------------------------------------------------------- 便捷入口
def run(raw: str, chat_fn, prefill_fields: dict | None = None) -> dict:
    """完整跑一遍。chat_fn(system, user) -> str|None。
    prefill_fields:当前行业要抽的参数(不给就用餐饮默认)。"""
    units = split_units(raw)
    sc = scan(raw, units)
    user, cut = build_user_prompt(units)

    res = empty_result()
    model_used = False
    err = None
    if chat_fn is not None:
        txt = chat_fn(system_prompt(prefill_fields), user)
        if txt:
            parsed = parse_json(txt)
            if parsed:
                for k in res:
                    if k in parsed:
                        res[k] = parsed[k]
                model_used = True
        else:
            err = "模型未返回内容"
    else:
        err = "未接入模型(只有确定性扫描)"

    verif = verify_quotes(res, raw)
    res["facts"] = apply_levels(res.get("facts") or [], verif)
    res["prefill"] = normalize_prefill(res.get("prefill") or {})

    return {
        "units": units, "scan": sc, "result": res,
        "verify": verif, "model_used": model_used,
        "truncated": cut, "error": err,
    }
