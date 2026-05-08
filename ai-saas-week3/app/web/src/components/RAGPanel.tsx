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
  CheckCircle,
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

export const RAGPanel: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [textInput, setTextInput] = useState("");
  const [chunkSize, setChunkSize] = useState(512);
  const [overlapRatio, setOverlapRatio] = useState(15);
  const [strategy, setStrategy] = useState<"fixed" | "recursive" | "header_aware">(
    "recursive"
  );
  const [results, setResults] = useState<RAGResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"upload" | "text">("upload");

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
    if (files.length === 0 && !textInput.trim()) return;

    setLoading(true);
    try {
      if (activeTab === "upload" && files.length > 0) {
        const formData = new FormData();
        files.forEach((file) => formData.append("files", file));
        formData.append("chunk_size", chunkSize.toString());
        formData.append("overlap_ratio", (overlapRatio / 100).toString());
        formData.append("chunk_strategy", strategy);

        const response = await fetch(
          `${import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"}/rag/parse`,
          {
            method: "POST",
            body: formData,
          }
        );

        if (response.ok) {
          const data = await response.json();
          setResults(data);
        } else {
          console.error("Failed to parse documents");
        }
      } else if (activeTab === "text" && textInput.trim()) {
        const response = await fetch(
          `${import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"}/rag/chunk`,
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
          }
        );

        if (response.ok) {
          const data = await response.json();
          setResults({
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
          });
        } else {
          console.error("Failed to chunk text");
        }
      }
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleDoc = (source: string) => {
    setExpandedDoc(expandedDoc === source ? null : source);
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
                  setStrategy(e.target.value as "fixed" | "recursive" | "header_aware")
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

            {!results ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>No results yet</p>
                <p className="text-sm mt-2">Upload files or enter text and click Execute</p>
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
                    <p className="text-sm text-gray-600 dark:text-gray-400">Success</p>
                  </div>
                  <div className="flex-1 bg-red-50 dark:bg-red-900/30 rounded-lg p-4">
                    <div className="flex items-center text-red-600 dark:text-red-400">
                      <AlertCircle className="w-5 h-5 mr-2" />
                      <span className="text-2xl font-bold">
                        {results.error_count}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Errors</p>
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
                                  {doc.chunk_stats.min_tokens}-{doc.chunk_stats.max_tokens}
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
    </div>
  );
};
