import React, { useState, KeyboardEvent } from "react";
import { Send, Loader2 } from "lucide-react";
import { useChatStore } from "../store/chatStore";

export const ChatInput: React.FC = () => {
  const [inputValue, setInputValue] = useState("");
  const { sendMessage, isStreaming } = useChatStore();

  const handleSend = async () => {
    if (!inputValue.trim() || isStreaming) return;

    await sendMessage(inputValue.trim());
    setInputValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-white dark:bg-gray-800">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息..."
              disabled={isStreaming}
              rows={1}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              style={{ minHeight: "44px", maxHeight: "120px" }}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isStreaming}
            className={`p-3 rounded-xl transition-all flex-shrink-0 ${
              inputValue.trim() && !isStreaming
                ? "bg-blue-500 hover:bg-blue-600 text-white"
                : "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed"
            }`}
          >
            {isStreaming ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
          按 Enter 发送，Shift + Enter 换行
        </p>
      </div>
    </div>
  );
};
