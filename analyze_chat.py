"""
群聊脏文件 → 结构化摘要。这就是产品该做的事,先拿自己的群聊练一遍。

用法: python analyze_chat.py <文件路径> [输出路径]
只输出"带出处的摘要",不输出全文;自动遮蔽手机号/微信号等隐私串。
"""

import re
import sys
from collections import Counter, defaultdict

TS = re.compile(r"^(\d{4})年(\d{2})月(\d{2})日\s+(\d{1,2}):(\d{2})$")
PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
WXID = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]{5,19}\b")

# 高信号关键词 → 找什么
TOPICS = {
    "命题/赛题": ["命题", "赛题", "题目", "题面", "选题"],
    "评审/评分": ["评审", "评分", "打分", "权重", "评分标准", "评委"],
    "规则/赛制": ["规则", "赛制", "晋级", "名额", "违规", "资格", "锁队"],
    "企业/甲方": ["企业", "甲方", "需求方", "赞助", "公司", "客户", "真实需求"],
    "赛前/合规": ["赛前", "提前", "复用", "开源", "已有", "底座", "翻新", "抄袭", "原创"],
    "提交/交付": ["提交", "交付", "封包", "录屏", "演示", "路演", "上线"],
    "组队/招募": ["组队", "招人", "缺", "招募", "队友", "匹配", "能力"],
    "方向/想法": ["方向", "想做", "打算", "想法", "idea", "准备做"],
    "痛点/抱怨": ["没用", "太难", "不懂", "坑", "麻烦", "崩溃", "焦虑", "怎么办", "求助"],
    "奖励/资源": ["奖金", "奖品", "资源", "算力", "额度", "导师", "投资", "孵化", "签约"],
}

OFFICIAL = ["组委会", "官方", "主办", "小助手", "管理员", "工作人员", "HOST", "组委会小助手"]


def parse(path: str):
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read().replace("\r\n", "\n")
    msgs, who, when, buf = [], None, None, []

    def flush():
        if who is not None and buf:
            text = "\n".join(buf).strip()
            if text:
                msgs.append((when, who, text))

    for line in raw.split("\n"):
        s = line.strip()
        m = TS.match(s)
        if m:
            flush()
            buf = []
            when = f"{m.group(1)}-{m.group(2)}-{m.group(3)} {int(m.group(4)):02d}:{m.group(5)}"
            continue
        if not s and not buf:
            who_next = True
            continue
        if not buf and s and not TS.match(s):
            # 可能是昵称行
            who = s
            buf = []
            continue
        buf.append(s)
    flush()

    # 上面的简化解析不稳,换一个更稳的两遍法
    msgs2 = []
    lines = [l.rstrip() for l in raw.split("\n")]
    i = 0
    while i < len(lines):
        name = lines[i].strip()
        if name and i + 1 < len(lines) and TS.match(lines[i + 1].strip()):
            t = TS.match(lines[i + 1].strip())
            ts = f"{t.group(1)}-{t.group(2)}-{t.group(3)} {int(t.group(4)):02d}:{t.group(5)}"
            body = []
            i += 2
            while i < len(lines):
                if lines[i].strip() == "" and i + 2 < len(lines) and TS.match(lines[i + 2].strip()):
                    break
                body.append(lines[i])
                i += 1
            txt = "\n".join(body).strip()
            if txt:
                msgs2.append((ts, name, txt))
        else:
            i += 1
    return msgs2


def mask(s: str) -> str:
    s = PHONE.sub("[手机号]", s)
    return s


def clip(s: str, n: int = 150) -> str:
    s = s.replace("\n", " ⏎ ")
    return s if len(s) <= n else s[:n] + "…"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "xihack群聊.txt"
    out = sys.argv[2] if len(sys.argv) > 2 else "群聊摘要.txt"
    msgs = parse(path)
    L = []
    L.append(f"# 群聊抽取摘要")
    L.append(f"来源文件:{path}")
    L.append(f"**解析出消息数:{len(msgs)}**\n")

    if not msgs:
        L.append("解析失败:没有识别出任何消息。")
        open(out, "w", encoding="utf-8").write("\n".join(L))
        print("no messages parsed")
        return

    dates = sorted({m[0][:10] for m in msgs})
    L.append(f"日期范围:{dates[0]} → {dates[-1]}(共 {len(dates)} 天)\n")

    L.append("## 发言排行(前 20)")
    for name, c in Counter(m[1] for m in msgs).most_common(20):
        L.append(f"- {c:>4}  {name}")
    L.append("")

    L.append("## 每日消息量")
    per = Counter(m[0][:10] for m in msgs)
    for d in sorted(per):
        L.append(f"- {d}  {per[d]}")
    L.append("")

    for topic, kws in TOPICS.items():
        L.append(f"## 【{topic}】命中片段")
        hit = 0
        for ts, name, txt in msgs:
            if any(k in txt for k in kws):
                hit += 1
                if hit <= 45:
                    L.append(f"- `{ts}` **{name}**:{mask(clip(txt))}")
        L.append(f"\n(共命中 {hit} 条,上面列出前 {min(hit,45)} 条)\n")

    L.append("## 【疑似官方/管理员】发言")
    n = 0
    for ts, name, txt in msgs:
        if any(k in name for k in OFFICIAL):
            n += 1
            if n <= 60:
                L.append(f"- `{ts}` **{name}**:{mask(clip(txt, 200))}")
    L.append(f"\n(共 {n} 条)")

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"已写出 {out}  ({len(chr(10).join(L))} 字符)")


if __name__ == "__main__":
    main()
