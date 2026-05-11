import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import HumanMessage

from src.agents.langgraph_rag_agent import (
    analyze_node,
    route_after_analyze,
    build_rag_agent_graph,
    RAGAgentState,
    KNOWLEDGE_KEYWORDS,
    CHITCHAT_KEYWORDS,
    CALCULATION_KEYWORDS,
)


class TestRAGAnalyzeNode:
    def test_knowledge_question_triggers_rag(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="什么是 RAG 技术？")],
            "user_input": "什么是 RAG 技术？",
            "needs_rag": False,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = analyze_node(state)

        assert result["needs_rag"] is True
        assert result["needs_direct_answer"] is False
        assert result["rag_query"] == "什么是 RAG 技术？"

    def test_chitchat_triggers_direct_answer(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="你好")],
            "user_input": "你好",
            "needs_rag": False,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = analyze_node(state)

        assert result["needs_rag"] is False
        assert result["needs_direct_answer"] is True

    def test_calculation_triggers_direct_answer(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="计算 2+3")],
            "user_input": "计算 2+3",
            "needs_rag": False,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = analyze_node(state)

        assert result["needs_rag"] is False
        assert result["needs_direct_answer"] is True

    def test_how_to_question_triggers_rag(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="如何配置 LangGraph？")],
            "user_input": "如何配置 LangGraph？",
            "needs_rag": False,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = analyze_node(state)

        assert result["needs_rag"] is True
        assert result["needs_direct_answer"] is False

    def test_long_question_triggers_rag(self):
        long_question = "请详细解释一下 LangGraph 中的状态管理机制以及如何与 RAG 管道集成"
        state: RAGAgentState = {
            "messages": [HumanMessage(content=long_question)],
            "user_input": long_question,
            "needs_rag": False,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = analyze_node(state)

        assert result["needs_rag"] is True

    def test_short_text_direct_answer(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="ok")],
            "user_input": "ok",
            "needs_rag": False,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = analyze_node(state)

        assert result["needs_rag"] is False
        assert result["needs_direct_answer"] is True

    def test_empty_state_defaults_to_direct(self):
        state: RAGAgentState = {
            "messages": [],
            "user_input": "",
            "needs_rag": False,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = analyze_node(state)

        assert result["needs_rag"] is False
        assert result["needs_direct_answer"] is True


class TestRAGRouting:
    def test_route_to_rag_tool(self):
        state: RAGAgentState = {
            "messages": [],
            "user_input": "",
            "needs_rag": True,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = route_after_analyze(state)
        assert result == "rag_tool"

    def test_route_to_response(self):
        state: RAGAgentState = {
            "messages": [],
            "user_input": "",
            "needs_rag": False,
            "needs_direct_answer": True,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        result = route_after_analyze(state)
        assert result == "response"


class TestRAGToolNode:
    @pytest.mark.asyncio
    async def test_rag_tool_error_handling(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="测试")],
            "user_input": "测试",
            "needs_rag": True,
            "needs_direct_answer": False,
            "rag_query": "测试查询",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        from src.agents.langgraph_rag_agent import rag_tool_node

        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(
            side_effect=Exception("模拟的工具调用失败")
        )

        with patch(
            "src.agents.langgraph_rag_agent.rag_search_tool", mock_tool
        ):
            result = await rag_tool_node(state)

            assert result["rag_confidence"] == "low"
            assert result["rag_references"] == []
            assert "暂时不可用" in result["error_message"]

    @pytest.mark.asyncio
    async def test_rag_tool_json_decode_error(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="测试")],
            "user_input": "测试",
            "needs_rag": True,
            "needs_direct_answer": False,
            "rag_query": "测试查询",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        from src.agents.langgraph_rag_agent import rag_tool_node

        mock_tool = MagicMock()
        mock_tool.ainvoke = AsyncMock(
            return_value="invalid json {{{"
        )

        with patch(
            "src.agents.langgraph_rag_agent.rag_search_tool", mock_tool
        ):
            result = await rag_tool_node(state)

            assert result["rag_confidence"] == "low"
            assert "解析失败" in result["error_message"]


class TestRAGResponseNode:
    @pytest.mark.asyncio
    async def test_direct_answer_for_chitchat(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="你好")],
            "user_input": "你好",
            "needs_rag": False,
            "needs_direct_answer": True,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        from src.agents.langgraph_rag_agent import response_node

        result = await response_node(state)

        final_response = json.loads(result["final_response"])
        assert final_response["source"] == "direct"
        assert final_response["confidence"] == "high"
        assert "answer" in final_response

    @pytest.mark.asyncio
    async def test_error_message_response(self):
        state: RAGAgentState = {
            "messages": [HumanMessage(content="测试")],
            "user_input": "测试",
            "needs_rag": True,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": "",
            "rag_confidence": "low",
            "rag_references": [],
            "final_response": "",
            "error_message": "知识库搜索暂时不可用，请稍后重试",
        }

        from src.agents.langgraph_rag_agent import response_node

        result = await response_node(state)

        final_response = json.loads(result["final_response"])
        assert final_response["source"] == "error"
        assert final_response["confidence"] == "low"

    @pytest.mark.asyncio
    async def test_rag_result_with_references(self):
        rag_result = json.dumps({
            "query": "测试",
            "results": [
                {
                    "doc_id": "abc123",
                    "content": "这是测试内容",
                    "score": 0.95,
                    "source": "test.pdf",
                    "metadata": {"page": 1},
                }
            ],
            "total_found": 1,
            "confidence": "high",
            "references": ["abc123"],
        })

        state: RAGAgentState = {
            "messages": [HumanMessage(content="测试")],
            "user_input": "测试",
            "needs_rag": True,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": rag_result,
            "rag_confidence": "high",
            "rag_references": ["abc123"],
            "final_response": "",
            "error_message": "",
        }

        with patch(
            "src.agents.langgraph_rag_agent.get_llm",
            return_value=MagicMock(
                ainvoke=AsyncMock(
                    return_value=MagicMock(
                        content="根据文档 [abc123](source_url)，这是测试内容。"
                    )
                )
            ),
        ):
            from src.agents.langgraph_rag_agent import response_node

            result = await response_node(state)

            final_response = json.loads(result["final_response"])
            assert final_response["source"] == "rag_search"
            assert "abc123" in final_response["references"]

    @pytest.mark.asyncio
    async def test_rag_result_no_references_marks_low_confidence(self):
        rag_result = json.dumps({
            "query": "测试",
            "results": [],
            "total_found": 0,
            "confidence": "low",
            "references": [],
        })

        state: RAGAgentState = {
            "messages": [HumanMessage(content="测试")],
            "user_input": "测试",
            "needs_rag": True,
            "needs_direct_answer": False,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_result": rag_result,
            "rag_confidence": "low",
            "rag_references": [],
            "final_response": "",
            "error_message": "",
        }

        from src.agents.langgraph_rag_agent import response_node

        result = await response_node(state)

        final_response = json.loads(result["final_response"])
        assert final_response["confidence"] == "low"
        assert final_response["references"] == []


class TestRAGGraphBuilding:
    def test_build_graph_returns_compiled_graph(self):
        graph = build_rag_agent_graph()

        assert graph is not None
        nodes = graph.get_graph().nodes
        node_names = {node for node in nodes.keys()}

        assert "analyze" in node_names
        assert "rag_tool" in node_names
        assert "response" in node_names

    def test_get_rag_agent_graph_singleton(self):
        from src.agents.langgraph_rag_agent import get_rag_agent_graph

        graph1 = get_rag_agent_graph()
        graph2 = get_rag_agent_graph()

        assert graph1 is graph2


class TestRAGKeywords:
    def test_knowledge_keywords_not_empty(self):
        assert len(KNOWLEDGE_KEYWORDS) > 0

    def test_chitchat_keywords_not_empty(self):
        assert len(CHITCHAT_KEYWORDS) > 0

    def test_calculation_keywords_not_empty(self):
        assert len(CALCULATION_KEYWORDS) > 0

    def test_keywords_no_overlap(self):
        knowledge_set = set(k.lower() for k in KNOWLEDGE_KEYWORDS)
        chitchat_set = set(k.lower() for k in CHITCHAT_KEYWORDS)
        calc_set = set(k.lower() for k in CALCULATION_KEYWORDS)

        assert len(knowledge_set & chitchat_set) == 0
        assert len(knowledge_set & calc_set) == 0


class TestRAGAgentStreaming:
    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        from src.agents.langgraph_rag_agent import run_rag_agent_stream

        chunks = []
        async for chunk in run_rag_agent_stream("什么是 RAG？", "test-stream"):
            chunks.append(chunk)

        assert len(chunks) > 0
        node_names = [c.get("node") for c in chunks if c.get("node")]
        assert "analyze" in node_names
        assert "response" in node_names

    @pytest.mark.asyncio
    async def test_stream_chitchat(self):
        from src.agents.langgraph_rag_agent import run_rag_agent_stream

        chunks = []
        async for chunk in run_rag_agent_stream("你好", "test-chitchat"):
            chunks.append(chunk)

        assert len(chunks) > 0
        response_chunks = [
            c for c in chunks if c.get("node") == "response"
        ]
        assert len(response_chunks) > 0


class TestRAGSessionInfo:
    @pytest.mark.asyncio
    async def test_get_session_info_new_thread(self):
        from src.agents.langgraph_rag_agent import get_rag_session_info

        info = await get_rag_session_info("non-existent-thread")

        assert info["thread_id"] == "non-existent-thread"
        assert info["has_state"] is False
        assert info["messages_count"] == 0


class TestRAGTrace:
    def test_get_execution_trace_empty(self):
        from src.agents.langgraph_rag_agent import get_execution_trace

        trace = get_execution_trace("non-existent")
        assert trace == []

    def test_clear_execution_trace(self):
        from src.agents.langgraph_rag_agent import (
            clear_execution_trace,
            get_execution_trace,
        )

        clear_execution_trace("test-clear")
        trace = get_execution_trace("test-clear")
        assert trace == []
