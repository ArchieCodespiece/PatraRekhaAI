"use client";

import { useState, useRef, useEffect } from "react";
import {
    FileText,
    Send,
    Bot,
    User,
    CheckSquare,
    Square,
    Sparkles,
    Paperclip,
    ChevronDown,
    X,
    Search,
    Loader2,
    MessageSquare,
    AlertCircle,
    Upload,
} from "lucide-react";

// Mock PDF documents
const MOCK_PDFS = [
    { id: "1", name: "PatraRekha_Project_Proposal.pdf", size: "2.4 MB", pages: 18, uploaded: "Jul 20, 2026" },
    { id: "2", name: "Q2_Financial_Report_2026.pdf", size: "5.1 MB", pages: 42, uploaded: "Jul 18, 2026" },
    { id: "3", name: "KMRL_Technical_Specification.pdf", size: "3.8 MB", pages: 67, uploaded: "Jul 15, 2026" },
    { id: "4", name: "AI_Research_Paper_v2.pdf", size: "1.9 MB", pages: 22, uploaded: "Jul 10, 2026" },
    { id: "5", name: "User_Requirements_Document.pdf", size: "4.2 MB", pages: 35, uploaded: "Jul 8, 2026" },
    { id: "6", name: "Infrastructure_Audit_2026.pdf", size: "6.7 MB", pages: 89, uploaded: "Jul 5, 2026" },
    { id: "7", name: "Meeting_Notes_July_Sprint.pdf", size: "0.8 MB", pages: 5, uploaded: "Jul 3, 2026" },
];

// Simulated AI responses
const AI_RESPONSES = [
    "Based on the selected documents, I found relevant information regarding your query. The documents indicate that the project timeline spans across Q3 and Q4 of 2026, with key milestones outlined in the proposal.",
    "According to the financial report, the total budget allocation for Phase 1 is ₹12.4 crore, with a projected ROI of 22% by end of FY2026.",
    "The technical specification document mentions that the system supports REST API integration, with rate limits set at 500 requests/minute per tenant.",
    "From the user requirements document, the top priority features requested include document search, AI summarization, and multi-user collaboration.",
    "I've analyzed all selected documents and identified 3 common themes: (1) Digital transformation, (2) AI integration, and (3) Scalable infrastructure.",
];

export default function ChatWithPDF() {
    const [selectedPDFs, setSelectedPDFs] = useState(new Set());
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [isPanelOpen, setIsPanelOpen] = useState(true);

    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    const filteredPDFs = MOCK_PDFS.filter((pdf) =>
        pdf.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const togglePDF = (id) => {
        setSelectedPDFs((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const toggleAllPDFs = () => {
        if (selectedPDFs.size === MOCK_PDFS.length) {
            setSelectedPDFs(new Set());
        } else {
            setSelectedPDFs(new Set(MOCK_PDFS.map((p) => p.id)));
        }
    };

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async (e) => {
        e?.preventDefault();
        const text = inputValue.trim();
        if (!text || selectedPDFs.size === 0 || isLoading) return;

        const userMsg = {
            id: Date.now(),
            role: "user",
            content: text,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMsg]);
        setInputValue("");
        setIsLoading(true);

        // Simulate AI response delay
        await new Promise((r) => setTimeout(r, 1200 + Math.random() * 800));

        const aiMsg = {
            id: Date.now() + 1,
            role: "assistant",
            content: AI_RESPONSES[Math.floor(Math.random() * AI_RESPONSES.length)],
            timestamp: new Date(),
            sources: [...selectedPDFs].slice(0, 2).map(
                (id) => MOCK_PDFS.find((p) => p.id === id)?.name
            ),
        };
        setMessages((prev) => [...prev, aiMsg]);
        setIsLoading(false);
        inputRef.current?.focus();
    };

    const handleKeyDown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const selectedCount = selectedPDFs.size;
    const canChat = selectedCount > 0;

    return (
        <div className="flex h-full w-full overflow-hidden bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl">

            {/* ── Chat Area ── */}
            <div className="flex flex-1 flex-col min-w-0">
                {/* Chat Header */}
                <div className="flex flex-col gap-2 px-6 py-4 border-b border-slate-800 bg-slate-900/70 backdrop-blur-sm">
                    {/* Row 1: Title + Documents button */}
                    <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400 shrink-0">
                                <Sparkles size={18} />
                            </div>
                            <div className="min-w-0">
                                <h2 className="text-sm font-bold text-foreground">Chat with PDF</h2>
                                <p className="text-[11px] text-slate-400">
                                    {canChat
                                        ? `${selectedCount} document${selectedCount > 1 ? "s" : ""} selected`
                                        : "Select documents to start chatting"}
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={() => setIsPanelOpen(!isPanelOpen)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition shrink-0"
                        >
                            <FileText size={14} />
                            <span className="hidden sm:inline">Documents</span>
                            <ChevronDown
                                size={13}
                                className={`transition-transform ${isPanelOpen ? "rotate-180" : ""}`}
                            />
                        </button>
                    </div>

                    {/* Row 2: Selected PDF chips (only when documents selected) */}
                    {canChat && (
                        <div className="flex flex-wrap items-center gap-1.5 pl-12">
                            {[...selectedPDFs].slice(0, 4).map((id) => {
                                const pdf = MOCK_PDFS.find((p) => p.id === id);
                                return (
                                    <span
                                        key={id}
                                        className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-blue-950/60 border border-blue-800/40 text-blue-400 text-[10px] font-medium max-w-[140px] truncate"
                                    >
                                        <FileText size={9} className="shrink-0" />
                                        <span className="truncate">{pdf?.name.replace(".pdf", "")}</span>
                                    </span>
                                );
                            })}
                            {selectedCount > 4 && (
                                <span className="flex items-center px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 text-[10px] font-medium border border-slate-700">
                                    +{selectedCount - 4} more
                                </span>
                            )}
                        </div>
                    )}
                </div>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    {messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center gap-5 py-16">
                            <div className="relative">
                                <div className="w-20 h-20 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center">
                                    <MessageSquare size={36} className="text-blue-500/60" />
                                </div>
                                <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center">
                                    <Sparkles size={12} className="text-white" />
                                </div>
                            </div>
                            <div>
                                <h3 className="text-base font-semibold text-slate-200">
                                    Ask anything about your documents
                                </h3>
                                <p className="text-sm text-slate-500 mt-1.5 max-w-xs">
                                    Select one or more PDFs from the panel, then type your question below.
                                </p>
                            </div>
                            {!canChat && (
                                <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs">
                                    <AlertCircle size={14} />
                                    No documents selected. Use the panel on the right to select PDFs.
                                </div>
                            )}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-sm w-full">
                                {[
                                    "Summarize the key findings",
                                    "What are the main risks?",
                                    "List all action items",
                                    "Compare the two documents",
                                ].map((prompt) => (
                                    <button
                                        key={prompt}
                                        onClick={() => {
                                            if (canChat) {
                                                setInputValue(prompt);
                                                inputRef.current?.focus();
                                            }
                                        }}
                                        disabled={!canChat}
                                        className="px-3 py-2 text-xs text-slate-400 border border-slate-800 rounded-xl hover:border-blue-800/60 hover:text-blue-400 hover:bg-blue-950/20 transition disabled:opacity-40 disabled:cursor-not-allowed text-left"
                                    >
                                        {prompt}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <>
                            {messages.map((msg) => (
                                <div
                                    key={msg.id}
                                    className={`flex gap-3.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
                                >
                                    {/* Avatar */}
                                    <div
                                        className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
                                            msg.role === "user"
                                                ? "bg-blue-600 text-white"
                                                : "bg-slate-800 border border-slate-700 text-blue-400"
                                        }`}
                                    >
                                        {msg.role === "user" ? <User size={15} /> : <Bot size={15} />}
                                    </div>

                                    {/* Bubble */}
                                    <div className={`max-w-[75%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1.5`}>
                                        <div
                                            className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                                                msg.role === "user"
                                                    ? "bg-blue-600 text-white rounded-tr-sm"
                                                    : "bg-slate-800 border border-slate-700 text-slate-200 rounded-tl-sm"
                                            }`}
                                        >
                                            {msg.content}
                                        </div>
                                        {msg.sources && (
                                            <div className="flex flex-wrap gap-1 mt-1">
                                                <span className="text-[10px] text-slate-600">Sources:</span>
                                                {msg.sources.filter(Boolean).map((src) => (
                                                    <span
                                                        key={src}
                                                        className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 border border-slate-700"
                                                    >
                                                        <FileText size={9} />
                                                        {src?.replace(".pdf", "")}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                        <span className="text-[10px] text-slate-600">
                                            {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                        </span>
                                    </div>
                                </div>
                            ))}
                            {isLoading && (
                                <div className="flex gap-3.5">
                                    <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 text-blue-400 flex items-center justify-center shrink-0">
                                        <Bot size={15} />
                                    </div>
                                    <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-slate-800 border border-slate-700 flex items-center gap-2">
                                        <Loader2 size={14} className="text-blue-400 animate-spin" />
                                        <span className="text-sm text-slate-400">Analyzing documents…</span>
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </>
                    )}
                </div>

                {/* Input Area */}
                <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/50">
                    {!canChat && (
                        <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-amber-500/8 border border-amber-500/15 text-amber-400/80 text-xs">
                            <AlertCircle size={13} />
                            Select at least one PDF document to enable chat.
                        </div>
                    )}
                    <form onSubmit={handleSend} className="flex items-end gap-3">
                        <div className="flex-1 relative">
                            <textarea
                                ref={inputRef}
                                rows={1}
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={handleKeyDown}
                                disabled={!canChat || isLoading}
                                placeholder={
                                    canChat
                                        ? "Ask a question about your documents…"
                                        : "Select documents first to start chatting…"
                                }
                                className="w-full resize-none bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 pr-10 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition disabled:opacity-50 disabled:cursor-not-allowed max-h-32"
                                style={{ minHeight: "48px" }}
                            />
                            <Paperclip size={15} className="absolute right-3 bottom-3.5 text-slate-600" />
                        </div>
                        <button
                            type="submit"
                            disabled={!canChat || !inputValue.trim() || isLoading}
                            className="flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition shadow-lg shadow-blue-950/40 active:scale-95 shrink-0"
                        >
                            {isLoading ? (
                                <Loader2 size={18} className="animate-spin" />
                            ) : (
                                <Send size={18} />
                            )}
                        </button>
                    </form>
                    <p className="text-[10px] text-slate-600 mt-2 text-center">
                        PatraRekhaAI may produce inaccurate information. Verify important details.
                    </p>
                </div>
            </div>

            {/* ── Right Panel: PDF List ── */}
            <div
                className={`shrink-0 border-l border-slate-800 bg-slate-900 flex flex-col transition-all duration-300 overflow-hidden ${
                    isPanelOpen ? "w-72 xl:w-80" : "w-0"
                }`}
            >
                <div className="min-w-[17rem] xl:min-w-[19rem] flex flex-col h-full">
                    {/* Panel Header */}
                    <div className="flex items-center justify-between px-4 py-4 border-b border-slate-800">
                        <div>
                            <h3 className="text-sm font-bold text-foreground">Your Documents</h3>
                            <p className="text-[11px] text-slate-500 mt-0.5">
                                {selectedCount} / {MOCK_PDFS.length} selected
                            </p>
                        </div>
                        <button
                            onClick={toggleAllPDFs}
                            className="text-[11px] font-medium px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                        >
                            {selectedCount === MOCK_PDFS.length ? "Deselect All" : "Select All"}
                        </button>
                    </div>

                    {/* Search */}
                    <div className="px-4 py-3 border-b border-slate-800/60">
                        <div className="relative">
                            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Search documents..."
                                className="w-full bg-slate-800 border border-slate-700/60 rounded-lg pl-8 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
                            />
                            {searchQuery && (
                                <button
                                    onClick={() => setSearchQuery("")}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                                >
                                    <X size={13} />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* PDF List */}
                    <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1.5">
                        {filteredPDFs.length > 0 ? (
                            filteredPDFs.map((pdf) => {
                                const isSelected = selectedPDFs.has(pdf.id);
                                return (
                                    <button
                                        key={pdf.id}
                                        onClick={() => togglePDF(pdf.id)}
                                        className={`w-full flex items-start gap-3 p-3 rounded-xl text-left border transition-all group ${
                                            isSelected
                                                ? "bg-blue-600/10 border-blue-500/40 shadow-sm"
                                                : "bg-slate-800/30 border-slate-800/60 hover:border-slate-700 hover:bg-slate-800/60"
                                        }`}
                                    >
                                        {/* Checkbox */}
                                        <div className={`shrink-0 mt-0.5 transition ${isSelected ? "text-blue-400" : "text-slate-600 group-hover:text-slate-400"}`}>
                                            {isSelected ? <CheckSquare size={17} /> : <Square size={17} />}
                                        </div>

                                        {/* PDF Icon */}
                                        <div className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold border transition ${
                                            isSelected
                                                ? "bg-blue-600/20 border-blue-500/30 text-blue-400"
                                                : "bg-slate-800 border-slate-700 text-slate-500"
                                        }`}>
                                            <FileText size={14} />
                                        </div>

                                        {/* Info */}
                                        <div className="min-w-0 flex-1">
                                            <p className={`text-xs font-medium leading-snug truncate transition ${isSelected ? "text-blue-300" : "text-slate-300 group-hover:text-slate-200"}`}>
                                                {pdf.name}
                                            </p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className="text-[10px] text-slate-600">{pdf.size}</span>
                                                <span className="text-[10px] text-slate-700">·</span>
                                                <span className="text-[10px] text-slate-600">{pdf.pages} pages</span>
                                            </div>
                                            <p className="text-[10px] text-slate-700 mt-0.5">{pdf.uploaded}</p>
                                        </div>
                                    </button>
                                );
                            })
                        ) : (
                            <div className="flex flex-col items-center justify-center py-10 text-center">
                                <Search size={20} className="text-slate-600 mb-2" />
                                <p className="text-xs text-slate-500">No documents found</p>
                            </div>
                        )}
                    </div>

                    {/* Panel Footer */}
                    <div className="px-4 py-3 border-t border-slate-800 bg-slate-950/50">
                        <button className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl border border-dashed border-slate-700 hover:border-blue-600/50 hover:bg-blue-600/5 text-slate-500 hover:text-blue-400 text-xs font-medium transition">
                            <Upload size={14} />
                            Upload New PDF
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
