import json
import logging
import re
from datetime import datetime
from typing import (
    TypedDict,
    Annotated,
    Sequence,
    Literal,
    Optional,
    Dict,
    Any,
    AsyncIterator,
)
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
import operator

from .llm_client import get_llm
from .rag_tool import rag_search_tool

logger = logging.getLogger(__name__)

_global_checkpointer = None
_execution_traces: Dict[str, list] = {}


def _get_checkpointer():
    global _global_checkpointer
    if _global_checkpointer is None:
        _global_checkpointer = MemorySaver()
    return _global_checkpointer


def _record_trace(thread_id: str, node: str, state: dict):
    if thread_id not in _execution_traces:
        _execution_traces[thread_id] = []
    trace_entry = {
        "node": node,
        "state": _sanitize_state_for_trace(state),
        "timestamp": datetime.now().isoformat(),
    }
    _execution_traces[thread_id].append(trace_entry)
    max_traces = 1000
    if len(_execution_traces[thread_id]) > max_traces:
        _execution_traces[thread_id] = _execution_traces[thread_id][-max_traces:]
    logger.info(
        f"[RAGTrace] thread={thread_id}, node={node}, trace_count={len(_execution_traces[thread_id])}"
    )


def _sanitize_state_for_trace(state: dict) -> dict:
    sanitized = {}
    for key, value in state.items():
        if key == "messages" and isinstance(value, Sequence):
            sanitized[key] = [
                (
                    {
                        "role": "human" if isinstance(m, HumanMessage) else "ai",
                        "content": m.content,
                    }
                    if hasattr(m, "content")
                    else str(m)
                )
                for m in value
            ]
        elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def get_execution_trace(thread_id: str) -> list:
    return _execution_traces.get(thread_id, [])


def clear_execution_trace(thread_id: str):
    if thread_id in _execution_traces:
        del _execution_traces[thread_id]


KNOWLEDGE_KEYWORDS = [
    "什么是",
    "如何",
    "怎么",
    "为什么",
    "解释",
    "定义",
    "介绍",
    "文档",
    "手册",
    "指南",
    "教程",
    "说明",
    "规范",
    "协议",
    "原理",
    "概念",
    "流程",
    "步骤",
    "方法",
    "方案",
    "架构",
    "配置",
    "部署",
    "安装",
    "使用",
    "调用",
    "参数",
    "接口",
    "api",
    "sdk",
    "版本",
    "更新",
    "变更",
    "区别",
    "对比",
    "what is",
    "how to",
    "why",
    "explain",
    "define",
    "describe",
    "document",
    "guide",
    "tutorial",
    "manual",
    "specification",
    "architecture",
    "configuration",
    "deployment",
    "installation",
]

CHITCHAT_KEYWORDS = [
    "你好",
    "嗨",
    "hello",
    "hi",
    "hey",
    "谢谢",
    "再见",
    "拜拜",
    "天气",
    "时间",
    "今天",
    "明天",
    "怎么样",
    "好吗",
    "你是谁",
    "你叫什么",
    "你的名字",
]

CALCULATION_KEYWORDS = [
    "计算",
    "calc",
    "+",
    "-",
    "*",
    "/",
    "=",
    "等于",
    "多少",
    "求和",
    "平均",
    "总和",
]


class RAGAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_input: str
    needs_rag: bool
    needs_direct_answer: bool
    rag_query: str
    rag_filters: Optional[Dict[str, Any]]
    rag_top_k: int
    rag_result: str
    rag_confidence: str
    rag_references: list[str]
    final_response: str
    error_message: str


def analyze_node(state: RAGAgentState) -> RAGAgentState:
    messages = state.get("messages", [])
    user_input = state.get("user_input", "")

    if not messages and not user_input:
        return {
            "needs_rag": False,
            "needs_direct_answer": True,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_confidence": "high",
        }

    if messages:
        last_message = messages[-1]
        user_input = (
            last_message.content if hasattr(last_message, "content") else user_input
        )

    user_lower = user_input.lower().strip()

    logger.info(f"[RAGAnalyzeNode] user_input='{user_input}'")

    is_chitchat = any(kw in user_lower for kw in CHITCHAT_KEYWORDS)
    is_calculation = any(kw in user_lower for kw in CALCULATION_KEYWORDS)
    is_knowledge = any(kw in user_lower for kw in KNOWLEDGE_KEYWORDS)

    if is_chitchat or is_calculation:
        logger.info(
            f"[RAGAnalyzeNode] 闲聊/计算问题 -> 直接回答, "
            f"is_chitchat={is_chitchat}, is_calculation={is_calculation}"
        )
        return {
            "user_input": user_input,
            "needs_rag": False,
            "needs_direct_answer": True,
            "rag_query": "",
            "rag_filters": None,
            "rag_top_k": 5,
            "rag_confidence": "high",
        }

    if is_knowledge:
        logger.info("[RAGAnalyzeNode] 知识型问题 -> 调用 rag_search")
        return {
            "user_input": user_input,
            "needs_rag": True,
            "needs_direct_answer": False,
            "rag_query": user_input,
            "rag_filters": None,
            "rag_top_k": 5,
        }

    if len(user_input) > 20 or "?" in user_input or "？" in user_input:
        logger.info("[RAGAnalyzeNode] 长文本/问句 -> 调用 rag_search")
        return {
            "user_input": user_input,
            "needs_rag": True,
            "needs_direct_answer": False,
            "rag_query": user_input,
            "rag_filters": None,
            "rag_top_k": 5,
        }

    logger.info("[RAGAnalyzeNode] 短文本 -> 直接回答")
    return {
        "user_input": user_input,
        "needs_rag": False,
        "needs_direct_answer": True,
        "rag_query": "",
        "rag_filters": None,
        "rag_top_k": 5,
        "rag_confidence": "high",
    }


async def rag_tool_node(state: RAGAgentState) -> RAGAgentState:
    rag_query = state.get("rag_query", "")
    rag_filters = state.get("rag_filters")
    rag_top_k = state.get("rag_top_k", 5)

    logger.info(
        f"[RAGToolNode] query='{rag_query}', filters={rag_filters}, top_k={rag_top_k}"
    )

    try:
        raw_result = await rag_search_tool.ainvoke(
            {
                "query": rag_query,
                "filters": rag_filters,
                "top_k": rag_top_k,
            }
        )

        result_data = json.loads(raw_result)
        confidence = result_data.get("confidence", "low")
        references = result_data.get("references", [])

        if not references:
            confidence = "low"
            logger.warning(
                f"[RAGToolNode] 未找到引用，标记置信度为 low - query='{rag_query}'"
            )

        logger.info(
            f"[RAGToolNode] 搜索完成 - found={result_data.get('total_found', 0)}, "
            f"confidence={confidence}, references={len(references)}"
        )

        return {
            "rag_result": raw_result,
            "rag_confidence": confidence,
            "rag_references": references,
            "error_message": "",
            "messages": [
                AIMessage(content=f"RAG 搜索完成，找到 {len(references)} 条引用")
            ],
        }

    except json.JSONDecodeError as e:
        logger.error(f"[RAGToolNode] JSON 解析失败: {str(e)}")
        return {
            "rag_result": "",
            "rag_confidence": "low",
            "rag_references": [],
            "error_message": "搜索结果解析失败，请稍后重试",
            "messages": [AIMessage(content="搜索结果解析失败，请稍后重试")],
        }

    except Exception as e:
        logger.error(f"[RAGToolNode] 工具调用失败: {str(e)}")
        return {
            "rag_result": "",
            "rag_confidence": "low",
            "rag_references": [],
            "error_message": "知识库搜索暂时不可用，请稍后重试",
            "messages": [AIMessage(content="知识库搜索暂时不可用，请稍后重试")],
        }


async def response_node(state: RAGAgentState) -> RAGAgentState:
    user_input = state.get("user_input", "")
    needs_rag = state.get("needs_rag", False)
    needs_direct_answer = state.get("needs_direct_answer", False)
    rag_result = state.get("rag_result", "")
    rag_confidence = state.get("rag_confidence", "low")
    rag_references = state.get("rag_references", [])
    error_message = state.get("error_message", "")

    logger.info(
        f"[RAGResponseNode] needs_rag={needs_rag}, "
        f"needs_direct_answer={needs_direct_answer}, "
        f"confidence={rag_confidence}, references={len(rag_references)}"
    )

    if error_message:
        final_response = json.dumps(
            {
                "answer": error_message,
                "confidence": "low",
                "references": [],
                "source": "error",
            },
            ensure_ascii=False,
        )
        return {
            "final_response": final_response,
            "messages": [AIMessage(content=final_response)],
            "rag_confidence": "low",
            "rag_references": [],
        }

    if needs_rag and rag_result:
        try:
            result_data = json.loads(rag_result)
            results = result_data.get("results", [])
            references = result_data.get("references", [])
            confidence = result_data.get("confidence", "low")

            if not references:
                confidence = "low"

            formatted_answer = await _format_rag_response(
                user_input, results, references, confidence
            )

            final_response = json.dumps(
                {
                    "answer": formatted_answer,
                    "confidence": confidence,
                    "references": references,
                    "results": [
                        {
                            "doc_id": r.get("doc_id", ""),
                            "content": r.get("content", "")[:200],
                            "score": r.get("score", 0),
                            "source": r.get("source", ""),
                        }
                        for r in results
                    ],
                    "source": "rag_search",
                },
                ensure_ascii=False,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[RAGResponseNode] 结果格式化失败: {str(e)}")
            final_response = json.dumps(
                {
                    "answer": "抱歉，搜索结果处理时出现问题，请重新提问。",
                    "confidence": "low",
                    "references": [],
                    "source": "error",
                },
                ensure_ascii=False,
            )

    elif needs_direct_answer:
        direct_answer = await _generate_direct_response(user_input)
        final_response = json.dumps(
            {
                "answer": direct_answer,
                "confidence": "high",
                "references": [],
                "source": "direct",
            },
            ensure_ascii=False,
        )
        # 直接回答时，rag_confidence 应该是 high
        rag_confidence = "high"

    else:
        final_response = json.dumps(
            {
                "answer": "我无法理解您的问题，请提供更多信息。",
                "confidence": "low",
                "references": [],
                "source": "fallback",
            },
            ensure_ascii=False,
        )

    logger.info(f"[RAGResponseNode] final_response length={len(final_response)}")

    return {
        "final_response": final_response,
        "messages": [AIMessage(content=final_response)],
        "rag_confidence": rag_confidence,
        "rag_references": rag_references,
    }


async def _format_rag_response(
    query: str,
    results: list,
    references: list,
    confidence: str,
) -> str:
    if not results:
        return "抱歉，未在知识库中找到相关信息。请尝试换个问法或提供更多细节。"

    context_parts = []
    for i, r in enumerate(results):
        doc_id = r.get("doc_id", f"ref-{i}")
        content = r.get("content", "")
        source = r.get("source", "unknown")
        context_parts.append(f"[{doc_id}](来源: {source})\n{content}")

    context = "\n\n---\n\n".join(context_parts)

    system_prompt = f"""你是一个基于知识库的问答助手。请根据以下检索到的文档内容回答用户问题。

要求：
1. 回答必须基于提供的文档内容，不要编造信息
2. 在回答中引用相关文档块，使用 [{doc_id}](source_url) 格式
3. 如果文档内容不足以回答问题，请明确说明
4. 置信度: {confidence}

检索到的文档内容：
{context}"""

    try:
        llm = get_llm()
        response = await llm.ainvoke(
            f"{system_prompt}\n\n用户问题：{query}\n\n请基于上述文档内容回答："
        )
        answer = response.content if hasattr(response, "content") else str(response)

        if not _has_reference_format(answer, references):
            ref_list = ", ".join([f"[{ref}](source_url)" for ref in references[:3]])
            answer = f"{answer}\n\n---\n引用来源: {ref_list}"

        return answer

    except Exception as e:
        logger.error(f"[RAGResponseNode] LLM 调用失败: {str(e)}")

        parts = []
        for i, r in enumerate(results[:3]):
            doc_id = r.get("doc_id", f"ref-{i}")
            content = r.get("content", "")[:300]
            source = r.get("source", "unknown")
            parts.append(f"[{doc_id}](来源: {source})\n{content}")

        ref_list = ", ".join([f"[{ref}](source_url)" for ref in references[:3]])
        return (
            "根据知识库检索结果：\n\n"
            + "\n\n---\n\n".join(parts)
            + f"\n\n---\n引用来源: {ref_list}"
        )


def _has_reference_format(answer: str, references: list) -> bool:
    if not references:
        return False
    for ref in references:
        if f"[{ref}]" in answer:
            return True
    return bool(re.search(r"\[.*?\]\(.*?\)", answer))


async def _generate_direct_response(user_input: str) -> str:
    user_lower = user_input.lower().strip()

    chitchat_responses = {
        "你好": "你好！有什么可以帮助你的吗？",
        "嗨": "嗨！有什么问题尽管问我。",
        "hello": "Hello! How can I help you today?",
        "hi": "Hi there! What can I do for you?",
        "hey": "Hey! Feel free to ask me anything.",
        "谢谢": "不客气！如果还有其他问题，随时问我。",
        "再见": "再见！祝你有美好的一天。",
        "拜拜": "拜拜！下次见。",
        "你是谁": "我是基于 LangGraph 的 RAG 智能助手，可以帮你搜索知识库中的信息。",
        "你叫什么": "我是 RAG 智能助手，专门为知识检索和问答设计。",
        "你的名字": "我叫 RAG Assistant，很高兴为你服务！",
    }

    for key, response in chitchat_responses.items():
        if key in user_lower:
            return response

    if any(kw in user_lower for kw in ["计算", "calc", "+", "-", "*", "/"]):
        try:
            expr = re.sub(r"[^0-9+\-*/().\s]", "", user_input)
            if expr.strip():
                result = eval(expr, {"__builtins__": {}})
                return f"计算结果：{expr.strip()} = {result}"
        except Exception:
            pass
        return "请输入有效的数学表达式，例如：2 + 3 * 4"

    try:
        llm = get_llm()
        response = await llm.ainvoke(f"请用简洁友好的方式回答用户的问题：{user_input}")
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error(f"[RAGResponseNode] 直接回答 LLM 调用失败: {str(e)}")
        return "我收到了你的消息，但暂时无法处理。请尝试重新提问。"


def route_after_analyze(state: RAGAgentState) -> Literal["rag_tool", "response"]:
    needs_rag = state.get("needs_rag", False)
    next_node = "rag_tool" if needs_rag else "response"
    logger.info(f"[RouteAfterAnalyze] needs_rag={needs_rag} -> next_node='{next_node}'")
    return next_node


def build_rag_agent_graph() -> StateGraph:
    graph = StateGraph(RAGAgentState)

    graph.add_node("analyze", analyze_node)
    graph.add_node("rag_tool", rag_tool_node)
    graph.add_node("response", response_node)

    graph.add_edge(START, "analyze")

    graph.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {
            "rag_tool": "rag_tool",
            "response": "response",
        },
    )

    graph.add_edge("rag_tool", "response")
    graph.add_edge("response", END)

    checkpointer = _get_checkpointer()
    compiled_graph = graph.compile(checkpointer=checkpointer)

    logger.info("[RAGAgent] Graph compiled successfully")
    return compiled_graph


_rag_agent_graph = None


def get_rag_agent_graph():
    global _rag_agent_graph
    if _rag_agent_graph is None:
        _rag_agent_graph = build_rag_agent_graph()
    return _rag_agent_graph


async def run_rag_agent(user_input: str, thread_id: str = "default") -> dict:
    graph = get_rag_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "user_input": user_input,
    }

    raw_result = await graph.ainvoke(initial_state, config)

    if isinstance(raw_result, dict):
        for node_name, node_state in raw_result.items():
            if node_name != "__end__" and isinstance(node_state, dict):
                _record_trace(thread_id, node_name, node_state)

    merged_state = {}
    if isinstance(raw_result, dict):
        if "final_response" in raw_result:
            merged_state = raw_result
        else:
            for key, value in raw_result.items():
                if isinstance(value, dict):
                    merged_state.update(value)
            merged_state.update(
                {k: v for k, v in raw_result.items() if not isinstance(v, dict)}
            )

    return merged_state


async def run_rag_agent_stream(
    user_input: str,
    thread_id: str = "default",
) -> AsyncIterator[Dict[str, Any]]:
    graph = get_rag_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "user_input": user_input,
    }

    async for event in graph.astream(initial_state, config, stream_mode="updates"):
        node_name = list(event.keys())[0] if event else ""
        node_state = event.get(node_name, {}) if node_name else {}

        if node_name and node_name != "__end__":
            _record_trace(thread_id, node_name, node_state)

        chunk = {
            "node": node_name,
            "state": _sanitize_state_for_trace(node_state),
            "timestamp": datetime.now().isoformat(),
        }

        if node_name == "response":
            final_response = node_state.get("final_response", "")
            chunk["final_response"] = final_response

        yield chunk


async def get_rag_session_info(thread_id: str) -> dict:
    checkpointer = _get_checkpointer()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await checkpointer.aget(config)
        if state:
            return {
                "thread_id": thread_id,
                "has_state": True,
                "messages_count": len(state.get("messages", [])),
            }
    except Exception:
        pass

    return {
        "thread_id": thread_id,
        "has_state": False,
        "messages_count": 0,
    }
