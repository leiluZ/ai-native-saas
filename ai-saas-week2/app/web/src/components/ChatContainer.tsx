import React, { useEffect, useRef, useState } from "react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { useChatStore } from "../store/chatStore";
import { Moon, Sun, Trash2, RefreshCw, History, X } from "lucide-react";

export const ChatContainer: React.FC = () => {
  const {
    messages,
    theme,
    toggleTheme,
    clearMessages,
    error,
    setError,
    agentType,
    setAgentType,
    currentThreadId,
  } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [historyData, setHistoryData] = useState<any>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const fetchSessionHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await fetch(
        `${
          import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"
        }/chat/sessions/${currentThreadId}/history`,
      );
      if (response.ok) {
        const data = await response.json();
        setHistoryData(data.data);
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (showHistory) {
      setHistoryData(null);
      fetchSessionHistory();
    }
  }, [showHistory, currentThreadId]);

  const refreshHistory = () => {
    fetchSessionHistory();
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      <header className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">AI</span>
            </div>
            <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
              AI 聊天助手
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
              <button
                onClick={() => setAgentType("agent")}
                className={`px-3 py-1 rounded-md text-sm transition-colors ${
                  agentType === "agent"
                    ? "bg-blue-500 text-white"
                    : "text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                Week1 Agent
              </button>
              <button
                onClick={() => setAgentType("langgraph")}
                className={`px-3 py-1 rounded-md text-sm transition-colors ${
                  agentType === "langgraph"
                    ? "bg-blue-500 text-white"
                    : "text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                Week2 LangGraph Agent
              </button>
            </div>
            <button
              onClick={() => setShowHistory(true)}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
              title="查看会话历史"
            >
              <History className="w-5 h-5" />
            </button>
            <button
              onClick={clearMessages}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
              title="清空聊天"
            >
              <Trash2 className="w-5 h-5" />
            </button>
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
              title={theme === "light" ? "切换暗色模式" : "切换亮色模式"}
            >
              {theme === "light" ? (
                <Moon className="w-5 h-5" />
              ) : (
                <Sun className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800 px-4 py-3">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <span className="text-red-600 dark:text-red-400 text-sm">
              {error}
            </span>
            <button
              onClick={() => setError(null)}
              className="flex items-center gap-1 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 text-sm"
            >
              <RefreshCw className="w-4 h-4" />
              重试
            </button>
          </div>
        </div>
      )}

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-20">
              <div className="w-20 h-20 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mb-6">
                <span className="text-4xl">🤖</span>
              </div>
              <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-100 mb-2">
                欢迎使用 AI 聊天助手
              </h2>
              <p className="text-gray-500 dark:text-gray-400 max-w-md">
                发送消息开始对话，我会尽力为您提供帮助。
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      <ChatInput />

      {showHistory && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
                会话历史
              </h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={refreshHistory}
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
                  title="刷新"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setShowHistory(false)}
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              {historyLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                </div>
              ) : historyData ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
                    <span>Token 使用: {historyData.total_tokens}</span>
                    <span>
                      需要摘要: {historyData.needs_summarization ? "是" : "否"}
                    </span>
                    <span>
                      待审批: {historyData.pending_approval ? "是" : "否"}
                    </span>
                    <span>置信度: {historyData.confidence}</span>
                  </div>
                  <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                    <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      对话历史 ({historyData.conversation_history.length} 条)
                    </h3>
                    <div className="space-y-2">
                      {historyData.conversation_history.length === 0 ? (
                        <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-4">
                          暂无对话历史
                        </p>
                      ) : (
                        historyData.conversation_history.map(
                          (item: any, index: number) => (
                            <div
                              key={index}
                              className={`p-3 rounded-lg ${
                                item.role === "user"
                                  ? "bg-blue-50 dark:bg-blue-900/20"
                                  : "bg-gray-100 dark:bg-gray-700"
                              }`}
                            >
                              <div className="flex items-center justify-between mb-1">
                                <span
                                  className={`text-xs font-medium ${
                                    item.role === "user"
                                      ? "text-blue-600 dark:text-blue-400"
                                      : "text-gray-600 dark:text-gray-400"
                                  }`}
                                >
                                  {item.role === "user" ? "用户" : "助手"}
                                </span>
                                <span className="text-xs text-gray-400">
                                  {item.timestamp}
                                </span>
                              </div>
                              <p className="text-sm text-gray-700 dark:text-gray-300">
                                {item.content}
                              </p>
                            </div>
                          ),
                        )
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  <History className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>无法获取会话历史</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
