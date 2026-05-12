import React, { useState } from "react";
import {
  Upload,
  FileText,
  LayoutGrid,
  Settings,
  Play,
  Trash2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  MessageCircle,
  Send,
  Loader2,
  BookOpen,
  Zap,
} from "lucide-react";

interface ParsedDocument {
  content: string;
  metadata: {
    source: string;
    file_type: string;
    page_count?: number;
    parsed_at: string;
  };
  chunks?: {
    id: string;
    content: string;
    token_count: number;
    start_idx: number;
  }[];
  chunk_stats?: {
    total_chunks: number;
    avg_tokens: number;
    min_tokens: number;
    max_tokens: number;
    p95_tokens: number;
  };
}

interface ErrorInfo {
  file: string;
  error: string;
}

interface RAGResult {
  success_count: number;
  error_count: number;
  documents: ParsedDocument[];
  errors: ErrorInfo[];
}

interface ChatMessage {
  id: string;
  content: string;
  role: "user" | "assistant";
  confidence?: string;
  references?: string[];
  timestamp: Date;
}

export const RAGPanel: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [textInput, setTextInput] = useState("");
  const [chunkSize, setChunkSize] = useState(512);
  const [overlapRatio, setOverlapRatio] = useState(15);
  const [strategy, setStrategy] = useState<
    "fixed" | "recursive" | "header_aware"
  >("recursive");
  const [results, setResults] = useState<RAGResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"upload" | "text">("upload");
  // Q&A related state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [questionInput, setQuestionInput] = useState("");
  const [isAnswering, setIsAnswering] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles([...files, ...Array.from(e.target.files)]);
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const clearFiles = () => {
    setFiles([]);
    setResults(null);
  };

  const parseDocuments = async () => {
    if (files.length === 0 && !textInput.trim()) {
      console.log("[RAGPanel] No files and no text input, skipping");
      return;
    }

    setLoading(true);
    setError(null);
    console.log("[RAGPanel] Starting parseDocuments", {
      activeTab,
      filesCount: files.length,
      textInputLength: textInput.length,
    });

    try {
      let parseResult: RAGResult | null = null;

      if (activeTab === "upload" && files.length > 0) {
        console.log("[RAGPanel] Processing file upload");
        const formData = new FormData();
        files.forEach((file) => formData.append("files", file));
        formData.append("chunk_size", chunkSize.toString());
        formData.append("overlap_ratio", (overlapRatio / 100).toString());
        formData.append("chunk_strategy", strategy);

        const apiUrl =
          import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
        console.log("[RAGPanel] Sending to:", `${apiUrl}/rag/parse`);

        const response = await fetch(`${apiUrl}/rag/parse`, {
          method: "POST",
          body: formData,
        });

        console.log("[RAGPanel] Parse response status:", response.status);

        if (response.ok) {
          const data = await response.json();
          console.log("[RAGPanel] Parse successful:", data);
          parseResult = data;
        } else {
          let errorMessage;
          try {
            const errorData = await response.json();
            errorMessage = errorData?.detail || "Failed to parse documents";
          } catch {
            errorMessage = `Failed to parse documents (HTTP ${response.status})`;
          }
          setError(errorMessage);
          console.error("[RAGPanel] Parse failed:", errorMessage);
          return;
        }
      } else if (activeTab === "text" && textInput.trim()) {
        console.log("[RAGPanel] Processing text input");
        const response = await fetch(
          `${
            import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"
          }/rag/chunk`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              content: textInput,
              source: "text_input",
              chunk_size: chunkSize,
              overlap_ratio: overlapRatio / 100,
              strategy,
            }),
          },
        );

        if (response.ok) {
          const data = await response.json();
          parseResult = {
            success_count: 1,
            error_count: 0,
            documents: [
              {
                content: textInput,
                metadata: {
                  source: "text_input",
                  file_type: "text/plain",
                  parsed_at: new Date().toISOString(),
                },
                chunks: data.chunks,
                chunk_stats: data.stats,
              },
            ],
            errors: [],
          };
        } else {
          const errorData = await response.json().catch(() => null);
          const errorMessage = errorData?.detail || "Failed to chunk text";
          setError(errorMessage);
          console.error("[RAGPanel] Failed to chunk text:", errorMessage);
          return;
        }
      }

      // 自动索引到向量数据库
      if (parseResult && parseResult.documents.length > 0) {
        for (const doc of parseResult.documents) {
          if (doc.chunks && doc.chunks.length > 0) {
            const indexResponse = await fetch(
              `${
                import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"
              }/rag/index`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  source: doc.metadata.source,
                  chunks: doc.chunks.map((c) => ({
                    content: c.content,
                    metadata: {
                      source: doc.metadata.source,
                      chunk_index: c.id,
                      token_count: c.token_count,
                    },
                  })),
                }),
              },
            );

            if (indexResponse.ok) {
              const indexData = await indexResponse.json();
              console.log(
                `[Index] ${doc.metadata.source}: ${indexData.chunks_indexed} chunks indexed`,
              );
            } else {
              const errorData = await indexResponse.json().catch(() => null);
              const errorMessage =
                errorData?.detail || `Failed to index ${doc.metadata.source}`;
              console.error("[Index] Failed to index:", errorMessage);
            }
          }
        }
      }

      if (parseResult) {
        setResults(parseResult);
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error";
      setError(errorMessage);
      console.error("Error:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleDoc = (source: string) => {
    setExpandedDoc(expandedDoc === source ? null : source);
  };

  const askQuestion = async () => {
    if (!questionInput.trim() || !results) return;

    setIsAnswering(true);

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      content: questionInput,
      role: "user",
      timestamp: new Date(),
    };
    setChatMessages((prev) => [...prev, userMessage]);

    const apiUrl =
      import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

    // Retry logic for CI robustness
    const maxRetries = 3;
    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(
          `[RAGPanel] Sending request to RAG endpoint (attempt ${attempt}/${maxRetries})`,
        );
        const response = await fetch(`${apiUrl}/chat/rag/execute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: questionInput,
            session_id: sessionId || undefined,
          }),
        });

        console.log("[RAGPanel] Response status:", response.status);

        if (response.ok) {
          const data = await response.json();
          console.log(
            "[RAGPanel] Response data:",
            JSON.stringify(data, null, 2),
          );

          if (!sessionId) {
            setSessionId(data.data.session_id);
          }

          let responseContent = data.data.response;
          let responseConfidence = data.data.confidence;
          let responseReferences = data.data.references;

          try {
            const parsedResponse = JSON.parse(data.data.response);
            responseContent = parsedResponse.answer || data.data.response;
            responseConfidence =
              parsedResponse.confidence || data.data.confidence;
            responseReferences =
              parsedResponse.references || data.data.references;
          } catch (e) {
            console.log("Response is not JSON, using raw response");
          }

          const assistantMessage: ChatMessage = {
            id: (Date.now() + 1).toString(),
            content: responseContent,
            role: "assistant",
            confidence: responseConfidence,
            references: responseReferences,
            timestamp: new Date(),
          };
          console.log("[RAGPanel] Adding assistant message:", assistantMessage);
          setChatMessages((prev) => [...prev, assistantMessage]);
          setIsAnswering(false);
          setQuestionInput("");
          return; // Success, exit loop
        } else {
          const errorData = await response.json().catch(() => null);
          console.error(
            "[RAGPanel] Failed to get answer, status:",
            response.status,
            "error:",
            errorData,
          );
          throw new Error(`API returned status ${response.status}`);
        }
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        console.error(
          `[RAGPanel] Error on attempt ${attempt}:`,
          lastError.message,
        );

        if (attempt < maxRetries) {
          const delay = Math.pow(2, attempt) * 1000; // Exponential backoff: 2s, 4s
          console.log(`[RAGPanel] Retrying in ${delay}ms...`);
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      }
    }

    // If all retries failed
    console.error("[RAGPanel] All retries failed:", lastError?.message);
    const errorMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      content: lastError?.message || "连接错误，请检查后端服务是否运行。",
      role: "assistant",
      timestamp: new Date(),
    };
    setChatMessages((prev) => [...prev, errorMessage]);

    setIsAnswering(false);
    setQuestionInput("");
  };

  const getConfidenceColor = (confidence?: string) => {
    switch (confidence) {
      case "high":
        return "bg-green-100 text-green-700 border-green-300";
      case "medium":
        return "bg-yellow-100 text-yellow-700 border-yellow-300";
      case "low":
        return "bg-red-100 text-red-700 border-red-300";
      default:
        return "bg-gray-100 text-gray-700 border-gray-300";
    }
  };

  const getConfidenceLabel = (confidence?: string) => {
    switch (confidence) {
      case "high":
        return "高置信度";
      case "medium":
        return "中置信度";
      case "low":
        return "低置信度";
      default:
        return "未知";
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          RAG Pipeline Test Portal
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Test document parsing and chunking locally
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab("upload")}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === "upload"
              ? "bg-blue-500 text-white"
              : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
          }`}
        >
          <Upload className="inline-block w-4 h-4 mr-2" />
          Upload Documents
        </button>
        <button
          onClick={() => setActiveTab("text")}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            activeTab === "text"
              ? "bg-blue-500 text-white"
              : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
          }`}
        >
          <FileText className="inline-block w-4 h-4 mr-2" />
          Text Input
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration Panel */}
        <div className="lg:col-span-1">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
              <Settings className="w-5 h-5 mr-2 text-blue-500" />
              Chunk Settings
            </h2>

            {/* Chunk Size */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Chunk Size: {chunkSize} tokens
              </label>
              <input
                type="range"
                min="128"
                max="2048"
                value={chunkSize}
                onChange={(e) => setChunkSize(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>128</span>
                <span>2048</span>
              </div>
            </div>

            {/* Overlap Ratio */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Overlap Ratio: {overlapRatio}%
              </label>
              <input
                type="range"
                min="0"
                max="50"
                value={overlapRatio}
                onChange={(e) => setOverlapRatio(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0%</span>
                <span>50%</span>
              </div>
            </div>

            {/* Strategy */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Chunk Strategy
              </label>
              <select
                value={strategy}
                onChange={(e) =>
                  setStrategy(
                    e.target.value as "fixed" | "recursive" | "header_aware",
                  )
                }
                className="w-full px-3 py-2 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="fixed">Fixed Size</option>
                <option value="recursive">Recursive</option>
                <option value="header_aware">Header Aware</option>
              </select>
            </div>

            {/* Upload Area */}
            {activeTab === "upload" && (
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Upload Files
                </label>
                <div
                  className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center hover:border-blue-500 transition-colors cursor-pointer"
                  onClick={() =>
                    document.getElementById("file-upload")?.click()
                  }
                >
                  <Upload className="w-10 h-10 mx-auto text-gray-400 mb-2" />
                  <p className="text-gray-600 dark:text-gray-400">
                    Click to upload PDF, DOCX, HTML, or TXT files
                  </p>
                  <input
                    id="file-upload"
                    type="file"
                    multiple
                    accept=".pdf,.docx,.html,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </div>

                {files.length > 0 && (
                  <div className="mt-4 space-y-2">
                    {files.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between bg-gray-50 dark:bg-gray-700 rounded-lg px-3 py-2"
                      >
                        <span className="text-sm text-gray-700 dark:text-gray-300 truncate flex-1 mr-2">
                          {file.name}
                        </span>
                        <button
                          onClick={() => removeFile(index)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={clearFiles}
                      className="w-full text-sm text-gray-500 hover:text-red-500 py-2"
                    >
                      Clear All Files
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Text Input */}
            {activeTab === "text" && (
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Input Text
                </label>
                <textarea
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="Enter text to chunk..."
                  rows={8}
                  className="w-full px-3 py-2 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
            )}

            {/* Execute Button */}
            <button
              onClick={parseDocuments}
              disabled={loading || (files.length === 0 && !textInput.trim())}
              className={`w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors ${
                loading || (files.length === 0 && !textInput.trim())
                  ? "bg-gray-300 dark:bg-gray-600 text-gray-500 cursor-not-allowed"
                  : "bg-blue-500 hover:bg-blue-600 text-white"
              }`}
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Execute RAG Pipeline
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-2">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
              <LayoutGrid className="w-5 h-5 mr-2 text-blue-500" />
              Results
            </h2>

            {error ? (
              <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
                <div className="flex items-center text-red-600 dark:text-red-400">
                  <AlertTriangle className="w-5 h-5 mr-2" />
                  <span className="font-medium">Error</span>
                </div>
                <p className="mt-2 text-red-700 dark:text-red-300">{error}</p>
              </div>
            ) : !results ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>No results yet</p>
                <p className="text-sm mt-2">
                  Upload files or enter text and click Execute
                </p>
              </div>
            ) : (
              <div>
                {/* Summary */}
                <div className="flex gap-4 mb-6">
                  <div className="flex-1 bg-green-50 dark:bg-green-900/30 rounded-lg p-4">
                    <div className="flex items-center text-green-600 dark:text-green-400">
                      <CheckCircle className="w-5 h-5 mr-2" />
                      <span className="text-2xl font-bold">
                        {results.success_count}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Success
                    </p>
                  </div>
                  <div className="flex-1 bg-red-50 dark:bg-red-900/30 rounded-lg p-4">
                    <div className="flex items-center text-red-600 dark:text-red-400">
                      <AlertCircle className="w-5 h-5 mr-2" />
                      <span className="text-2xl font-bold">
                        {results.error_count}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Errors
                    </p>
                  </div>
                </div>

                {/* Errors */}
                {results.errors.length > 0 && (
                  <div className="mb-6">
                    <h3 className="text-sm font-medium text-red-600 dark:text-red-400 mb-2">
                      Failed Files
                    </h3>
                    <div className="space-y-2">
                      {results.errors.map((error, index) => (
                        <div
                          key={index}
                          className="bg-red-50 dark:bg-red-900/30 rounded-lg p-3 text-sm"
                        >
                          <span className="font-medium text-red-700 dark:text-red-400">
                            {error.file}
                          </span>
                          <p className="text-red-600 dark:text-red-300 mt-1">
                            {error.error}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Documents */}
                <div className="space-y-4">
                  {results.documents.map((doc, docIndex) => (
                    <div
                      key={docIndex}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
                    >
                      <button
                        onClick={() => toggleDoc(doc.metadata.source)}
                        className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
                      >
                        <div className="flex items-center">
                          <FileText className="w-5 h-5 mr-2 text-blue-500" />
                          <span className="font-medium text-gray-900 dark:text-white">
                            {doc.metadata.source}
                          </span>
                          <span className="text-xs text-gray-500 ml-2">
                            ({doc.metadata.file_type})
                          </span>
                        </div>
                        <div className="flex items-center">
                          {doc.chunk_stats && (
                            <span className="text-sm text-gray-600 dark:text-gray-400 mr-2">
                              {doc.chunk_stats.total_chunks} chunks
                            </span>
                          )}
                          {expandedDoc === doc.metadata.source ? (
                            <ChevronUp className="w-5 h-5 text-gray-500" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-500" />
                          )}
                        </div>
                      </button>

                      {expandedDoc === doc.metadata.source && (
                        <div className="p-4">
                          {/* Chunk Stats */}
                          {doc.chunk_stats && (
                            <div className="grid grid-cols-4 gap-4 mb-4">
                              <div className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-blue-600 dark:text-blue-400">
                                  {doc.chunk_stats.total_chunks}
                                </div>
                                <div className="text-xs text-gray-600 dark:text-gray-400">
                                  Total Chunks
                                </div>
                              </div>
                              <div className="bg-green-50 dark:bg-green-900/30 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-green-600 dark:text-green-400">
                                  {doc.chunk_stats.avg_tokens}
                                </div>
                                <div className="text-xs text-gray-600 dark:text-gray-400">
                                  Avg Tokens
                                </div>
                              </div>
                              <div className="bg-yellow-50 dark:bg-yellow-900/30 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-yellow-600 dark:text-yellow-400">
                                  {doc.chunk_stats.min_tokens}-
                                  {doc.chunk_stats.max_tokens}
                                </div>
                                <div className="text-xs text-gray-600 dark:text-gray-400">
                                  Min-Max
                                </div>
                              </div>
                              <div className="bg-purple-50 dark:bg-purple-900/30 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold text-purple-600 dark:text-purple-400">
                                  {doc.chunk_stats.p95_tokens}
                                </div>
                                <div className="text-xs text-gray-600 dark:text-gray-400">
                                  P95 Tokens
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Content Preview */}
                          <div className="mb-4">
                            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                              Content Preview
                            </h4>
                            <div className="bg-gray-100 dark:bg-gray-900 rounded-lg p-3 max-h-32 overflow-auto">
                              <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                                {doc.content.slice(0, 500)}
                                {doc.content.length > 500 && "..."}
                              </p>
                            </div>
                          </div>

                          {/* Chunks */}
                          {doc.chunks && doc.chunks.length > 0 && (
                            <div>
                              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Chunks ({doc.chunks.length})
                              </h4>
                              <div className="space-y-2 max-h-64 overflow-auto">
                                {doc.chunks.map((chunk, chunkIndex) => (
                                  <div
                                    key={chunkIndex}
                                    className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3"
                                  >
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
                                        Chunk {chunkIndex + 1}
                                      </span>
                                      <span className="text-xs text-gray-500">
                                        {chunk.token_count} tokens
                                      </span>
                                    </div>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                                      {chunk.content}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Q&A Panel */}
      <div className="mt-8">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center">
            <MessageCircle className="w-5 h-5 mr-2 text-blue-500" />
            Knowledge Base Q&A
            <Zap className="w-4 h-4 ml-2 text-yellow-500" />
          </h2>

          {/* Chat Messages */}
          <div className="space-y-4 mb-4 max-h-64 overflow-y-auto">
            {!results ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>请先上传文档并执行 RAG Pipeline</p>
                <p className="text-sm mt-1">
                  上传文件或输入文本，点击 "Execute RAG Pipeline" 按钮
                </p>
              </div>
            ) : chatMessages.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>开始与知识库对话</p>
                <p className="text-sm mt-1">基于上传的文档提问</p>
              </div>
            ) : (
              chatMessages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-4 py-3 ${
                      message.role === "user"
                        ? "bg-blue-500 text-white rounded-br-md"
                        : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-bl-md"
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">
                      {message.content}
                    </p>
                    {message.role === "assistant" &&
                      (message.confidence || message.references?.length) && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {message.confidence && (
                            <span
                              className={`text-xs px-2 py-1 rounded-full border ${getConfidenceColor(
                                message.confidence,
                              )}`}
                            >
                              {getConfidenceLabel(message.confidence)}
                            </span>
                          )}
                          {message.references?.length &&
                            message.references.length > 0 && (
                              <span className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-700 border border-blue-300">
                                {message.references.length} 个引用
                              </span>
                            )}
                        </div>
                      )}
                    {message.references?.length &&
                      message.references.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                            引用来源:
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {message.references.slice(0, 5).map((ref, idx) => (
                              <span
                                key={idx}
                                className="text-xs px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300"
                              >
                                {ref}
                              </span>
                            ))}
                            {message.references.length > 5 && (
                              <span className="text-xs text-gray-500">
                                +{message.references.length - 5}
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Input Area */}
          <div className="flex gap-3">
            <input
              type="text"
              value={questionInput}
              onChange={(e) => setQuestionInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && askQuestion()}
              placeholder="基于文档内容提问..."
              disabled={isAnswering}
              className="flex-1 px-4 py-3 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              onClick={askQuestion}
              disabled={!questionInput.trim() || isAnswering}
              className={`px-6 py-3 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                !questionInput.trim() || isAnswering
                  ? "bg-gray-300 dark:bg-gray-600 text-gray-500 cursor-not-allowed"
                  : "bg-green-500 hover:bg-green-600 text-white"
              }`}
            >
              {isAnswering ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Thinking...
                </>
              ) : (
                <>
                  <Send className="w-5 h-5" />
                  Ask
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
