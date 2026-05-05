import { create } from "zustand";
import { Message, ChatState } from "../types";

const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

type AgentType = "agent" | "langgraph";

interface ChatStore extends ChatState {
  agentType: AgentType;
  sendMessage: (content: string) => Promise<void>;
  approveMessage: (
    threadId: string,
    approved: boolean,
    modifiedResult?: string,
  ) => Promise<void>;
  setAgentType: (type: AgentType) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  isStreaming: false,
  error: null,
  theme: (localStorage.getItem("theme") as "light" | "dark") || "light",
  agentType: "langgraph",
  currentThreadId: localStorage.getItem("threadId") || `thread-${Date.now()}`,

  setAgentType: (type: AgentType) => {
    set({ agentType: type });
    localStorage.setItem("agentType", type);
  },

  setCurrentThreadId: (threadId: string) => {
    set({ currentThreadId: threadId });
    localStorage.setItem("threadId", threadId);
  },

  addMessage: (message: Message) => {
    set((state) => ({
      messages: [...state.messages, message],
      error: null,
    }));
  },

  updateMessage: (id: string, content: string) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content } : msg,
      ),
    }));
  },

  setStreaming: (streaming: boolean) => {
    set({ isStreaming: streaming });
  },

  setError: (error: string | null) => {
    set({ error });
  },

  toggleTheme: () => {
    set((state) => {
      const newTheme = state.theme === "light" ? "dark" : "light";
      localStorage.setItem("theme", newTheme);
      document.documentElement.classList.toggle("dark", newTheme === "dark");
      return { theme: newTheme };
    });
  },

  clearMessages: () => {
    const newThreadId = `thread-${Date.now()}`;
    set({ messages: [], currentThreadId: newThreadId });
    localStorage.setItem("threadId", newThreadId);
  },

  sendMessage: async (content: string) => {
    const { addMessage, updateMessage, setStreaming, setError } = get();

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date(),
    };
    addMessage(userMessage);

    const assistantMessage: Message = {
      id: `msg-${Date.now()}-assistant`,
      role: "assistant",
      content: "",
      timestamp: new Date(),
      isLoading: true,
    };
    addMessage(assistantMessage);
    setStreaming(true);

    const { agentType, currentThreadId, setCurrentThreadId } = get();
    const endpoint =
      agentType === "langgraph"
        ? `${API_BASE_URL}/chat/langgraph/human-in-loop`
        : `${API_BASE_URL}/chat/agent`;

    const requestBody =
      agentType === "langgraph"
        ? { prompt: content, session_id: currentThreadId }
        : { prompt: content };

    try {
      console.log("[ChatStore] Sending request:", {
        endpoint,
        requestBody,
        agentType,
      });

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      console.log(
        "[ChatStore] Received response:",
        JSON.stringify(data, null, 2),
      );

      if (data.code === 202 && data.extra?.needsApproval) {
        const threadId = data.extra.threadId;
        const confidence = data.extra.confidence;
        const originalResult = data.data?.response || "";

        if (threadId && threadId !== get().currentThreadId) {
          setCurrentThreadId(threadId);
        }

        console.log("[ChatStore] Needs approval:", {
          threadId,
          confidence,
          originalResult,
        });

        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === assistantMessage.id
              ? {
                  ...msg,
                  content: originalResult,
                  isLoading: false,
                  needsApproval: true,
                  threadId,
                  confidence,
                  originalResult,
                }
              : msg,
          ),
        }));
        return;
      }

      const agentResponse = data.data?.response || "No response from agent";
      updateMessage(assistantMessage.id, agentResponse);

      const messages = get().messages;
      const msgIndex = messages.findIndex((m) => m.id === assistantMessage.id);
      if (msgIndex !== -1) {
        const updatedMessages = [...messages];
        updatedMessages[msgIndex] = {
          ...updatedMessages[msgIndex],
          isLoading: false,
        };
        set({ messages: updatedMessages });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "网络连接失败");
      updateMessage(
        assistantMessage.id,
        "❌ 请求失败，请检查 Ollama 服务是否运行",
      );
    } finally {
      setStreaming(false);
    }
  },

  approveMessage: async (
    threadId: string,
    approved: boolean,
    modifiedResult?: string,
  ) => {
    const { setError } = get();

    try {
      const response = await fetch(`${API_BASE_URL}/chat/approve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          thread_id: threadId,
          approved,
          modified_result: modifiedResult,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      if (data.code === 200) {
        const finalResult = approved
          ? data.data.original_result
          : data.data.modified_result || modifiedResult;

        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.threadId === threadId
              ? {
                  ...msg,
                  content: `[已审批] ${finalResult}`,
                  needsApproval: false,
                }
              : msg,
          ),
        }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "审批请求失败");
    }
  },
}));
