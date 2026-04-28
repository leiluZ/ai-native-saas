import { create } from "zustand";
import { Message, ChatState } from "../types";

const STREAMING_DELAY = 50;

const mockResponses = [
  "我来帮您处理这个问题。首先，让我分析一下您的需求...",
  "好的，我理解了。让我为您详细解释一下...",
  "这个问题很有意思！让我从几个方面来分析...",
  "根据您的描述，我认为最佳方案是...",
  "感谢您的提问！这是一个很好的问题，让我来解答...",
];

const generateMockResponse = () => {
  return mockResponses[Math.floor(Math.random() * mockResponses.length)];
};

interface ChatStore extends ChatState {
  sendMessage: (content: string) => Promise<void>;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  isStreaming: false,
  error: null,
  theme: (localStorage.getItem("theme") as "light" | "dark") || "light",

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
    set({ messages: [] });
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

    try {
      const mockResponse = generateMockResponse();
      let currentContent = "";

      for (let i = 0; i < mockResponse.length; i++) {
        await new Promise((resolve) => setTimeout(resolve, STREAMING_DELAY));
        currentContent += mockResponse[i];
        updateMessage(assistantMessage.id, currentContent);
      }

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
      setError("网络连接失败，请重试");
      updateMessage(assistantMessage.id, "❌ 发送失败，请重试");
    } finally {
      setStreaming(false);
    }
  },
}));
