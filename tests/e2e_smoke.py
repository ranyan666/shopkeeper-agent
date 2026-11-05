import json
import sys

import httpx

URL = "http://127.0.0.1:8001/api/query"
QUERY = "统计华北地区的销售总额"
EXPECTED_AMOUNT = 41099.5


def main():
    events = []
    result = None

    with httpx.Client(timeout=180) as client:
        with client.stream("POST", URL, json={"query": QUERY}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                events.append(event)
                print(
                    f"{event.get('type')}: "
                    f"{event.get('step', '')} "
                    f"{event.get('status', '')}"
                )
                if event["type"] == "error":
                    print(f"E2E_FAILED: {event['message']}")
                    sys.exit(1)
                if event["type"] == "result":
                    result = event["data"]

    assert events, "没有收到 SSE 事件"
    assert result, "没有收到最终结果"
    assert len(result) == 1, f"结果行数错误：{result}"
    actual_amount = float(result[0]["销售总额"])
    assert abs(actual_amount - EXPECTED_AMOUNT) < 0.01, (
        f"结果错误：预期 {EXPECTED_AMOUNT}，实际 {actual_amount}"
    )
    print(f"E2E_OK: 销售总额={actual_amount}")


if __name__ == "__main__":
    main()