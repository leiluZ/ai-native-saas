import React, { useState, useEffect } from "react";
import { X, RefreshCw, GitBranch, FileCode } from "lucide-react";

interface LangGraphPanelProps {
  threadId: string;
  onClose: () => void;
}

type ViewMode = "trace" | "mermaid";

export const LangGraphPanel: React.FC<LangGraphPanelProps> = ({
  threadId,
  onClose,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>("trace");
  const [traceData, setTraceData] = useState<any[]>([]);
  const [mermaidCode, setMermaidCode] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const baseUrl =
    import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

  const fetchTrace = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${baseUrl}/chat/langgraph/sessions/${threadId}/trace`,
      );
      if (response.ok) {
        const data = await response.json();
        setTraceData(data.data || []);
      } else {
        setError("获取执行轨迹失败");
      }
    } catch (err) {
      setError("网络请求失败");
      console.error("Failed to fetch trace:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchMermaid = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${baseUrl}/chat/langgraph/sessions/${threadId}/mermaid`,
      );
      if (response.ok) {
        const data = await response.json();
        setMermaidCode(data.data || "");
      } else {
        setError("获取 Mermaid 图失败");
      }
    } catch (err) {
      setError("网络请求失败");
      console.error("Failed to fetch mermaid:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (viewMode === "trace") {
      fetchTrace();
    } else {
      fetchMermaid();
    }
  }, [viewMode, threadId]);

  const handleRefresh = () => {
    if (viewMode === "trace") {
      fetchTrace();
    } else {
      fetchMermaid();
    }
  };

  const renderTrace = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex items-center justify-center h-64 text-red-500">
          {error}
        </div>
      );
    }

    if (traceData.length === 0) {
      return (
        <div className="flex items-center justify-center h-64 text-gray-500">
          暂无执行轨迹数据
        </div>
      );
    }

    return (
      <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
        {traceData.map((entry, index) => (
          <div
            key={index}
            className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-blue-600 dark:text-blue-400">
                {entry.node}
              </span>
              <span className="text-xs text-gray-400">
                {entry.timestamp?.replace("T", " ")?.slice(0, 19)}
              </span>
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-300">
              <pre className="whitespace-pre-wrap break-all">
                {JSON.stringify(entry.state, null, 2)}
              </pre>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderMermaid = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex items-center justify-center h-64 text-red-500">
          {error}
        </div>
      );
    }

    if (!mermaidCode) {
      return (
        <div className="flex items-center justify-center h-64 text-gray-500">
          暂无 Mermaid 图数据
        </div>
      );
    }

    return (
      <div className="max-h-96 overflow-y-auto pr-2">
        <div className="bg-gray-900 rounded-lg p-4">
          <pre className="text-green-400 text-sm whitespace-pre-wrap break-all font-mono">
            {mermaidCode}
          </pre>
        </div>
        <div className="mt-4 text-xs text-gray-500 dark:text-gray-400">
          <p>
            提示：复制以上代码到 Mermaid 渲染器（如 mermaid.live）查看可视化图表
          </p>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <GitBranch className="w-5 h-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
              LangGraph 执行信息
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setViewMode("trace")}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
              viewMode === "trace"
                ? "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 border-b-2 border-blue-500"
                : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
            }`}
          >
            <FileCode className="w-4 h-4" />
            执行轨迹
          </button>
          <button
            onClick={() => setViewMode("mermaid")}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
              viewMode === "mermaid"
                ? "bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400 border-b-2 border-blue-500"
                : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
            }`}
          >
            <GitBranch className="w-4 h-4" />
            Mermaid 序列图
          </button>
        </div>

        <div className="p-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Thread ID: {threadId.slice(0, 20)}...
          </span>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </button>
        </div>

        <div className="flex-1 overflow-hidden p-4">
          {viewMode === "trace" ? renderTrace() : renderMermaid()}
        </div>
      </div>
    </div>
  );
};
