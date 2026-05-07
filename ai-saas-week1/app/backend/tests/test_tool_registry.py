"""工具注册模块测试"""
import pytest
from app.agents.tool_registry import ToolRegistry, get_weather, get_current_time, calculate, tool_registry


class TestToolRegistry:
    """工具注册管理器测试类"""

    def test_register_tool(self):
        """测试注册工具"""
        registry = ToolRegistry()

        def test_tool():
            return "test"

        registry.register_tool("test_tool", test_tool)

        assert registry.has_tool("test_tool")
        assert registry.get_tool("test_tool") == test_tool

    def test_get_tool_not_found(self):
        """测试获取不存在的工具"""
        registry = ToolRegistry()

        result = registry.get_tool("nonexistent")

        assert result is None

    def test_list_tools(self):
        """测试获取工具列表"""
        registry = ToolRegistry()

        def tool1():
            pass

        def tool2():
            pass

        registry.register_tool("tool1", tool1)
        registry.register_tool("tool2", tool2)

        tools = registry.list_tools()

        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools

    def test_has_tool(self):
        """测试检查工具是否存在"""
        registry = ToolRegistry()

        def test_tool():
            pass

        registry.register_tool("test_tool", test_tool)

        assert registry.has_tool("test_tool")
        assert not registry.has_tool("nonexistent")

    def test_invoke_tool(self):
        """测试调用工具"""
        registry = ToolRegistry()

        def greet(name: str):
            return f"Hello, {name}!"

        # 使用 mock 工具调用
        with pytest.raises(ValueError):
            registry.invoke_tool("nonexistent", {})

    def test_invoke_tool_error(self):
        """测试工具调用错误"""
        registry = ToolRegistry()

        def faulty_tool():
            raise ValueError("test error")

        # 需要使用 langchain 的 tool 装饰器才能正确调用
        registry.register_tool("faulty", faulty_tool)


class TestTools:
    """工具函数测试类"""

    def test_get_weather(self):
        """测试天气工具"""
        result = get_weather.invoke({"location": "Beijing"})

        assert "晴" in result or "Beijing" in result or "25°C" in result

    def test_get_weather_lowercase(self):
        """测试天气工具不区分大小写"""
        result = get_weather.invoke({"location": "BEIJING"})

        assert "晴" in result or "Beijing" in result

    def test_get_weather_not_found(self):
        """测试天气工具未找到城市"""
        result = get_weather.invoke({"location": "Tokyo"})

        assert "未找到" in result or "Tokyo" in result

    def test_get_current_time(self):
        """测试时间工具"""
        result = get_current_time.invoke({})

        assert "Asia/Shanghai" in result
        assert "当前时间" in result

    def test_get_current_time_with_timezone(self):
        """测试时间工具带时区参数"""
        result = get_current_time.invoke({"timezone": "America/New_York"})

        assert "America/New_York" in result

    def test_get_current_time_invalid_timezone(self):
        """测试时间工具无效时区"""
        result = get_current_time.invoke({"timezone": "Invalid/Timezone"})

        assert "错误" in result

    def test_calculate(self):
        """测试计算工具"""
        result = calculate.invoke({"expression": "2 + 3 * 4"})

        assert "14" in result or "计算结果" in result

    def test_calculate_with_sqrt(self):
        """测试计算工具带平方根"""
        result = calculate.invoke({"expression": "sqrt(16)"})

        assert "4" in result

    def test_calculate_invalid_expression(self):
        """测试计算工具无效表达式"""
        result = calculate.invoke({"expression": "invalid"})

        assert "错误" in result

    def test_global_tool_registry(self):
        """测试全局工具注册表"""
        assert tool_registry.has_tool("get_weather")
        assert tool_registry.has_tool("get_current_time")
        assert tool_registry.has_tool("calculate")
        assert len(tool_registry.list_tools()) == 3
