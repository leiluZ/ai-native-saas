"""LLM 客户端模块 - 统一管理 LLM 连接"""

from langchain_core.language_models import BaseChatModel
import os


class LLMClient:
    """LLM 客户端封装类"""

    @staticmethod
    def get_llm() -> BaseChatModel:
        """
        获取配置的 LLM 实例

        Returns:
            BaseChatModel: 配置好的 LLM 实例

        Raises:
            ValueError: 当既没有配置 OLLAMA_MODEL 也没有配置 OPENAI_API_KEY 时
            ImportError: 当需要的依赖未安装时
        """
        ollama_model = os.environ.get("OLLAMA_MODEL")

        if ollama_model:
            try:
                from langchain_ollama import ChatOllama

                return ChatOllama(
                    model=ollama_model,
                    temperature=0.7,
                    base_url=os.environ.get(
                        "OLLAMA_BASE_URL", "http://localhost:11434"
                    ),
                )
            except ImportError:
                raise ImportError(
                    "langchain-ollama 未安装，请运行 pip install langchain-ollama"
                )

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("必须设置 OLLAMA_MODEL 或 OPENAI_API_KEY 环境变量")

        try:
            from langchain_openai import ChatOpenAI

            openai_base_url = os.environ.get("OPENAI_BASE_URL")

            return ChatOpenAI(
                model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
                api_key=api_key,
                temperature=0.7,
                base_url=openai_base_url if openai_base_url else None,
            )
        except ImportError:
            raise ImportError(
                "langchain-openai 未安装，请运行 pip install langchain-openai"
            )


def get_llm() -> BaseChatModel:
    """
    获取 LLM 实例（便捷函数）

    Returns:
        BaseChatModel: 配置好的 LLM 实例
    """
    return LLMClient.get_llm()
