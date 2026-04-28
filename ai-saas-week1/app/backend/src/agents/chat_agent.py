from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import os
import re
import json
from typing import Optional, Literal


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


tools_map = {
    "get_weather": get_weather,
    "get_current_time": get_current_time,
    "calculate": calculate,
}


def get_llm() -> BaseChatModel:
    ollama_model = os.environ.get("OLLAMA_MODEL")

    if ollama_model:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=ollama_model,
            temperature=0.7,
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        )
    else:
        from langchain_openai import ChatOpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Either OLLAMA_MODEL or OPENAI_API_KEY environment variable must be set")

        return ChatOpenAI(
            model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
            api_key=api_key,
            temperature=0.7
        )


def parse_tool_call(text: str) -> tuple[Optional[str], Optional[dict]]:
    """从文本中解析工具调用"""
    patterns = [
        r'(\w+)\s*\(\s*([^)]+)\s*\)',
        r'"(\w+)"\s*:\s*\{[^}]*"arguments"[^}]*\{[^}]*"([^"]+)"[^}]*\}[^}]*\}',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            tool_name = match.group(1) if match.lastindex >= 1 else None
            args_str = match.group(2) if match.lastindex >= 2 else "{}"

            if tool_name and tool_name in tools_map:
                args = {}

                if tool_name == "get_weather":
                    loc_match = re.search(r'["\']?location["\']?\s*:\s*["\']([^"\']+)["\']', args_str)
                    if loc_match:
                        args = {"location": loc_match.group(1)}
                    else:
                        simple_match = re.search(r'["\']([^"\']+)["\']', args_str)
                        if simple_match:
                            args = {"location": simple_match.group(1)}

                elif tool_name == "get_current_time":
                    tz_match = re.search(r'["\']?timezone["\']?\s*:\s*["\']([^"\']+)["\']', args_str)
                    if tz_match:
                        args = {"timezone": tz_match.group(1)}

                elif tool_name == "calculate":
                    expr_match = re.search(r'["\']?expression["\']?\s*:\s*["\']([^"\']+)["\']', args_str)
                    if expr_match:
                        args = {"expression": expr_match.group(1)}
                    else:
                        simple_match = re.search(r'["\']([^"\']+)["\']', args_str)
                        if simple_match:
                            args = {"expression": simple_match.group(1)}

                if args:
                    return tool_name, args

    return None, None


async def run_agent(prompt: str) -> str:
    try:
        llm = get_llm()

        system_prompt = """You are a helpful assistant. When the user asks about weather, time, or calculations, you MUST call the appropriate tool.

Available tools:
- get_weather(location): Get weather for a city
- get_current_time(timezone): Get current time (default: Asia/Shanghai)
- calculate(expression): Calculate math expression

Instructions:
1. If user asks about weather, call get_weather with the location
2. If user asks about time, call get_current_time with timezone
3. If user asks about math, call calculate with the expression
4. After getting tool results, provide the final answer

IMPORTANT: Always actually call the tools, don't just describe what you would do."""

        full_prompt = f"{system_prompt}\n\nUser: {prompt}"

        response = await llm.ainvoke(full_prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)

        tool_name, args = parse_tool_call(response_text)

        if tool_name and tool_name in tools_map:
            tool = tools_map[tool_name]
            try:
                tool_result = tool.invoke(args) if args else tool.invoke({})
                return f"{tool_result}"
            except Exception as e:
                return f"Tool execution error: {str(e)}"

        return response_text

    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}. Please try again later."
