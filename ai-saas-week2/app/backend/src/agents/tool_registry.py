"""工具注册模块 - 管理所有可用工具"""
from langchain.tools import tool
from typing import Dict, Callable, Any, Optional
from datetime import datetime
import math
import pytz


class ToolRegistry:
    """工具注册管理器"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, tool_func: Callable) -> None:
        """
        注册工具

        Args:
            name: 工具名称
            tool_func: 工具函数
        """
        self._tools[name] = tool_func

    def get_tool(self, name: str) -> Optional[Callable]:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            Callable: 工具函数，如果不存在返回 None
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """
        获取所有已注册工具的名称列表

        Returns:
            list[str]: 工具名称列表
        """
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """
        检查工具是否已注册

        Args:
            name: 工具名称

        Returns:
            bool: 如果工具已注册返回 True，否则返回 False
        """
        return name in self._tools

    def invoke_tool(self, name: str, args: Dict[str, Any]) -> str:
        """
        调用工具

        Args:
            name: 工具名称
            args: 工具参数

        Returns:
            str: 工具执行结果

        Raises:
            ValueError: 当工具不存在时
        """
        tool_func = self.get_tool(name)
        if not tool_func:
            raise ValueError(f"工具 {name} 未注册")

        try:
            return tool_func.invoke(args)
        except Exception as e:
            return f"工具执行错误: {str(e)}"


# 全局工具注册表
tool_registry = ToolRegistry()


@tool
def get_weather(location: str) -> str:
    """
    获取指定位置的当前天气

    Args:
        location: 城市名称或位置，例如 "Beijing", "Shanghai"

    Returns:
        str: 包含温度和天气状况的信息
    """
    weather_data = {
        "beijing": "晴，25°C，湿度 45%",
        "shanghai": "多云，28°C，湿度 60%",
        "guangzhou": "小雨，32°C，湿度 85%",
        "shenzhen": "多云转晴，30°C，湿度 70%",
    }
    location_lower = location.lower()
    return weather_data.get(location_lower, f"未找到 {location} 的天气数据")


@tool
def get_current_time(timezone: Optional[str] = "Asia/Shanghai") -> str:
    """
    获取指定时区的当前时间

    Args:
        timezone: 时区字符串（默认：Asia/Shanghai）
                  常用值: "Asia/Shanghai", "America/New_York", "Europe/London"

    Returns:
        str: 格式化的 ISO 8601 时间字符串
    """
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz).isoformat()
        return f"{timezone} 当前时间: {current_time}"
    except Exception as e:
        return f"获取时间错误: {str(e)}"


@tool
def calculate(expression: str) -> str:
    """
    计算数学表达式

    Args:
        expression: 要计算的数学表达式，例如 "2 + 3 * 4", "sqrt(16)"

    Returns:
        str: 计算结果
    """
    try:
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith('_')}
        result = eval(expression, {"__builtins__": None}, allowed_names)
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


# 注册所有工具
tool_registry.register_tool("get_weather", get_weather)
tool_registry.register_tool("get_current_time", get_current_time)
tool_registry.register_tool("calculate", calculate)
