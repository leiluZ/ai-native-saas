import React, { useState } from "react";
import {
  MessageCircle,
  Bot,
  AlertTriangle,
  Check,
  X,
  Edit3,
} from "lucide-react";
import { Message } from "../types";
import { useChatStore } from "../store/chatStore";

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === "user";
  const [showEdit, setShowEdit] = useState(false);
  const [modifiedResult, setModifiedResult] = useState("");
  const { approveMessage } = useChatStore();

  const handleApprove = async () => {
    if (message.threadId) {
      await approveMessage(message.threadId, true);
    }
  };

  const handleReject = async () => {
    if (message.threadId) {
      const resultToSend =
        modifiedResult.trim() || message.originalResult || message.content;
      await approveMessage(message.threadId, false, resultToSend);
      setShowEdit(false);
      setModifiedResult("");
    }
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`flex items-end gap-2 max-w-[70%] ${
          isUser ? "flex-row-reverse" : "flex-row"
        }`}
      >
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            isUser
              ? "bg-blue-500 text-white"
              : "bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
          }`}
        >
          {isUser ? (
            <MessageCircle className="w-5 h-5" />
          ) : (
            <Bot className="w-5 h-5" />
          )}
        </div>
        <div
          className={`px-4 py-3 rounded-2xl ${
            isUser
              ? "bg-blue-500 text-white rounded-br-md"
              : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-100 rounded-bl-md"
          }`}
        >
          <p className="text-sm leading-relaxed">{message.content}</p>

          {message.needsApproval && (
            <div className="mt-3 p-3 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 rounded-lg">
              <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 mb-2">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-xs font-medium">
                  置信度较低 ({message.confidence?.toFixed(2)})，请确认结果
                </span>
              </div>

              {!showEdit ? (
                <div className="flex gap-2">
                  <button
                    onClick={handleApprove}
                    className="flex items-center gap-1 px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white text-xs rounded-lg transition-colors"
                  >
                    <Check className="w-3 h-3" />
                    批准
                  </button>
                  <button
                    onClick={() => setShowEdit(true)}
                    className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-600 dark:hover:bg-gray-500 text-gray-700 dark:text-gray-200 text-xs rounded-lg transition-colors"
                  >
                    <Edit3 className="w-3 h-3" />
                    修改
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <textarea
                    value={modifiedResult}
                    onChange={(e) => setModifiedResult(e.target.value)}
                    placeholder={
                      message.originalResult || "输入修改后的结果..."
                    }
                    className="w-full px-2 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 resize-none"
                    rows={2}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleReject}
                      className="flex items-center gap-1 px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs rounded-lg transition-colors"
                    >
                      <X className="w-3 h-3" />
                      发送修改
                    </button>
                    <button
                      onClick={() => {
                        setShowEdit(false);
                        setModifiedResult("");
                      }}
                      className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {message.isLoading && (
            <div className="flex gap-1 mt-2">
              <span
                className="w-2 h-2 bg-white/60 rounded-full animate-bounce"
                style={{ animationDelay: "0ms" }}
              />
              <span
                className="w-2 h-2 bg-white/60 rounded-full animate-bounce"
                style={{ animationDelay: "150ms" }}
              />
              <span
                className="w-2 h-2 bg-white/60 rounded-full animate-bounce"
                style={{ animationDelay: "300ms" }}
              />
            </div>
          )}
          <div
            className={`text-xs mt-1 opacity-60 ${
              isUser ? "text-white" : "text-gray-500 dark:text-gray-400"
            }`}
          >
            {new Date(message.timestamp).toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
