import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  Loader2,
  LogOut,
  File,
  Plus,
  Trash2,
  Menu,
  X,
  Upload,
  FileText,
  MessageSquare,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  key_points?: string[];
  confidence?: number;
  confidence_label?: string;
  mode?: "strong" | "hybrid" | "fallback";
  graph_used?: boolean;
  detailed_hits?: DetailedHit[];
}

interface Citation {
  id?: string;
  source?: string;
  page?: number;
  content?: string;
  parent_context?: string;
}

interface DetailedHit {
  index: number;
  content: string;
  metadata: any;
  score: number;
  graph_score: number;
  parent_context?: string;
}

interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

interface Document {
  id: number;
  filename: string;
  file_size: number;
  mime_type: string;
  uploaded_at: string;
}

interface DashboardPageProps {
  user: any;
  token: string;
  onLogout: () => void;
}

// SourceNode Component
const SourceNode: React.FC<{ citation: Citation; index: number; detailedHits?: DetailedHit[] }> = ({ citation, index, detailedHits }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Find parent context from detailed hits if available
  const parentContext = citation.parent_context || 
    (detailedHits && detailedHits[index]?.parent_context) || 
    undefined;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="inline-block mr-2 mb-2"
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-3 py-1.5 bg-slate-700/50 hover:bg-slate-600/50 border border-slate-600/50 rounded-lg text-xs text-slate-300 hover:text-slate-200 transition-all flex items-center gap-1.5"
      >
        <File className="w-3 h-3" />
        <span className="font-medium">{citation.source || `Source ${index + 1}`}</span>
        {citation.page && <span className="text-slate-400">p.{citation.page}</span>}
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg text-xs text-slate-300 max-w-md"
          >
            {parentContext && (
              <div className="mb-2">
                <div className="font-medium text-slate-200 mb-1">Parent Context:</div>
                <div className="text-slate-400 italic">{parentContext}</div>
              </div>
            )}
            {citation.content && (
              <div>
                <div className="font-medium text-slate-200 mb-1">Content:</div>
                <div className="text-slate-400">{citation.content}</div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

// Logic Badge Component
const LogicBadge: React.FC<{ message: Message }> = ({ message }) => {
  if (message.role === "user") return null;

  const getBadgeConfig = () => {
    const confidence = message.confidence || 0;
    const mode = message.mode;
    const graphUsed = message.graph_used;

    if (confidence > 0.7 || mode === "strong") {
      return {
        label: "Source-Verified",
        color: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
        icon: "✓"
      };
    } else if ((confidence >= 0.4 && confidence <= 0.7) || mode === "hybrid") {
      return {
        label: "Inferred from Context",
        color: "bg-amber-500/10 text-amber-300 border-amber-500/30",
        icon: "~"
      };
    } else if (graphUsed) {
      return {
        label: "Relational Insight",
        color: "bg-purple-500/10 text-purple-300 border-purple-500/30",
        icon: "🔗"
      };
    }

    return {
      label: "General Knowledge",
      color: "bg-slate-500/10 text-slate-300 border-slate-500/30",
      icon: "?"
    };
  };

  const config = getBadgeConfig();

  return (
    <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${config.color}`}>
      <span className="mr-1">{config.icon}</span>
      {config.label}
      {message.confidence && (
        <span className="ml-1 opacity-75">
          ({Math.round((message.confidence || 0) * 100)}%)
        </span>
      )}
    </div>
  );
};

// Helper function to parse message data from backend
const parseMessage = (msg: any): Message => {
  return {
    id: msg.id,
    role: msg.role,
    content: msg.content,
    citations: msg.citations ? JSON.parse(msg.citations) : [],
    key_points: msg.key_points ? JSON.parse(msg.key_points) : [],
    confidence: msg.confidence ? parseFloat(msg.confidence) : undefined,
    confidence_label: msg.confidence,
    mode: msg.mode as "strong" | "hybrid" | "fallback",
    graph_used: msg.graph_used,
    detailed_hits: msg.detailed_hits ? JSON.parse(msg.detailed_hits) : []
  };
};

export default function DashboardPage({ user, token, onLogout }: DashboardPageProps) {
  const [activeView, setActiveView] = useState<"chat" | "documents">("chat");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef(false);
  const [graphStatus, setGraphStatus] = useState<'off'|'indexing'|'active'>('off');

  const ALLOWED_EXTENSIONS = ["pdf", "txt", "csv", "doc", "docx"];

  const getDocumentTypeLabel = (doc: Document) => {
    const extension = doc.filename.split(".").pop()?.toLowerCase();
    if (extension) {
      return extension.toUpperCase();
    }
    if (doc.mime_type) {
      if (doc.mime_type.includes("pdf")) return "PDF";
      if (doc.mime_type.includes("csv")) return "CSV";
      if (doc.mime_type.includes("msword")) return "DOC";
      if (doc.mime_type.includes("wordprocessingml")) return "DOCX";
      if (doc.mime_type.includes("text")) return "TXT";
    }
    return "FILE";
  };

  const handleUnauthorized = () => {
    setUploadStatus({
      type: "error",
      message: "Session expired. Please login again.",
    });
    onLogout();
  };

  const authenticatedFetch = async (url: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers || {});
    headers.set("Authorization", `Bearer ${token}`);

    return fetch(url, {
      ...init,
      headers,
    });
  };

  // Load conversations on mount
  useEffect(() => {
    if (initializedRef.current) {
      return;
    }
    initializedRef.current = true;
    loadConversations();
    loadDocuments();
    // initial fetch for graph status
    fetchGraphStatus();
  }, []);

  useEffect(() => {
    // Poll graph status every 10 seconds
    const id = setInterval(() => {
      fetchGraphStatus();
    }, 10000);
    return () => clearInterval(id);
  }, []);

  const fetchGraphStatus = async () => {
    try {
      const res = await authenticatedFetch('/api/system/status');
      if (res.ok) {
        const data = await res.json();
        const s = (data && data.graph_status) || 'off';
        setGraphStatus(s);
      }
    } catch (err) {
      console.error('Error fetching system status:', err);
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [currentConversation?.messages]);

  const loadConversations = async () => {
    try {
      const response = await authenticatedFetch("/api/chat/conversations");
      if (response.status === 401) {
        handleUnauthorized();
        return;
      }
      if (response.ok) {
        const data = await response.json();
        // Parse messages in each conversation
        const parsedConversations = data.conversations.map((conv: any) => ({
          ...conv,
          messages: conv.messages.map(parseMessage)
        }));
        setConversations(parsedConversations);
        if (parsedConversations.length > 0 && !currentConversation) {
          setCurrentConversation(parsedConversations[0]);
        }
      }
    } catch (err) {
      console.error("Error loading conversations:", err);
    }
  };

  const loadDocuments = async () => {
    try {
      const response = await authenticatedFetch("/api/documents/list");
      if (response.status === 401) {
        handleUnauthorized();
        return;
      }
      if (response.ok) {
        const data = await response.json();
        setDocuments(data.documents);
      }
    } catch (err) {
      console.error("Error loading documents:", err);
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    setIsLoading(true);
    try {
      const response = await authenticatedFetch("/api/chat/message", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversation_id: currentConversation?.id || null,
          question: input,
          topic: "General",
        }),
      });

      if (response.status === 401) {
        handleUnauthorized();
        return;
      }

      if (response.ok) {
        const data = await response.json();
        setInput("");
        loadConversations();
        // Refresh current conversation
        if (data.conversation_id) {
          const convResponse = await authenticatedFetch(`/api/chat/conversations/${data.conversation_id}`);
          if (convResponse.status === 401) {
            handleUnauthorized();
            return;
          }
          if (convResponse.ok) {
            const convData = await convResponse.json();
            // Parse messages in the conversation
            const parsedConversation = {
              ...convData,
              messages: convData.messages.map(parseMessage)
            };
            setCurrentConversation(parsedConversation);
          }
        }
      }
    } catch (err) {
      console.error("Error sending message:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const uploadFiles = async (files: File[]) => {
    if (!files.length) {
      return;
    }

    setUploadStatus(null);
    setUploadingFile(true);

    let successCount = 0;
    let failureCount = 0;

    for (const file of files) {
      const extension = file.name.split(".").pop()?.toLowerCase() || "";
      if (!ALLOWED_EXTENSIONS.includes(extension)) {
        failureCount += 1;
        continue;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await authenticatedFetch("/api/documents/upload", {
          method: "POST",
          body: formData,
        });

        if (response.status === 401) {
          handleUnauthorized();
          setUploadingFile(false);
          return;
        }

        if (response.status === 413) {
          failureCount += 1;
          setUploadStatus({
            type: "error",
            message: "File is too large. Please upload a smaller file.",
          });
          continue;
        }

        if (response.ok) {
          successCount += 1;
        } else {
          failureCount += 1;
        }
      } catch (err) {
        console.error("Error uploading file:", err);
        failureCount += 1;
      }
    }

    await loadDocuments();

    if (successCount > 0 && failureCount === 0) {
      setUploadStatus({
        type: "success",
        message: `${successCount} file${successCount > 1 ? "s" : ""} uploaded successfully.`,
      });
    } else if (successCount > 0 && failureCount > 0) {
      setUploadStatus({
        type: "error",
        message: `${successCount} uploaded, ${failureCount} failed. Allowed: PDF, TXT, CSV, DOC, DOCX.`,
      });
    } else {
      setUploadStatus({
        type: "error",
        message: "Upload failed. Only PDF, TXT, CSV, DOC, DOCX are supported.",
      });
    }

    setUploadingFile(false);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected: File[] = e.target.files ? Array.from(e.target.files) : [];
    await uploadFiles(selected);
    e.target.value = "";
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (uploadingFile) {
      return;
    }

    const droppedFiles: File[] = Array.from(e.dataTransfer.files || []);
    await uploadFiles(droppedFiles);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!uploadingFile) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDeleteDocument = async (docId: number) => {
    try {
      const response = await authenticatedFetch(`/api/documents/${docId}`, {
        method: "DELETE",
      });

      if (response.status === 401) {
        handleUnauthorized();
        return;
      }

      if (response.ok) {
        loadDocuments();
      }
    } catch (err) {
      console.error("Error deleting document:", err);
    }
  };

  const handleDeleteConversation = async (convId: number) => {
    try {
      const response = await authenticatedFetch(`/api/chat/conversations/${convId}`, {
        method: "DELETE",
      });

      if (response.status === 401) {
        handleUnauthorized();
        return;
      }

      if (response.ok) {
        setCurrentConversation(null);
        loadConversations();
      }
    } catch (err) {
      console.error("Error deleting conversation:", err);
    }
  };

  const startNewConversation = () => {
    setCurrentConversation(null);
    setInput("");
  };

  return (
    <div className="flex h-full bg-slate-900">
      {/* Sidebar */}
      <motion.aside
        animate={{ x: isSidebarOpen ? 0 : -320 }}
        transition={{ duration: 0.3 }}
        className="w-80 bg-slate-800/50 border-r border-slate-700/50 flex flex-col overflow-hidden"
      >
        {/* Sidebar Header */}
        <div className="p-6 border-b border-slate-700/50">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-white">Conversations</h2>
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="lg:hidden p-2 hover:bg-slate-700/30 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-slate-400" />
            </button>
          </div>

          <button
            onClick={startNewConversation}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-700 hover:to-cyan-700 text-white rounded-lg font-semibold transition-all"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {conversations.map((conv) => (
            <motion.button
              key={conv.id}
              onClick={() => setCurrentConversation(conv)}
              className={`w-full text-left px-4 py-3 rounded-lg transition-all truncate ${
                currentConversation?.id === conv.id
                  ? "bg-blue-600/20 border border-blue-500/50 text-blue-200"
                  : "text-slate-300 hover:bg-slate-700/30"
              }`}
            >
              <p className="text-sm font-medium truncate">{conv.title}</p>
              <p className="text-xs text-slate-500 mt-1">
                {new Date(conv.updated_at).toLocaleDateString()}
              </p>
            </motion.button>
          ))}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-slate-700/50 space-y-2">
          <button
            onClick={() => setActiveView(activeView === "chat" ? "documents" : "chat")}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-slate-300 hover:bg-slate-700/30 rounded-lg transition-colors text-sm font-medium"
          >
            <FileText className="w-4 h-4" />
            {activeView === "documents" ? "Back to Chat" : "View Documents"}
          </button>

          <button
            onClick={onLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors text-sm font-medium"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </motion.aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <div className="border-b border-slate-700/50 bg-slate-800/30 p-4 flex items-center justify-between">
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="lg:hidden p-2 hover:bg-slate-700/30 rounded-lg transition-colors"
          >
            <Menu className="w-5 h-5 text-slate-300" />
          </button>
          <h1 className="text-xl font-bold text-white">
            {activeView === "chat" ? "Chat" : "Knowledge Base"}
          </h1>
          <div className="flex items-center gap-4">
            <div className="text-sm text-slate-400">{user?.email}</div>
            <div>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                graphStatus === 'active'
                  ? 'bg-emerald-500/10 text-emerald-300'
                  : graphStatus === 'indexing'
                  ? 'bg-amber-500/10 text-amber-300'
                  : 'bg-slate-700/20 text-slate-400'
              }`}>
                <span className={`w-2 h-2 rounded-full mr-2 ${
                  graphStatus === 'active' ? 'bg-emerald-400' : graphStatus === 'indexing' ? 'bg-amber-400' : 'bg-slate-500'
                }`} />
                {graphStatus === 'active' ? 'Graph Active' : graphStatus === 'indexing' ? 'Graph Indexing' : 'Graph Off'}
              </span>
            </div>
          </div>
        </div>

        {/* Content Area */}
        {activeView === "chat" ? (
          <>
            {/* Messages */}
            <div
              ref={scrollRef}
              className="flex-1 overflow-y-auto p-6 space-y-6"
            >
              {currentConversation && currentConversation.messages.length > 0 ? (
                <AnimatePresence>
                  {currentConversation.messages.map((msg) => (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
                    >
                      <div
                        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                          msg.role === "user"
                            ? "bg-blue-600 text-white"
                            : "bg-slate-700 text-slate-300"
                        }`}
                      >
                        {msg.role === "user" ? (
                          <User className="w-4 h-4" />
                        ) : (
                          <Bot className="w-4 h-4" />
                        )}
                      </div>
                      <div
                        className={`max-w-md px-4 py-3 rounded-lg ${
                          msg.role === "user"
                            ? "bg-blue-600 text-white rounded-tr-none"
                            : "bg-slate-700 text-slate-100 rounded-tl-none"
                        }`}
                      >
                        {msg.role === "assistant" && (
                          <div className="mb-3">
                            <LogicBadge message={msg} />
                          </div>
                        )}
                        <p className="text-sm leading-relaxed">{msg.content}</p>
                        {msg.role === "assistant" && msg.citations && msg.citations.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-slate-600/30">
                            <div className="text-xs text-slate-400 mb-2 font-medium">Sources:</div>
                            <div className="flex flex-wrap">
                              {msg.citations.map((citation, index) => (
                                <SourceNode key={index} citation={citation} index={index} detailedHits={msg.detailed_hits} />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-slate-400">
                  <MessageSquare className="w-12 h-12 mb-4 opacity-50" />
                  <p className="text-lg font-semibold">No messages yet</p>
                  <p className="text-sm">Start a new conversation or select one from the sidebar</p>
                </div>
              )}

              {isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex gap-4"
                >
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-slate-300">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div className="px-4 py-3 bg-slate-700 rounded-lg rounded-tl-none">
                    <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                  </div>
                </motion.div>
              )}
            </div>

            {/* Input Area */}
            <div className="border-t border-slate-700/50 bg-slate-800/30 p-4">
              <div className="max-w-4xl mx-auto flex gap-3">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder="Ask about your documents..."
                  className="flex-1 bg-slate-700/50 border border-slate-600/50 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all resize-none min-h-[48px]"
                  rows={1}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!input.trim() || isLoading}
                  className="flex-shrink-0 p-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white transition-all"
                >
                  {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-4xl">
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-white mb-4">Knowledge Base</h2>
                <div
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                    isDragOver
                      ? "border-blue-400 bg-blue-500/15"
                      : "border-slate-600 hover:border-blue-500 hover:bg-blue-500/5"
                  } ${uploadingFile ? "opacity-70 cursor-wait" : "cursor-pointer"}`}
                  onClick={() => {
                    if (!uploadingFile) {
                      fileInputRef.current?.click();
                    }
                  }}
                >
                  {uploadingFile ? (
                    <Loader2 className="w-8 h-8 text-blue-400 mx-auto mb-3 animate-spin" />
                  ) : (
                    <Upload className="w-8 h-8 text-slate-400 mx-auto mb-3" />
                  )}
                  <p className="text-white font-semibold">
                    {uploadingFile ? "Uploading documents..." : "Drag and drop documents here"}
                  </p>
                  <p className="text-sm text-slate-400">or click to browse files</p>
                  <p className="text-xs text-slate-500 mt-2">Supports multiple files: PDF, TXT, CSV, DOC, DOCX</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleFileUpload}
                    disabled={uploadingFile}
                    className="hidden"
                    accept=".pdf,.txt,.csv,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/csv"
                    multiple
                  />
                </div>

                {uploadStatus && (
                  <div
                    className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
                      uploadStatus.type === "success"
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                        : "border-red-500/40 bg-red-500/10 text-red-300"
                    }`}
                  >
                    {uploadStatus.message}
                  </div>
                )}
              </div>

              {/* Documents List */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-4">
                  Your Documents ({documents.length})
                </h3>
                {documents.length === 0 ? (
                  <p className="text-slate-400 text-center py-8">
                    No documents uploaded yet
                  </p>
                ) : (
                  <div className="space-y-3">
                    {documents.map((doc) => (
                      <motion.div
                        key={doc.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-center justify-between p-4 bg-slate-700/30 border border-slate-600/50 rounded-lg hover:bg-slate-700/50 transition-all"
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <File className="w-5 h-5 text-blue-400 flex-shrink-0" />
                          <div className="min-w-0">
                            <p className="font-semibold text-white truncate">
                              {doc.filename}
                            </p>
                            <p className="text-xs text-slate-400">
                              {getDocumentTypeLabel(doc)} •{" "}
                              {(doc.file_size / 1024).toFixed(2)} KB •{" "}
                              {new Date(doc.uploaded_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => handleDeleteDocument(doc.id)}
                          className="p-2 hover:bg-red-500/20 text-red-400 rounded-lg transition-colors flex-shrink-0"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
