"""
电商问数 Agent 使用的大模型实例

集中初始化 OpenAI 兼容的 Chat Model，供节点或本地测试直接复用
这里区分两个实例：
- llm：主模型，负责生成和校正 SQL，质量优先
- fast_llm：轻量模型，负责关键词扩写和候选过滤，速度优先
"""

import os

from langchain.chat_models import init_chat_model

from app.conf.app_config import app_config


def _build_chat_model(model_name: str):
    """按统一参数初始化一个 OpenAI 兼容的 Chat Model"""

    return init_chat_model(
        model=model_name,
        # 硅基流动等服务兼容 OpenAI 协议时，可以使用 openai provider 接入
        model_provider="openai",
        base_url=app_config.llm.base_url,
        api_key=app_config.llm.api_key,
        # 字段扩展、SQL 生成更看重稳定性，所以这里关闭随机发散
        temperature=0,
    )


# 统一从配置读取模型三件套，节点只复用 llm，不重复初始化模型连接
llm = _build_chat_model(app_config.llm.model_name)

# 环境变量优先级最高，便于在不改配置文件的前提下做 A/B 对比
fast_model_name = (
    os.getenv("LLM_FAST_MODEL") or app_config.llm.fast_model_name or ""
).strip()

# 未配置轻量模型时直接复用主模型，行为与旧版本完全一致
fast_llm = _build_chat_model(fast_model_name) if fast_model_name else llm


if __name__ == "__main__":
    # 本地快速验证 LLM 配置是否能正常调用
    print(llm.invoke("你好").content)
    print(f"fast_model_name={fast_model_name or '(复用主模型)'}")
