"""
问数链路基准测试脚本

对 /api/query 连续发起多次请求，从 SSE 事件时间戳还原每个节点的耗时，
输出中位数统计。用于在改动前后对比性能，避免被单次采样和 LLM 抖动误导。

用法:
    uv run python tests/bench_query.py --runs 5
    uv run python tests/bench_query.py --runs 5 --url http://127.0.0.1:8002/api/query
"""

import argparse
import json
import statistics
import sys
import time
from collections import OrderedDict

import httpx

DEFAULT_URL = "http://127.0.0.1:8001/api/query"
DEFAULT_QUERY = "统计华北地区的销售总额"


def run_once(url: str, query: str) -> dict:
    """执行一次问数，返回各节点耗时与总耗时"""

    started = time.perf_counter()
    marks: list[tuple[float, dict]] = []
    result = None
    sql = ""

    with httpx.Client(timeout=300) as client:
        with client.stream("POST", url, json={"query": query}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                marks.append((time.perf_counter() - started, event))
                if event["type"] == "error":
                    raise RuntimeError(f"后端返回错误：{event['message']}")
                if event["type"] == "meta":
                    sql = event.get("sql", "")
                if event["type"] == "result":
                    result = event["data"]

    if result is None:
        raise RuntimeError("没有收到 result 事件")

    spans: "OrderedDict[str, float]" = OrderedDict()
    opened: dict[str, float] = {}
    for at, event in marks:
        if event.get("type") != "progress":
            continue
        step = event["step"]
        if event["status"] == "running":
            opened[step] = at
        elif step in opened:
            spans[step] = at - opened[step]

    return {
        "total_ms": (marks[-1][0] if marks else 0.0) * 1000,
        "steps": {step: cost * 1000 for step, cost in spans.items()},
        "rows": len(result) if isinstance(result, list) else 1,
        "sql": sql,
    }


def summarize(values: list[float]) -> dict:
    return {
        "p50": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def main():
    parser = argparse.ArgumentParser(description="问数链路基准测试")
    parser.add_argument("--url", default=DEFAULT_URL, help="接口地址")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="测试问题")
    parser.add_argument("--runs", type=int, default=5, help="统计样本数")
    parser.add_argument("--warmup", type=int, default=1, help="预热次数，不计入统计")
    args = parser.parse_args()

    for index in range(args.warmup):
        print(f"预热 {index + 1}/{args.warmup} ...", flush=True)
        run_once(args.url, args.query)

    samples = []
    for index in range(args.runs):
        print(f"采样 {index + 1}/{args.runs} ...", flush=True)
        samples.append(run_once(args.url, args.query))

    totals = [sample["total_ms"] for sample in samples]
    total_stats = summarize(totals)

    step_names = list(samples[0]["steps"].keys())
    step_stats = {
        step: summarize([sample["steps"].get(step, 0.0) for sample in samples])
        for step in step_names
    }

    print(f"\n=== {args.query} ===")
    print(f"接口 {args.url}    样本 {args.runs} 次（预热 {args.warmup} 次不计入）\n")
    print(f"{'节点':<16}{'p50':>10}{'min':>10}{'max':>10}")
    print("-" * 46)
    for step in step_names:
        stats = step_stats[step]
        print(
            f"{step:<16}{stats['p50']:>9.0f}ms"
            f"{stats['min']:>9.0f}ms{stats['max']:>9.0f}ms"
        )
    print("-" * 46)
    print(
        f"{'端到端':<16}{total_stats['p50']:>9.0f}ms"
        f"{total_stats['min']:>9.0f}ms{total_stats['max']:>9.0f}ms"
    )

    rows = {sample["rows"] for sample in samples}
    print(f"\n结果行数: {rows}")
    print(f"SQL 示例: {samples[-1]['sql'][:120]}")

    if any(sample["rows"] == 0 for sample in samples):
        print("BENCH_FAILED: 出现空结果")
        sys.exit(1)


if __name__ == "__main__":
    main()
