"use client";

import { useEffect, useMemo, useState } from "react";
import { getStoredAuthUser } from "../lib/supabaseAuth";
import {
    AlertTriangle,
    CalendarClock,
    Eye,
    FileText,
    Grid3X3,
    List,
    Loader2,
    RefreshCw,
    Search,
    Sparkles,
    X,
} from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8001";

function parseTimeline(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value;

    if (typeof value === "string") {
        try {
            const parsed = JSON.parse(value);
            return Array.isArray(parsed) ? parsed : [];
        } catch {
            return [];
        }
    }

    return [];
}

function cleanFilename(filename) {
    return (filename || "Untitled.pdf").replace(/^\w{12}-/, "");
}

function documentTitle(document) {
    return document.file_heading || `This is a report for (${cleanFilename(document.filename)})`;
}

function formatBytes(bytes) {
    const size = Number(bytes || 0);
    if (!size) return "Unknown size";

    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
    return `${(size / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

async function fetchDocumentList(ownerEmail) {
    const url = new URL(`${API_BASE_URL}/get-documents`);
    if (ownerEmail) url.searchParams.set("owner_email", ownerEmail);
    const response = await fetch(url);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data?.detail || "Unable to load documents.");
    }

    return Array.isArray(data.documents) ? data.documents : [];
}

async function fetchSemanticDocuments(query, ownerEmail) {
    const response = await fetch(`${API_BASE_URL}/semantic-document-search`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ query, owner_email: ownerEmail }),
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data?.detail || "Unable to search documents.");
    }

    return Array.isArray(data.documents) ? data.documents : [];
}

export default function Documents() {
    const [documents, setDocuments] = useState([]);
    const [selectedDocument, setSelectedDocument] = useState(null);
    const [viewMode, setViewMode] = useState("row");
    const [searchMode, setSearchMode] = useState("normal");
    const [searchQuery, setSearchQuery] = useState("");
    const [semanticDocuments, setSemanticDocuments] = useState([]);
    const [isSemanticLoading, setIsSemanticLoading] = useState(false);
    const [semanticError, setSemanticError] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState("");
    const [previewUrl, setPreviewUrl] = useState("");
    const [ownerEmail] = useState(() => getStoredAuthUser()?.email || "");

    const refreshDocuments = async () => {
        setIsLoading(true);
        setError("");

        try {
            setDocuments(await fetchDocumentList(ownerEmail));
        } catch (fetchError) {
            setError(fetchError.message || "Unable to load documents.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        let isActive = true;

        fetchDocumentList(ownerEmail)
            .then((nextDocuments) => {
                if (isActive) {
                    setDocuments(nextDocuments);
                }
            })
            .catch((fetchError) => {
                if (isActive) {
                    setError(fetchError.message || "Unable to load documents.");
                }
            })
            .finally(() => {
                if (isActive) {
                    setIsLoading(false);
                }
            });

        return () => {
            isActive = false;
        };
    }, [ownerEmail]);

    const filteredDocuments = useMemo(() => {
        if (searchMode === "semantic") {
            return searchQuery.trim() ? semanticDocuments : documents;
        }

        const query = searchQuery.trim().toLowerCase();
        if (!query) return documents;

        return documents.filter((document) => {
            const title = documentTitle(document).toLowerCase();
            const filename = cleanFilename(document.filename).toLowerCase();
            return title.includes(query) || filename.includes(query);
        });
    }, [documents, searchMode, searchQuery, semanticDocuments]);

    const openDocument = (document) => {
        setSelectedDocument(document);
        setPreviewUrl("");
    };

    const closeDocument = () => {
        setSelectedDocument(null);
        setPreviewUrl("");
    };

    const closePreview = () => {
        setPreviewUrl("");
    };

    const handleSearchSubmit = async (event) => {
        event.preventDefault();

        if (searchMode !== "semantic") {
            return;
        }

        const query = searchQuery.trim();
        if (!query) {
            setSemanticDocuments([]);
            setSemanticError("");
            return;
        }

        setIsSemanticLoading(true);
        setSemanticError("");

        try {
            const results = await fetchSemanticDocuments(query, ownerEmail);
            setSemanticDocuments(results);
            setSelectedDocument(results[0] || null);
            setPreviewUrl("");
        } catch (searchError) {
            setSemanticDocuments([]);
            setSemanticError(searchError.message || "Unable to search documents.");
        } finally {
            setIsSemanticLoading(false);
        }
    };

    return (
        <div className="flex h-full min-h-0 w-full overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl">
            <section className="flex min-w-0 flex-1 flex-col">
                <header className="flex flex-col gap-4 border-b border-slate-800 bg-slate-900/70 px-6 py-5">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                            <h2 className="text-lg font-bold text-foreground">Documents</h2>
                            <p className="text-xs text-slate-500">
                                {documents.length} processed document{documents.length === 1 ? "" : "s"} ready
                            </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                            <button
                                type="button"
                                onClick={refreshDocuments}
                                className="flex h-9 items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 text-xs font-semibold text-slate-400 transition hover:border-blue-800 hover:text-blue-400"
                            >
                                <RefreshCw size={14} />
                                Refresh
                            </button>

                            <div className="flex h-9 rounded-lg border border-slate-800 bg-slate-950 p-1">
                                <button
                                    type="button"
                                    title="Row view"
                                    onClick={() => setViewMode("row")}
                                    className={`flex h-7 w-8 items-center justify-center rounded-md transition ${
                                        viewMode === "row"
                                            ? "bg-blue-600 text-white"
                                            : "text-slate-500 hover:text-slate-300"
                                    }`}
                                >
                                    <List size={15} />
                                </button>
                                <button
                                    type="button"
                                    title="Grid view"
                                    onClick={() => setViewMode("grid")}
                                    className={`flex h-7 w-8 items-center justify-center rounded-md transition ${
                                        viewMode === "grid"
                                            ? "bg-blue-600 text-white"
                                            : "text-slate-500 hover:text-slate-300"
                                    }`}
                                >
                                    <Grid3X3 size={14} />
                                </button>
                            </div>
                        </div>
                    </div>

                    <form onSubmit={handleSearchSubmit} className="flex max-w-3xl flex-col gap-2 lg:flex-row lg:items-center">
                        <div className="flex h-10 shrink-0 rounded-lg border border-slate-800 bg-slate-950 p-1">
                            <button
                                type="button"
                                onClick={() => {
                                    setSearchMode("normal");
                                    setSemanticError("");
                                }}
                                className={`flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold transition ${
                                    searchMode === "normal"
                                        ? "bg-blue-600 text-white"
                                        : "text-slate-500 hover:text-slate-300"
                                }`}
                            >
                                <Search size={13} />
                                Normal
                            </button>
                            <button
                                type="button"
                                onClick={() => setSearchMode("semantic")}
                                className={`flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold transition ${
                                    searchMode === "semantic"
                                        ? "bg-blue-600 text-white"
                                        : "text-slate-500 hover:text-slate-300"
                                }`}
                            >
                                <Sparkles size={13} />
                                Semantic
                            </button>
                        </div>

                        <div className="relative min-w-0 flex-1">
                            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                            <input
                                value={searchQuery}
                                onChange={(event) => {
                                    setSearchQuery(event.target.value);
                                    if (searchMode === "normal") {
                                        setSemanticDocuments([]);
                                    }
                                }}
                                placeholder={searchMode === "semantic" ? "Semantic search across document content..." : "Search by heading or filename..."}
                                className="h-10 w-full rounded-lg border border-slate-800 bg-slate-950 px-9 pr-20 text-sm text-slate-200 placeholder-slate-500 outline-none transition focus:border-blue-500"
                            />
                            {searchQuery && (
                                <button
                                    type="button"
                                    onClick={() => {
                                        setSearchQuery("");
                                        setSemanticDocuments([]);
                                        setSemanticError("");
                                    }}
                                    className="absolute right-12 top-1/2 -translate-y-1/2 text-slate-500 transition hover:text-slate-300"
                                >
                                    <X size={14} />
                                </button>
                            )}
                            <button
                                type="submit"
                                disabled={searchMode !== "semantic" || !searchQuery.trim() || isSemanticLoading}
                                className="absolute right-1 top-1/2 flex h-8 w-9 -translate-y-1/2 items-center justify-center rounded-md bg-blue-600 text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
                                title="Run semantic search"
                            >
                                {isSemanticLoading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                            </button>
                        </div>
                    </form>

                    {semanticError && (
                        <p className="text-xs text-red-400">{semanticError}</p>
                    )}
                </header>

                <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                    {isLoading ? (
                        <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-500">
                            <Loader2 size={18} className="animate-spin text-blue-400" />
                            Loading documents...
                        </div>
                    ) : error ? (
                        <div className="flex h-full items-center justify-center">
                            <div className="max-w-sm rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-slate-300">
                                {error}
                            </div>
                        </div>
                    ) : isSemanticLoading ? (
                        <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-500">
                            <Loader2 size={18} className="animate-spin text-blue-400" />
                            Searching document meaning...
                        </div>
                    ) : filteredDocuments.length === 0 ? (
                        <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                            <FileText size={36} className="text-slate-500" />
                            <div>
                                <p className="text-sm font-semibold text-slate-300">
                                    {searchMode === "semantic" && searchQuery.trim()
                                        ? "No semantic matches found"
                                        : "No processed documents found"}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">
                                    {searchMode === "semantic" && searchQuery.trim()
                                        ? "Try a different phrase from the document content."
                                        : "Documents appear here after summarization and vector storage complete."}
                                </p>
                            </div>
                        </div>
                    ) : viewMode === "row" ? (
                        <div className="space-y-2">
                            {filteredDocuments.map((document) => (
                                <DocumentRow
                                    key={document.file_id}
                                    document={document}
                                    isSelected={selectedDocument?.file_id === document.file_id}
                                    onOpen={() => openDocument(document)}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                            {filteredDocuments.map((document) => (
                                <DocumentTile
                                    key={document.file_id}
                                    document={document}
                                    isSelected={selectedDocument?.file_id === document.file_id}
                                    onOpen={() => openDocument(document)}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </section>

            {selectedDocument && (
                <DocumentDetails
                    document={selectedDocument}
                    onPreview={() => setPreviewUrl(selectedDocument.file_url)}
                    onClose={closeDocument}
                />
            )}

            {previewUrl && selectedDocument && (
                <PdfPreviewModal
                    document={selectedDocument}
                    previewUrl={previewUrl}
                    onClose={closePreview}
                />
            )}
        </div>
    );
}

function DocumentRow({ document, isSelected, onOpen }) {
    const deadlines = parseTimeline(document.timeline_json);

    return (
        <button
            type="button"
            onClick={onOpen}
            className={`grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-xl border p-3 text-left transition ${
                isSelected
                    ? "border-blue-500/50 bg-blue-600/10"
                    : "border-slate-800 bg-slate-900/55 hover:border-blue-800/70 hover:bg-slate-900"
            }`}
        >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-800 bg-slate-950 text-blue-400">
                <FileText size={18} />
            </div>

            <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-200">{documentTitle(document)}</p>
                <p className="mt-1 truncate text-xs text-slate-500">
                    {cleanFilename(document.filename)} · {formatBytes(document.file_size)}
                </p>
            </div>

            <div className="flex items-center gap-2">
                {deadlines.length > 0 && (
                    <span className="flex h-8 items-center gap-1.5 rounded-lg border border-yellow-500/50 bg-yellow-500/20 px-2 text-xs font-bold text-[#8A5A00]">
                        <AlertTriangle size={13} />
                        {deadlines.length}
                    </span>
                )}
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-950 text-slate-500">
                    <Eye size={14} />
                </span>
            </div>
        </button>
    );
}

function DocumentTile({ document, isSelected, onOpen }) {
    const deadlines = parseTimeline(document.timeline_json);

    return (
        <button
            type="button"
            onClick={onOpen}
            className={`flex aspect-[4/3] min-h-44 flex-col justify-between rounded-xl border p-4 text-left transition ${
                isSelected
                    ? "border-blue-500/50 bg-blue-600/10"
                    : "border-slate-800 bg-slate-900/55 hover:border-blue-800/70 hover:bg-slate-900"
            }`}
        >
            <div className="flex items-start justify-between gap-3">
                <div className="flex h-20 w-20 items-center justify-center rounded-xl border border-slate-800 bg-slate-950 text-blue-400 shadow-sm">
                    <FileText size={46} strokeWidth={1.6} />
                </div>
                {deadlines.length > 0 && (
                    <span className="flex h-7 items-center gap-1 rounded-lg border border-yellow-500/50 bg-yellow-500/20 px-2 text-xs font-bold text-[#8A5A00]">
                        <AlertTriangle size={12} />
                        {deadlines.length}
                    </span>
                )}
            </div>

            <div className="min-w-0">
                <p className="line-clamp-2 text-sm font-semibold leading-snug text-slate-200">
                    {documentTitle(document)}
                </p>
                <p className="mt-2 truncate text-xs text-slate-500">{cleanFilename(document.filename)}</p>
                <p className="mt-1 text-xs text-slate-600">{formatBytes(document.file_size)}</p>
            </div>
        </button>
    );
}

function DocumentDetails({ document, onPreview, onClose }) {
    const deadlines = parseTimeline(document.timeline_json);

    return (
        <aside className="flex w-[420px] shrink-0 flex-col border-l border-slate-800 bg-slate-900">
            <div className="flex items-start justify-between gap-4 border-b border-slate-800 px-5 py-4">
                <div className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase text-slate-500">Document details</p>
                    <h3 className="mt-1 line-clamp-2 text-base font-bold leading-snug text-slate-200">
                        {documentTitle(document)}
                    </h3>
                    <p className="mt-1 truncate text-xs text-slate-500">{cleanFilename(document.filename)}</p>
                </div>
                <button
                    type="button"
                    title="Close"
                    onClick={onClose}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-800 hover:text-slate-300"
                >
                    <X size={16} />
                </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                {deadlines.length > 0 && (
                    <div className="mb-4 flex items-start gap-2 rounded-xl border border-yellow-500/50 bg-yellow-500/20 px-3 py-2 text-xs font-semibold text-[#8A5A00]">
                        <AlertTriangle size={15} className="mt-0.5 shrink-0 text-yellow-600" />
                        <span>Important deadlines are present in this document.</span>
                    </div>
                )}

                <section>
                    <h4 className="text-xs font-bold uppercase text-slate-500">Summary</h4>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                        {document.summarization || "No summary is available for this document."}
                    </p>
                </section>

                <section className="mt-6">
                    <div className="flex items-center justify-between gap-2">
                        <h4 className="text-xs font-bold uppercase text-slate-500">Important deadlines</h4>
                        <CalendarClock size={15} className="text-blue-400" />
                    </div>

                    {deadlines.length > 0 ? (
                        <ol className="mt-3 space-y-3">
                            {deadlines.map((item, index) => (
                                <li key={`${item.date}-${item.event}-${index}`} className="grid grid-cols-[auto_minmax(0,1fr)] gap-3">
                                    <div className="flex flex-col items-center">
                                        <span className="h-2.5 w-2.5 rounded-full bg-yellow-500" />
                                        {index < deadlines.length - 1 && <span className="mt-1 h-full min-h-10 w-px bg-slate-800" />}
                                    </div>
                                    <div className="pb-1">
                                        <p className="inline-flex rounded-md bg-yellow-500/20 px-2 py-1 text-xs font-bold text-[#8A5A00]">
                                            {item.date || "Date not specified"}
                                        </p>
                                        <p className="mt-1 text-sm leading-5 text-slate-300">{item.event || "Event not specified"}</p>
                                    </div>
                                </li>
                            ))}
                        </ol>
                    ) : (
                        <p className="mt-2 text-sm text-slate-500">No important deadlines were extracted.</p>
                    )}
                </section>

                <section className="mt-6">
                    <button
                        type="button"
                        onClick={onPreview}
                        disabled={!document.file_url}
                        className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-3 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <Eye size={16} />
                        View PDF
                    </button>
                </section>
            </div>
        </aside>
    );
}

function PdfPreviewModal({ document, previewUrl, onClose }) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#413632]/70 p-6 backdrop-blur-sm">
            <div className="flex h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl">
                <div className="flex items-center justify-between gap-4 border-b border-slate-800 bg-slate-900 px-4 py-3">
                    <div className="min-w-0">
                        <p className="truncate text-sm font-bold text-slate-200">{documentTitle(document)}</p>
                        <p className="truncate text-xs text-slate-500">{cleanFilename(document.filename)}</p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-950 text-slate-500 transition hover:bg-slate-800 hover:text-slate-200"
                        title="Close PDF preview"
                    >
                        <X size={18} />
                    </button>
                </div>
                <iframe
                    title={documentTitle(document)}
                    src={previewUrl}
                    className="min-h-0 flex-1 bg-white"
                />
            </div>
        </div>
    );
}
