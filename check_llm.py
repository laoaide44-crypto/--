"""
检查 LLM 是否配好 —— 会真打一次接口,但**绝不打印密钥**。

跑法:
    cd D:\\学习工具\\Python\\xihack-fde
    $env:PYTHONIOENCODING="utf-8"
    python check_llm.py
"""

import sys

import fde_llm
import fde_model as M

HINT_VALUE = "<你的密钥>"


def main() -> int:
    st = fde_llm.status()
    print("LLM 配置状态")
    print(f"  已配置   : {st['configured']}")
    print(f"  配置来源 : {st['source']}")
    print(f"  端点     : {st['base']}")
    print(f"  模型     : {st['model']}")
    print()

    print("诊断(只看键名与状态,从不读值)")
    print(f"  .env.local 存在 : {st['file_exists']}")
    print(f"  文件里定义的键  : {st['vars_found'] or '(无)'}")
    print(f"  实际采用的键    : {st['key_picked'] or '(未找到可用的键)'}")
    print(f"  值是否占位符    : {st['is_placeholder']}")
    print(f"  读取错误        : {st['error'] or '(无)'}")
    print()

    if not st["configured"]:
        if st["is_placeholder"]:
            print(">> 原因:文件里那行的值还是占位符,把它换成真实密钥再存一次。")
        elif st["file_exists"] and not st["key_picked"]:
            print(">> 原因:文件里没有 OPENAI_API_KEY / DEEPSEEK_API_KEY 这样的键名。")
            print(f"   请写一行:  OPENAI_API_KEY={HINT_VALUE}")
        elif not st["file_exists"]:
            print(">> 原因:.env.local 不在预期位置。")
            print(f"   预期路径: {fde_llm.ENV_FILE}")
        else:
            print(">> 未配置。两个办法(都不需要经过对话):")
            print(f"   A) 在同目录建 .env.local,写一行 OPENAI_API_KEY={HINT_VALUE}")
            print(f"      位置: {fde_llm.ENV_FILE}")
            print("   B) 自己设用户级环境变量 OPENAI_API_KEY")
        print()
        print("没配也能跑:应用会自动退回本地模板,不影响演示。")
        return 0

    print("真打一次接口测试……")
    a = M.analyze(12, 300000, 8, 0.27)
    text, src = fde_llm.client_summary(a)
    print(f"  返回来源 : {src}")
    if src == "llm":
        print("  [OK] 模型接通")
        print("  模型输出 :")
        for line in text.splitlines():
            print(f"    {line}")
        return 0

    print("  [FAIL] 调用了但失败,已退回模板。返回内容:")
    for line in text.splitlines():
        print(f"    {line}")
    print()
    print("  常见原因:密钥无效 / 余额不足 / 网络不通")
    return 1


if __name__ == "__main__":
    sys.exit(main())
