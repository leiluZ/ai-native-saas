import React, { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { useChatStore } from "../store/chatStore";
import { Moon, Sun, Trash2, RefreshCw } from "lucide-react";

export const ChatContainer: React.FC = () => {
  const { messages, theme, toggleTheme, clearMessages, error, setError, agentType, setAgentType } =
    useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

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
                LangGraph
              </button>
            </div>
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
    </div>
  );
};
