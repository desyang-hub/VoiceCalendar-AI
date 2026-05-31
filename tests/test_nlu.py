#!/usr/bin/env python
"""NLU 意图解析测试脚本 - 使用真实 LLM 验证各种语音输入。

用法:
    python tests/test_nlu.py          # 使用 settings.json 中的配置
    python tests/test_nlu.py --model qwen-plus  # 指定模型
    python tests/test_nlu.py --debug   # 打印原始 LLM 返回
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# 将项目根目录加入 sys.path（tests/ 的父目录）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicecalendar.core import settings as settings_module
from voicecalendar.services.nlu_parser import NLUParser, ParseIntent

TEST_CASES = [
    # -- 添加日程 (6 cases) --
    {"input": "明天下午三点开会", "expect": "add"},
    {"input": "后天早上九点和客户吃饭", "expect": "add"},
    {"input": "下周一上午十点在会议室A做产品评审", "expect": "add"},
    {"input": "本周三下午两点到四点参加技术分享", "expect": "add"},
    {"input": "三天后下午五点半去健身房", "expect": "add"},
    {"input": "今天下午四点和团队做个周会", "expect": "add"},

    # -- 查询日程 (4 cases) --
    {"input": "今天有什么安排", "expect": "query"},
    {"input": "明天有日程吗", "expect": "query"},
    {"input": "这周的所有日程", "expect": "query"},  # query/list 均可接受
    {"input": "下周一有什么", "expect": "query"},

    # -- 删除日程 (3 cases) --
    {"input": "取消明天的会议", "expect": "delete"},
    {"input": "删除后天的产品评审", "expect": "delete"},
    {"input": "去掉今天下午的安排", "expect": "delete"},

    # -- 边缘情况 (2 cases) --
    {"input": "帮我预约一个下周三早上10点的牙医", "expect": "add"},
    {"input": "提醒我明天中午12点交报告", "expect": "add"},
]

ACTION_NAMES = {
    ParseIntent.Action.ADD: "add(添加)",
    ParseIntent.Action.QUERY: "query(查询)",
    ParseIntent.Action.DELETE: "delete(删除)",
    ParseIntent.Action.LIST: "list(列出)",
    ParseIntent.Action.UNKNOWN: "unknown(未知)",
}


def action_name(action):
    return ACTION_NAMES.get(action, str(action))


def print_event(ev):
    if ev is None:
        return
    print(f"    标题: {ev.title}")
    print(f"    日期: {ev.start_date}")
    print(f"    开始: {ev.start_time}")
    if ev.end_time:
        print(f"    结束: {ev.end_time}")
    if ev.location:
        print(f"    地点: {ev.location}")
    if ev.description:
        print(f"    描述: {ev.description}")


def main():
    parser = argparse.ArgumentParser(description="NLU 意图解析测试")
    parser.add_argument("--model", default=None, help="覆盖模型名称")
    parser.add_argument("--debug", action="store_true", help="打印原始 LLM 返回")
    args = parser.parse_args()

    nlu_cfg = settings_module.get_nlu_config()
    api_key = nlu_cfg.get("api_key", "")
    base_url = nlu_cfg.get("base_url", "")
    model = args.model or nlu_cfg.get("model", "gpt-4o")

    if not api_key:
        print("错误: 未找到 NLU API Key")
        sys.exit(1)

    print("=" * 70)
    print("NLU 意图解析测试")
    print("=" * 70)
    print(f"  模型: {model}")
    print(f"  Base URL: {base_url}")
    print(f"  今日: {date.today().isoformat()}")
    print(f"  测试用例: {len(TEST_CASES)} 个")
    print("=" * 70)
    print()

    nlu = NLUParser(api_key=api_key, base_url=base_url, model=model)
    if not nlu.is_ready:
        print("错误: NLU 客户端未就绪")
        sys.exit(1)

    passed = 0
    failed = 0
    errors = 0
    llm_hits = 0  # 统计 LLM 直接命中数 (confidence >= 0.8)

    for i, tc in enumerate(TEST_CASES, 1):
        inp = tc["input"]
        expect = tc["expect"]
        print(f"[{i}/{len(TEST_CASES)}] 输入: {inp}")
        print(f"     期望: {expect}")

        try:
            intent = nlu.parse(inp)
            actual_str = action_name(intent.action)

            # query 和 list 视为等价（都是查询类操作）
            if expect == "query":
                ok = actual_str.startswith(("query", "list"))
            else:
                ok = actual_str.startswith(expect)

            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1

            # 统计 LLM 命中
            if intent.confidence >= 0.8:
                llm_hits += 1

            mark = "[OK]" if ok else "[FAIL]"
            print(f"  {mark} {status} -> 实际: {actual_str} (confidence={intent.confidence:.2f})")

            if intent.event:
                print_event(intent.event)
            if intent.query_keyword:
                print(f"    查询关键词: {intent.query_keyword}")
            if intent.delete_keyword:
                print(f"    删除关键词: {intent.delete_keyword}")

        except Exception as e:
            errors += 1
            print(f"  [ERR] 异常: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()

        print()

    total = passed + failed + errors
    print("=" * 70)
    print("测试汇总")
    print("=" * 70)
    print(f"  总计: {total}")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(f"  异常: {errors}")
    print(f"  LLM 命中: {llm_hits}/{total}")
    rate = (passed / total * 100) if total > 0 else 0
    print(f"  通过率: {rate:.1f}%")
    print("=" * 70)

    # 调试模式: 测试 raw LLM 响应
    if args.debug:
        print()
        print("=" * 70)
        print("原始 LLM 响应调试")
        print("=" * 70)
        import datetime

        from voicecalendar.services.nlu_parser import SYSTEM_PROMPT

        for inp, expect in [("明天下午三点开会", "add"),
                             ("今天有什么安排", "query"),
                             ("取消明天的会议", "delete")]:
            print(f"\n--- 输入: {inp} ---")
            try:
                import openai as _openai

                now = datetime.datetime.now()
                ref = date.today()
                prompt = SYSTEM_PROMPT.format(
                    current_date=ref.isoformat(),
                    current_time=now.strftime("%H:%M"),
                )
                client = _openai.OpenAI(api_key=api_key, base_url=base_url)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": inp},
                    ],
                    temperature=0.1,
                    max_tokens=500,
                    response_format={"type": "json_object"},
                )
                raw = resp.choices[0].message.content
                print(f"  原始响应: {raw[:200]}")
                data = json.loads(raw)
                print(f"  JSON action: {data.get('action')}")
            except Exception as e:
                print(f"  错误: {e}")


if __name__ == "__main__":
    main()
