"""
问数结果元信息构建

把一次问数链路里已经算出来的 SQL、召回关键词和指标口径整理成前端可展示的
meta 事件。这里只做纯数据整形，不访问任何外部依赖，方便单独测试。
"""

import re

from app.agent.state import DataAgentState

# 关键词展示数量上限，避免原始问题切出的长尾词把界面撑满
MAX_KEYWORDS = 12

# 整行的 markdown 围栏，例如 ``` 或 ```sql
_FENCE_LINE = re.compile(r"^```[a-zA-Z]*\s*$", re.MULTILINE)

# 行首带语言标记的围栏，例如 ```sql SELECT
_OPEN_FENCE = re.compile(r"^```[a-zA-Z]*\s*")

# 行尾闭合围栏
_CLOSE_FENCE = re.compile(r"\s*```$")


def normalize_sql(raw: str) -> str:
    """把模型返回的 SQL 整理成适合直接展示的纯文本

    生成节点的提示词要求模型只输出 SQL，但模型偶尔仍会包一层 markdown 代码块，
    展示前统一去掉围栏，避免前端出现多余的反引号。
    """

    sql = (raw or "").strip()
    if not sql:
        return ""

    # 先去掉整行的围栏，再兜底处理单行内联的 ```sql SELECT ... ```
    sql = _FENCE_LINE.sub("", sql)
    sql = _OPEN_FENCE.sub("", sql)
    sql = _CLOSE_FENCE.sub("", sql)
    return sql.strip()


def _display_keywords(state: DataAgentState) -> list[str]:
    """整理用于展示的召回关键词

    关键词抽取节点会把原始问题本身也塞进列表，作为切分不准时的检索兜底。
    这个问题对检索有用，但直接展示会显得很怪，所以这里过滤掉原始问题。
    """

    query = (state.get("query") or "").strip()
    keywords: list[str] = []

    for keyword in state.get("keywords") or []:
        text = str(keyword).strip()
        if not text or text == query or text in keywords:
            continue
        keywords.append(text)
        if len(keywords) >= MAX_KEYWORDS:
            break

    return keywords


def _display_metrics(state: DataAgentState) -> list[dict]:
    """整理用于展示的指标口径"""

    metrics: list[dict] = []

    for metric in state.get("metric_infos") or []:
        name = (metric or {}).get("name")
        if not name:
            continue
        metrics.append(
            {
                "name": name,
                "description": (metric.get("description") or "").strip(),
                "alias": [str(item) for item in metric.get("alias") or []],
            }
        )

    return metrics


def build_meta_event(state: DataAgentState) -> dict:
    """把状态里的可解释信息整理成一条可直接写入流的事件"""

    return {
        "type": "meta",
        "sql": normalize_sql(state.get("sql") or ""),
        "keywords": _display_keywords(state),
        "metrics": _display_metrics(state),
    }
