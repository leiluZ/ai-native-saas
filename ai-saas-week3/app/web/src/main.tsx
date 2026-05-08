import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { ChatContainer } from "./components/ChatContainer";
import { RAGPanel } from "./components/RAGPanel";
import "./index.css";

const App: React.FC = () => {
  const [activePanel, setActivePanel] = useState<"chat" | "rag">("chat");

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
      {/* Navigation Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                AI SaaS Week3
              </h1>
              <nav className="flex space-x-1">
                <button
                  onClick={() => setActivePanel("chat")}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    activePanel === "chat"
                      ? "bg-blue-500 text-white"
                      : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                  }`}
                >
                  Chat Agent
                </button>
                <button
                  onClick={() => setActivePanel("rag")}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    activePanel === "rag"
                      ? "bg-blue-500 text-white"
                      : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                  }`}
                >
                  RAG Pipeline
                </button>
              </nav>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activePanel === "chat" ? <ChatContainer /> : <RAGPanel />}
      </main>
    </div>
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
