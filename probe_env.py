"""
.env.local 结构探针 —— 只报告文件的**结构**,绝不打印任何值。

输出:字节数 / 是否有 BOM / 行数 / 每行是注释还是键值 / 键名 / 值是否为空。
值本身永远不打印,连长度都不打印(长度也可能泄露信息)。
"""

import re
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else ".env.local"
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

with open(PATH, "rb") as f:
    raw = f.read()

print(f"文件: {PATH}")
print(f"字节数: {len(raw)}")
print(f"开头 3 字节(十六进制,用于判断 BOM): {raw[:3].hex(' ')}")

for enc in ("utf-8-sig", "utf-8", "utf-16", "gbk"):
    try:
        text = raw.decode(enc)
        print(f"可解码编码: {enc}")
        break
    except (UnicodeDecodeError, UnicodeError) as e:
        print(f"  {enc} 解码失败: {type(e).__name__}")
else:
    print("所有编码都解不开 —— 文件可能损坏")
    sys.exit(1)

lines = text.splitlines()
print(f"行数: {len(lines)}")
print(f"含 '=' 的行数: {sum(1 for l in lines if '=' in l)}")
print(f"含 'OPENAI_API_KEY' 子串的行数: {sum(1 for l in lines if 'OPENAI_API_KEY' in l)}")
print(f"非 ASCII 字符数: {sum(1 for c in text if ord(c) > 127)}")
print()
print("逐行结构:")
for i, l in enumerate(lines, 1):
    s = l.strip().lstrip("\ufeff")
    if not s:
        print(f"  {i:>3}: (空行)")
    elif s.startswith("#"):
        print(f"  {i:>3}: 注释")
    elif "=" in s:
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        k_ok = "键名合法" if KEY_RE.match(k) else "⚠ 键名含异常字符(可能有 BOM/空格/不可见字符)"
        v_state = "值非空" if v else "⚠ 值为空"
        print(f"  {i:>3}: 键值行  键名=[{k}]  {k_ok}  {v_state}")
    else:
        print(f"  {i:>3}: 既不是注释也不是键值行 —— 这行大概只有内容没有 '=' 前缀")
