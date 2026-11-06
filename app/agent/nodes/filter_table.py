"""
表信息过滤节点

负责在合并后的候选表结构中筛选出当前问题真正需要的表和字段
这里让大模型只返回“保留哪些表和字段”的选择结果，真正的结构裁剪仍由程序完成
"""

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt

# 过滤任务只需要判断字段语义，不需要真实取值样例和别名
# 保留 role 是因为提示词要求模型在跨表时选出 join 所需的主外键字段
FILTER_COLUMN_FIELDS = ("name", "type", "role", "description")


def build_filter_payload(table_infos: list[TableInfoState]) -> str:
    """构建过滤用的精简表结构 YAML

    examples 里是字段真实取值、alias 是同义词，体积都不小，
    但对“哪些字段和问题相关”这个判断几乎没有帮助，发给模型只会拖慢响应。
    """

    trimmed_tables = [
        {
            "name": table_info.get("name", ""),
            "role": table_info.get("role", ""),
            "description": table_info.get("description", ""),
            "columns": [
                {field: column.get(field, "") for field in FILTER_COLUMN_FIELDS}
                for column in table_info.get("columns", [])
            ],
        }
        for table_info in table_infos
    ]
    return yaml.dump(trimmed_tables, allow_unicode=True, sort_keys=False)


def apply_selection(
    table_infos: list[TableInfoState], selection: dict
) -> list[TableInfoState]:
    """按模型给出的选择结果裁剪原始表结构

    模型只负责选择，裁剪由程序完成，避免模型重写复杂结构时出错。
    """

    if not isinstance(selection, dict):
        raise ValueError(f"过滤结果不是 JSON 对象：{selection!r}")

    filtered_table_infos: list[TableInfoState] = []
    for table_info in table_infos:
        name = table_info["name"]
        if name not in selection:
            continue

        selected_columns = set(selection[name] or [])
        columns = [
            column
            for column in table_info["columns"]
            if column["name"] in selected_columns
        ]
        # 返回新对象，避免直接改写 state 里已有的表结构
        filtered_table_infos.append({**table_info, "columns": columns})

    return filtered_table_infos


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """根据用户问题裁剪候选表结构上下文"""

    writer = runtime.stream_writer
    step = "过滤表信息"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        query = state["query"]
        table_infos: list[TableInfoState] = state["table_infos"]

        # table_infos 是嵌套结构，转成 YAML 后更适合放进提示词，也保留中文字段说明
        prompt = PromptTemplate(
            template=load_prompt("filter_table_info"),
            input_variables=["query", "table_infos"],
        )
        # filter_table_info prompt 要求模型只输出 JSON 对象：表名 -> 字段名列表
        output_parser = JsonOutputParser()
        # LCEL 管道：填充提示词 -> 调用模型 -> 解析 JSON
        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {
                "query": query,
                "table_infos": build_filter_payload(table_infos),
            }
        )
        filtered_table_infos = apply_selection(table_infos, result)

        logger.info(
            f"过滤后的表信息：{[filtered_table_info['name'] for filtered_table_info in filtered_table_infos]}"
        )
        writer({"type": "progress", "step": step, "status": "success"})
        return {"table_infos": filtered_table_infos}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
