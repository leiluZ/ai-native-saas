from langchain.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
import os
from typing import Optional


@tool
def get_weather(location: str) -> str:
    """
    Get the current weather for a given location.

    Args:
        location: The city name or location to check weather for, e.g., "Beijing", "Shanghai"

    Returns:
        Weather information including temperature and conditions.
    """
    weather_data = {
        "beijing": "Sunny, 25°C, humidity 45%",
        "shanghai": "Cloudy, 28°C, humidity 60%",
        "guangzhou": "Rainy, 32°C, humidity 85%",
        "shenzhen": "Partly cloudy, 30°C, humidity 70%",
    }
    location_lower = location.lower()
    return weather_data.get(location_lower, f"Weather data not available for {location}")


@tool
def get_current_time(timezone: Optional[str] = "Asia/Shanghai") -> str:
    """
    Get the current time in a specific timezone.

    Args:
        timezone: Optional timezone string (default: Asia/Shanghai).
                  Common values: "Asia/Shanghai", "America/New_York", "Europe/London"

    Returns:
        Current time formatted as ISO 8601 string.
    """
    from datetime import datetime
    import pytz

    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz).isoformat()
        return f"Current time in {timezone}: {current_time}"
    except Exception as e:
        return f"Error getting time: {str(e)}"


@tool
def calculate(expression: str) -> str:
    """
    Calculate a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate, e.g., "2 + 3 * 4", "sqrt(16)"

    Returns:
        The result of the calculation.
    """
    import math

    try:
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith('_')}
        result = eval(expression, {"__builtins__": None}, allowed_names)
        return f"Result: {result}"
    except Exception as e:
        return f"Calculation error: {str(e)}"


def get_llm() -> BaseChatModel:
    """
    根据环境变量选择 LLM 提供商。

    优先级：
    1. OLLAMA_MODEL - 使用本地 Ollama
    2. OPENAI_API_KEY - 使用 OpenAI

    Returns:
        配置好的 LLM 实例
    """
    ollama_model = os.environ.get("OLLAMA_MODEL")

    if ollama_model:
        # 使用本地 Ollama
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=ollama_model,
            temperature=0.7,
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        )
    else:
        # 使用 OpenAI
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Either OLLAMA_MODEL or OPENAI_API_KEY environment variable must be set")

        return ChatOpenAI(
            model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
            api_key=api_key,
            temperature=0.7
        )


def create_agent() -> AgentExecutor:
    llm = get_llm()

    tools = [get_weather, get_current_time, calculate]

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant. Use the available tools to answer questions.

        If you cannot answer the question or if a tool call fails, provide a friendly fallback message.

        Available tools:
        - get_weather: Get weather information
        - get_current_time: Get current time
        - calculate: Perform mathematical calculations

        Respond with either:
        - A tool call to get information
        - A final answer directly if you have enough information

        If a tool call fails, provide a human-readable fallback message."""),
        ("user", "{input}"),
        ("agent_scratchpad", "{agent_scratchpad}")
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5
    )

    return executor


async def run_agent(prompt: str) -> str:
    try:
        executor = create_agent()
        result = await executor.ainvoke({"input": prompt})
        return result.get("output", "No response")
    except Exception as e:
        return f"Sorry, I encountered an error while processing your request: {str(e)}. Please try again later."
