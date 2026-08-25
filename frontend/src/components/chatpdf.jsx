"use client";

import { useState, useRef, useEffect, useCallback } from "react";

import {
    FileText,
    Send,
    Bot,
    User,
    CheckSquare,
    Square,
    Paperclip,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    X,
    Search,
    Loader2,
    MessageSquare,
    AlertCircle,
    Upload,
    Plus,
    Trash2,
    ExternalLink,
    BookOpen,
} from "lucide-react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
    fetchDocuments,
    authenticatedFetch,
} from "../lib/supabaseAuth";


const MAX_SELECTION = 5;


/* ========================================================================
   HELPERS
   ======================================================================== */

function cleanFilename(filename) {
    return (filename || "Untitled.pdf").replace(
        /^\w{12}-/,
        ""
    );
}


function filenameStem(filename) {
    return cleanFilename(filename).replace(
        /\.[^.]+$/i,
        ""
    );
}


function formatBytes(bytes) {
    const size = Number(bytes || 0);

    if (!size) {
        return "Unknown size";
    }

    const units = [
        "B",
        "KB",
        "MB",
        "GB",
    ];

    const index = Math.min(
        Math.floor(
            Math.log(size) /
            Math.log(1024)
        ),
        units.length - 1
    );

    return `${(
        size /
        1024 ** index
    ).toFixed(
        index === 0 ? 0 : 1
    )} ${units[index]}`;
}


function formatDate(value) {
    if (!value) {
        return "Unknown date";
    }

    const date = new Date(value);

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return "Unknown date";
    }

    return date.toLocaleDateString(
        "en-US",
        {
            month: "short",
            day: "numeric",
            year: "numeric",
        }
    );
}


function formatMessageTime(value) {
    if (!value) {
        return "";
    }

    const date = new Date(value);

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return "";
    }

    return date.toLocaleTimeString(
        [],
        {
            hour: "2-digit",
            minute: "2-digit",
        }
    );
}


function normalizeDocument(document) {
    const name = filenameStem(
        document.filename
    );

    return {
        id: String(
            document.file_id
        ),

        name,

        label:
            document.file_heading ||
            name,

        filename:
            cleanFilename(
                document.filename
            ),

        size:
            formatBytes(
                document.file_size
            ),

        uploaded:
            formatDate(
                document.uploaded_at ||
                document.created_at
            ),
    };
}


function normalizeMessage(message) {
    const rawSources = Array.isArray(message.sources)
        ? message.sources
        : [];
    const rawCitations = Array.isArray(message.citations)
        ? message.citations
        : [];

    const citations = rawCitations.map((c) => ({
        document_name: c.document_name || "",
        file_id: c.file_id || "",
        page_start: c.page_start ?? null,
        page_end: c.page_end ?? null,
        section: c.section || "",
        text: c.text || "",
        score: typeof c.score === "number" ? c.score : 0,
    }));

    const sources = citations.length > 0
        ? citations.map((c) => c.document_name).filter(Boolean)
        : rawSources;

    return {
        id: message.id,
        role: message.role,
        content: message.content,
        timestamp: new Date(message.created_at),
        sources,
        citations,
    };
}


/* ========================================================================
   COMPONENT
   ======================================================================== */

export default function ChatWithPDF() {

    /* --------------------------------------------------------------------
       Documents
    -------------------------------------------------------------------- */

    const [
        selectedPDFs,
        setSelectedPDFs,
    ] = useState(
        new Set()
    );

    const [
        documents,
        setDocuments,
    ] = useState([]);

    const [
        isDocumentsLoading,
        setIsDocumentsLoading,
    ] = useState(true);

    const [
        documentsError,
        setDocumentsError,
    ] = useState("");

    const [
        searchQuery,
        setSearchQuery,
    ] = useState("");

    const [
        isPanelOpen,
        setIsPanelOpen,
    ] = useState(true);


    /* --------------------------------------------------------------------
       Chat
    -------------------------------------------------------------------- */

    const [
        messages,
        setMessages,
    ] = useState([]);

    const [
        inputValue,
        setInputValue,
    ] = useState("");

    const [
        isLoading,
        setIsLoading,
    ] = useState(false);


    /* --------------------------------------------------------------------
       Conversation history
    -------------------------------------------------------------------- */

    const [
        conversations,
        setConversations,
    ] = useState([]);

    const [
        currentConversationId,
        setCurrentConversationId,
    ] = useState(null);

    const [
        isHistoryLoading,
        setIsHistoryLoading,
    ] = useState(false);

    const [
        isHistoryOpen,
        setIsHistoryOpen,
    ] = useState(true);


    /* --------------------------------------------------------------------
       Refs
    -------------------------------------------------------------------- */

    const messagesEndRef =
        useRef(null);

    const inputRef =
        useRef(null);


    /* --------------------------------------------------------------------
       Citation preview
    -------------------------------------------------------------------- */

    const [
        previewDocument,
        setPreviewDocument,
    ] = useState(null);

    const [
        previewUrl,
        setPreviewUrl,
    ] = useState("");

    const [
        previewPage,
        setPreviewPage,
    ] = useState(null);

    const [
        previewText,
        setPreviewText,
    ] = useState("");

    const [
        isPreviewLoading,
        setIsPreviewLoading,
    ] = useState(false);


    const openCitation =
        useCallback(
            async (citation) => {
                if (!citation) {
                    return;
                }

                const fileId =
                    citation.file_id ||
                    (citation.document_name &&
                        documents.find(
                            (d) =>
                                d.name ===
                                citation.document_name
                        )?.id);

                if (!fileId) {
                    return;
                }

                setIsPreviewLoading(
                    true
                );
                setPreviewText(
                    citation.text ||
                    ""
                );
                setPreviewPage(
                    citation.page_start ||
                    null
                );

                try {
                    const localDocument =
                        documents.find(
                            (d) =>
                                d.id ===
                                fileId
                        );

                    if (
                        localDocument?.file_url
                    ) {
                        setPreviewDocument(
                            localDocument
                        );
                        setPreviewUrl(
                            localDocument.file_url
                        );
                    } else {
                        const response =
                            await authenticatedFetch(
                                `/get-documents/${encodeURIComponent(
                                    fileId
                                )}`
                            );

                        const data =
                            await response.json();

                        if (
                            !response.ok
                        ) {
                            throw new Error(
                                data?.detail ||
                                    "Unable to load document."
                            );
                        }

                        setPreviewDocument(
                            {
                                file_id:
                                    fileId,
                                filename:
                                    citation.document_name,
                            }
                        );
                        setPreviewUrl(
                            data?.file_url ||
                            ""
                        );
                    }
                } catch {
                    setPreviewDocument(
                        null
                    );
                    setPreviewUrl("");
                } finally {
                    setIsPreviewLoading(
                        false
                    );
                }
            },
            [documents]
        );

    const closePreview =
        useCallback(() => {
            setPreviewDocument(
                null
            );
            setPreviewUrl("");
            setPreviewPage(null);
            setPreviewText("");
        }, []);


    /* ====================================================================
       FILTER DOCUMENTS
    ==================================================================== */

    const filteredPDFs =
        documents.filter(
            (pdf) =>
                `${pdf.label} ${pdf.name} ${pdf.filename}`
                    .toLowerCase()
                    .includes(
                        searchQuery.toLowerCase()
                    )
        );


    /* ====================================================================
       LOAD DOCUMENTS
       ==================================================================== */

    useEffect(() => {

        let isActive = true;

        async function loadDocuments() {

            try {

                setIsDocumentsLoading(
                    true
                );

                setDocumentsError("");

                const data =
                    await fetchDocuments();

                const nextDocuments =
                    Array.isArray(
                        data?.documents
                    )
                        ? data.documents.map(
                            normalizeDocument
                        )
                        : [];

                if (isActive) {
                    setDocuments(
                        nextDocuments
                    );
                }

            } catch (error) {

                if (isActive) {

                    setDocumentsError(
                        error?.message ||
                        "Unable to load documents."
                    );

                }

            } finally {

                if (isActive) {

                    setIsDocumentsLoading(
                        false
                    );

                }

            }
        }

        loadDocuments();

        return () => {
            isActive = false;
        };

    }, []);


    /* ====================================================================
       LOAD CONVERSATIONS
       ==================================================================== */

    const loadConversations =
        async () => {

            try {

                setIsHistoryLoading(
                    true
                );

                const response =
                    await authenticatedFetch(
                        "/conversations",
                        {
                            method: "GET",
                        }
                    );

                const data =
                    await response.json();

                if (!response.ok) {

                    throw new Error(
                        data?.detail ||
                        "Unable to load chat history."
                    );

                }

                setConversations(
                    Array.isArray(
                        data?.conversations
                    )
                        ? data.conversations
                        : []
                );

            } catch (error) {

                console.error(
                    "Conversation history error:",
                    error
                );

            } finally {

                setIsHistoryLoading(
                    false
                );

            }
        };


    useEffect(() => {

        loadConversations();

    }, []);


    /* ====================================================================
       SCROLL CHAT
       ==================================================================== */

    useEffect(() => {

        messagesEndRef.current?.scrollIntoView(
            {
                behavior: "smooth",
            }
        );

    }, [messages]);


    /* ====================================================================
       SELECT PDF
       ==================================================================== */

    const togglePDF = (id) => {

        setSelectedPDFs(
            (previous) => {

                const next =
                    new Set(previous);

                if (
                    next.has(id)
                ) {

                    next.delete(id);

                    return next;
                }

                if (
                    next.size >=
                    MAX_SELECTION
                ) {

                    return previous;
                }

                next.add(id);

                return next;
            }
        );
    };


    /* ====================================================================
       SELECT ALL
       ==================================================================== */

    const toggleAllPDFs = () => {

        const selectableIds =
            documents
                .slice(
                    0,
                    MAX_SELECTION
                )
                .map(
                    (pdf) => pdf.id
                );

        const selectedCount =
            selectableIds.filter(
                (id) =>
                    selectedPDFs.has(
                        id
                    )
            ).length;

        if (
            selectedCount ===
            selectableIds.length
        ) {

            setSelectedPDFs(
                new Set()
            );

        } else {

            setSelectedPDFs(
                new Set(
                    selectableIds
                )
            );

        }
    };


    /* ====================================================================
       NEW CHAT
       ==================================================================== */

    const handleNewChat = () => {

        setMessages([]);

        setInputValue("");

        setCurrentConversationId(
            null
        );

        setSelectedPDFs(
            new Set()
        );

        inputRef.current?.focus();
    };


    /* ====================================================================
       OPEN CONVERSATION
       ==================================================================== */

    const openConversation =
        async (
            conversationId
        ) => {

            if (
                conversationId ===
                currentConversationId
            ) {
                return;
            }

            try {

                setIsHistoryLoading(
                    true
                );

                const response =
                    await authenticatedFetch(
                        `/conversations/${conversationId}`,
                        {
                            method: "GET",
                        }
                    );

                const data =
                    await response.json();

                if (!response.ok) {

                    throw new Error(
                        data?.detail ||
                        "Unable to open conversation."
                    );

                }

                const conversation =
                    data?.conversation;

                const loadedMessages =
                    Array.isArray(
                        data?.messages
                    )
                        ? data.messages.map(
                            normalizeMessage
                        )
                        : [];

                setCurrentConversationId(
                    conversation?.id ||
                    conversationId
                );

                setMessages(
                    loadedMessages
                );

                /*
                 * Restore selected PDFs.
                 *
                 * We stored document names,
                 * not IDs.
                 *
                 * Match them against the
                 * currently loaded documents.
                 */

                const storedDocuments =
                    Array.isArray(
                        conversation?.selected_documents
                    )
                        ? conversation.selected_documents
                        : [];

                const matchingIds =
                    documents
                        .filter(
                            (document) =>
                                storedDocuments.includes(
                                    document.name
                                ) ||
                                storedDocuments.includes(
                                    document.filename
                                ) ||
                                storedDocuments.includes(
                                    document.label
                                )
                        )
                        .slice(
                            0,
                            MAX_SELECTION
                        )
                        .map(
                            (document) =>
                                document.id
                        );

                setSelectedPDFs(
                    new Set(
                        matchingIds
                    )
                );

                setInputValue("");

            } catch (error) {

                console.error(
                    "Open conversation error:",
                    error
                );

            } finally {

                setIsHistoryLoading(
                    false
                );

                inputRef.current?.focus();
            }
        };


    /* ====================================================================
       DELETE CONVERSATION
       ==================================================================== */

    const deleteConversation =
        async (
            event,
            conversationId
        ) => {

            event.stopPropagation();

            try {

                const response =
                    await authenticatedFetch(
                        `/conversations/${conversationId}`,
                        {
                            method: "DELETE",
                        }
                    );

                const data =
                    await response.json();

                if (!response.ok) {

                    throw new Error(
                        data?.detail ||
                        "Unable to delete conversation."
                    );

                }

                setConversations(
                    (previous) =>
                        previous.filter(
                            (conversation) =>
                                conversation.id !==
                                conversationId
                        )
                );

                if (
                    currentConversationId ===
                    conversationId
                ) {

                    handleNewChat();
                }

            } catch (error) {

                console.error(
                    "Delete conversation error:",
                    error
                );
            }
        };


    /* ====================================================================
       SEND CHAT
       ==================================================================== */

    const handleSend =
        async (event) => {

            event?.preventDefault();

            const text =
                inputValue.trim();

            if (
                !text ||
                selectedPDFs.size === 0 ||
                isLoading
            ) {
                return;
            }

            const temporaryId =
                `temp-${Date.now()}`;

            const userMessage = {

                id:
                    temporaryId,

                role:
                    "user",

                content:
                    text,

                timestamp:
                    new Date(),

                sources:
                    [],
            };

            setMessages(
                (previous) => [
                    ...previous,
                    userMessage,
                ]
            );

            setInputValue("");

            setIsLoading(true);

            try {

                const selectedDocumentNames =
                    [...selectedPDFs]
                        .map(
                            (id) =>
                                documents.find(
                                    (pdf) =>
                                        pdf.id ===
                                        id
                                )?.name
                        )
                        .filter(Boolean);


                const response =
                    await authenticatedFetch(
                        "/chat",
                        {
                            method: "POST",

                            body:
                                JSON.stringify(
                                    {
                                        query:
                                            text,

                                        selected_documents:
                                            selectedDocumentNames,

                                        conversation_id:
                                            currentConversationId,
                                    }
                                ),
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data?.detail ||
                        "Unable to get a response from the server."
                    );

                }


                /* --------------------------------------------------------
                   Store conversation ID
                -------------------------------------------------------- */

                if (
                    data?.conversation_id &&
                    !currentConversationId
                ) {

                    setCurrentConversationId(
                        data.conversation_id
                    );

                }


                /* --------------------------------------------------------
                   AI message
                -------------------------------------------------------- */

                const aiMessage = {

                    id:
                        `assistant-${Date.now()}`,

                    role:
                        "assistant",

                    content:
                        data?.answer ||
                        "I couldn't generate a response.",

                    timestamp:
                        new Date(),

                    sources:
                        Array.isArray(
                            data?.sources
                        )
                            ? data.sources
                            : [],

                    citations:
                        Array.isArray(
                            data?.citations
                        )
                            ? data.citations
                            : [],
                };


                setMessages(
                    (previous) => [

                        ...previous,

                        aiMessage,

                    ]
                );


                /* --------------------------------------------------------
                   Refresh sidebar
                -------------------------------------------------------- */

                await loadConversations();

            } catch (error) {

                const errorMessage = {

                    id:
                        `error-${Date.now()}`,

                    role:
                        "assistant",

                    content:
                        error?.message ||
                        "Something went wrong while contacting the API.",

                    timestamp:
                        new Date(),

                    sources:
                        [],
                };

                setMessages(
                    (previous) => [
                        ...previous,
                        errorMessage,
                    ]
                );

            } finally {

                setIsLoading(
                    false
                );

                inputRef.current?.focus();
            }
        };


    /* ====================================================================
       ENTER
       ==================================================================== */

    const handleKeyDown =
        (event) => {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                handleSend();
            }
        };


    /* ====================================================================
       VALUES
       ==================================================================== */

    const selectedCount =
        selectedPDFs.size;

    const canChat =
        selectedCount > 0;


    /* ====================================================================
       UI
       ==================================================================== */

    return (

        <div className="flex h-full w-full overflow-hidden bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl">


            {/* ============================================================
               RECENT CHATS
            ============================================================ */}

            <div
                className={`
                    shrink-0
                    border-r
                    border-slate-800
                    bg-slate-900
                    flex
                    flex-col
                    transition-all
                    duration-300
                    overflow-hidden

                    ${
                        isHistoryOpen
                            ? "w-64"
                            : "w-0"
                    }
                `}
            >

                <div className="min-w-[16rem] flex flex-col h-full">


                    {/* Header */}

                    <div className="px-4 py-4 border-b border-slate-800">

                        <div className="flex items-center justify-between">

                            <div>

                                <h3 className="text-sm font-bold text-slate-200">
                                    Recent Chats
                                </h3>

                                <p className="text-[10px] text-slate-500 mt-0.5">
                                    Your conversation history
                                </p>

                            </div>

                            <button
                                onClick={() =>
                                    setIsHistoryOpen(
                                        false
                                    )
                                }
                                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300"
                            >

                                <ChevronLeft
                                    size={15}
                                />

                            </button>

                        </div>


                        {/* New chat */}

                        <button
                            onClick={
                                handleNewChat
                            }
                            className="w-full mt-4 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition"
                        >

                            <Plus
                                size={14}
                            />

                            New Chat

                        </button>

                    </div>


                    {/* Conversations */}

                    <div className="flex-1 overflow-y-auto px-2 py-3">

                        {isHistoryLoading &&
                        conversations.length === 0 ? (

                            <div className="flex items-center justify-center gap-2 py-10 text-xs text-slate-500">

                                <Loader2
                                    size={14}
                                    className="animate-spin"
                                />

                                Loading chats...

                            </div>

                        ) : conversations.length === 0 ? (

                            <div className="flex flex-col items-center justify-center text-center py-10 px-4">

                                <MessageSquare
                                    size={22}
                                    className="text-slate-700 mb-2"
                                />

                                <p className="text-xs text-slate-500">
                                    No conversations yet
                                </p>

                                <p className="text-[10px] text-slate-700 mt-1">
                                    Start a new chat to see it here.
                                </p>

                            </div>

                        ) : (

                            <div className="space-y-1">

                                {conversations.map(
                                    (
                                        conversation
                                    ) => {

                                        const active =
                                            conversation.id ===
                                            currentConversationId;

                                        return (

                                            <button
                                                key={
                                                    conversation.id
                                                }
                                                onClick={() =>
                                                    openConversation(
                                                        conversation.id
                                                    )
                                                }
                                                className={`
                                                    w-full
                                                    group
                                                    flex
                                                    items-center
                                                    gap-2
                                                    text-left
                                                    px-3
                                                    py-2.5
                                                    rounded-xl
                                                    transition

                                                    ${
                                                        active
                                                            ? "bg-blue-600/15 border border-blue-500/30"
                                                            : "border border-transparent hover:bg-slate-800"
                                                    }
                                                `}
                                            >

                                                <MessageSquare
                                                    size={14}
                                                    className={`
                                                        shrink-0

                                                        ${
                                                            active
                                                                ? "text-blue-400"
                                                                : "text-slate-600"
                                                        }
                                                    `}
                                                />


                                                <div className="min-w-0 flex-1">

                                                    <p
                                                        className={`
                                                            text-xs
                                                            font-medium
                                                            truncate

                                                            ${
                                                                active
                                                                    ? "text-blue-300"
                                                                    : "text-slate-300"
                                                            }
                                                        `}
                                                    >
                                                        {
                                                            conversation.title
                                                        }
                                                    </p>

                                                    <p className="text-[9px] text-slate-600 mt-0.5">
                                                        {formatDate(
                                                            conversation.updated_at
                                                        )}
                                                    </p>

                                                </div>


                                                <span
                                                    role="button"
                                                    tabIndex={0}
                                                    onClick={(
                                                        event
                                                    ) =>
                                                        deleteConversation(
                                                            event,
                                                            conversation.id
                                                        )
                                                    }
                                                    className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-500/10 text-slate-600 hover:text-red-400 transition"
                                                >

                                                    <Trash2
                                                        size={12}
                                                    />

                                                </span>

                                            </button>

                                        );
                                    }
                                )}

                            </div>

                        )}

                    </div>

                </div>

            </div>


            {/* ============================================================
               CHAT AREA
            ============================================================ */}

            <div className="flex flex-1 flex-col min-w-0">


                {/* Header */}

                <div className="flex flex-col gap-2 px-6 py-4 border-b border-slate-800 bg-slate-900/70">

                    <div className="flex items-center justify-between gap-3">

                        <div className="flex items-center gap-3 min-w-0">

                            {!isHistoryOpen && (

                                <button
                                    onClick={() =>
                                        setIsHistoryOpen(
                                            true
                                        )
                                    }
                                    className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400"
                                >

                                    <ChevronRight
                                        size={16}
                                    />

                                </button>

                            )}


                            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/30 text-blue-400 shrink-0">

                                <MessageSquare
                                    size={18}
                                />

                            </div>


                            <div className="min-w-0">

                                <h2 className="text-sm font-bold text-foreground">
                                    Chat with PDF
                                </h2>

                                <p className="text-[11px] text-slate-400">

                                    {canChat
                                        ? `${selectedCount} document${
                                            selectedCount >
                                            1
                                                ? "s"
                                                : ""
                                        } selected`

                                        : "Select documents to start chatting"}

                                </p>

                            </div>

                        </div>


                        <button
                            onClick={() =>
                                setIsPanelOpen(
                                    !isPanelOpen
                                )
                            }
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition shrink-0"
                        >

                            <FileText
                                size={14}
                            />

                            <span className="hidden sm:inline">
                                Documents
                            </span>

                            <ChevronDown
                                size={13}
                                className={`
                                    transition-transform

                                    ${
                                        isPanelOpen
                                            ? "rotate-180"
                                            : ""
                                    }
                                `}
                            />

                        </button>

                    </div>


                    {/* Selected documents */}

                    {canChat && (

                        <div className="flex flex-wrap items-center gap-1.5 pl-12">

                            {[...selectedPDFs]
                                .slice(0, 4)
                                .map(
                                    (id) => {

                                        const pdf =
                                            documents.find(
                                                (item) =>
                                                    item.id ===
                                                    id
                                            );

                                        return (

                                            <span
                                                key={
                                                    id
                                                }
                                                className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-blue-950/60 border border-blue-800/40 text-blue-400 text-[10px] font-medium max-w-[140px] truncate"
                                            >

                                                <FileText
                                                    size={9}
                                                    className="shrink-0"
                                                />

                                                <span className="truncate">
                                                    {
                                                        pdf?.label ||
                                                        pdf?.name
                                                    }
                                                </span>

                                            </span>

                                        );
                                    }
                                )}

                            {selectedCount > 4 && (

                                <span className="flex items-center px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 text-[10px] font-medium border border-slate-700">

                                    +
                                    {selectedCount - 4}
                                    {" "}
                                    more

                                </span>

                            )}

                        </div>

                    )}

                </div>


                {/* ========================================================
                   MESSAGES
                ======================================================== */}

                <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">

                    {messages.length === 0 ? (

                        <div className="flex flex-col items-center justify-center h-full text-center gap-5 py-16">

                            <div className="w-20 h-20 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center">

                                <MessageSquare
                                    size={36}
                                    className="text-blue-500/60"
                                />

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

                                    <AlertCircle
                                        size={14}
                                    />

                                    No documents selected.

                                </div>

                            )}


                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-sm w-full">

                                {[
                                    "Summarize the key findings",
                                    "What are the main risks?",
                                    "List all action items",
                                    "Compare the two documents",
                                ].map(
                                    (
                                        prompt
                                    ) => (

                                        <button
                                            key={
                                                prompt
                                            }
                                            onClick={() => {

                                                if (
                                                    canChat
                                                ) {

                                                    setInputValue(
                                                        prompt
                                                    );

                                                    inputRef.current?.focus();

                                                }

                                            }}
                                            disabled={
                                                !canChat
                                            }
                                            className="px-3 py-2 text-xs text-slate-400 border border-slate-800 rounded-xl hover:border-blue-800/60 hover:text-blue-400 hover:bg-blue-950/20 transition disabled:opacity-40 disabled:cursor-not-allowed text-left"
                                        >
                                            {
                                                prompt
                                            }
                                        </button>

                                    )
                                )}

                            </div>

                        </div>

                    ) : (

                        <>

                            {messages.map(
                                (
                                    message
                                ) => (

                                    <div
                                        key={
                                            message.id
                                        }
                                        className={`
                                            flex
                                            gap-3.5

                                            ${
                                                message.role ===
                                                "user"
                                                    ? "flex-row-reverse"
                                                    : ""
                                            }
                                        `}
                                    >

                                        <div
                                            className={`
                                                w-8
                                                h-8
                                                rounded-xl
                                                flex
                                                items-center
                                                justify-center
                                                shrink-0

                                                ${
                                                    message.role ===
                                                    "user"
                                                        ? "bg-blue-600 text-white"
                                                        : "bg-slate-800 border border-slate-700 text-blue-400"
                                                }
                                            `}
                                        >

                                            {message.role ===
                                            "user" ? (

                                                <User
                                                    size={15}
                                                />

                                            ) : (

                                                <Bot
                                                    size={15}
                                                />

                                            )}

                                        </div>


                                        <div
                                            className={`
                                                max-w-[75%]
                                                flex
                                                flex-col
                                                gap-1.5

                                                ${
                                                    message.role ===
                                                    "user"
                                                        ? "items-end"
                                                        : "items-start"
                                                }
                                            `}
                                        >

                                            <div
                                                className={`
                                                    px-4
                                                    py-3
                                                    rounded-2xl
                                                    text-sm
                                                    leading-relaxed
                                                    
                                                    ${
                                                        message.role ===
                                                        "user"
                                                            ? "bg-blue-600 text-white rounded-tr-sm"
                                                            : "bg-slate-800 border border-slate-700 text-slate-200 rounded-tl-sm"
                                                    }
                                                `}
                                            >
                                                <ReactMarkdown
                                                    remarkPlugins={[
                                                        remarkGfm,
                                                    ]}
                                                    components={{
                                                        table: ({
                                                            children,
                                                        }) => (
                                                            <div className="overflow-x-auto my-2 -mx-1">
                                                                <table className="min-w-full border-collapse text-xs">
                                                                    {children}
                                                                </table>
                                                            </div>
                                                        ),
                                                        th: ({
                                                            children,
                                                        }) => (
                                                            <th className="border border-slate-600 px-2 py-1 bg-slate-700 text-slate-200 text-left font-semibold">
                                                                {children}
                                                            </th>
                                                        ),
                                                        td: ({
                                                            children,
                                                        }) => (
                                                            <td className="border border-slate-600 px-2 py-1 text-slate-300">
                                                                {children}
                                                            </td>
                                                        ),
                                                        ul: ({
                                                            children,
                                                        }) => (
                                                            <ul className="list-disc list-inside space-y-1 my-2">
                                                                {children}
                                                            </ul>
                                                        ),
                                                        ol: ({
                                                            children,
                                                        }) => (
                                                            <ol className="list-decimal list-inside space-y-1 my-2">
                                                                {children}
                                                            </ol>
                                                        ),
                                                        p: ({
                                                            children,
                                                        }) => (
                                                            <p className="mb-2 last:mb-0">
                                                                {children}
                                                            </p>
                                                        ),
                                                        h1: ({
                                                            children,
                                                        }) => (
                                                            <h1 className="text-lg font-bold mt-4 mb-2 text-slate-100">
                                                                {children}
                                                            </h1>
                                                        ),
                                                        h2: ({
                                                            children,
                                                        }) => (
                                                            <h2 className="text-base font-bold mt-3 mb-2 text-slate-100">
                                                                {children}
                                                            </h2>
                                                        ),
                                                        h3: ({
                                                            children,
                                                        }) => (
                                                            <h3 className="text-sm font-semibold mt-2 mb-1 text-slate-200">
                                                                {children}
                                                            </h3>
                                                        ),
                                                        strong: ({
                                                            children,
                                                        }) => (
                                                            <strong className="font-semibold text-slate-100">
                                                                {children}
                                                            </strong>
                                                        ),
                                                        a: ({
                                                            href,
                                                            children,
                                                        }) => (
                                                            <a
                                                                href={href}
                                                                className="text-blue-400 underline"
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                            >
                                                                {children}
                                                            </a>
                                                        ),
                                                        code: ({
                                                            inline,
                                                            children,
                                                        }) =>
                                                            inline ? (
                                                                <code className="bg-slate-700 px-1 py-0.5 rounded text-blue-300 text-xs">
                                                                    {children}
                                                                </code>
                                                            ) : (
                                                                <code className="block bg-slate-900 p-3 rounded-lg text-slate-300 text-xs overflow-x-auto my-2">
                                                                    {children}
                                                                </code>
                                                            ),
                                                    }}
                                                >
                                                    {message.content}
                                                </ReactMarkdown>
                                            </div>


                                            {((message.citations &&
                                                message.citations.length >
                                                0) ||
                                                (message.sources &&
                                                    message.sources
                                                        .length >
                                                    0)) && (
                                                <div className="flex flex-wrap gap-1.5 mt-1.5">
                                                    <span className="text-[10px] text-slate-600 self-center mr-1">
                                                        Sources:
                                                    </span>

                                                    {message.citations &&
                                                        message.citations
                                                            .length >
                                                        0
                                                        ? message.citations
                                                              .filter(
                                                                  (c) =>
                                                                      c
                                                                          .document_name
                                                              )
                                                              .map(
                                                                  (
                                                                      citation,
                                                                      idx
                                                                  ) => {
                                                                      const pageLabel =
                                                                          citation.page_start &&
                                                                          citation.page_end
                                                                              ? citation.page_start ===
                                                                                citation.page_end
                                                                                  ? `Page ${citation.page_start}`
                                                                                  : `Pages ${citation.page_start}-${citation.page_end}`
                                                                              : citation.page_start
                                                                                ? `Page ${citation.page_start}`
                                                                                : null;

                                                                      return (
                                                                          <button
                                                                              key={
                                                                                  `${message.id}-citation-${idx}`
                                                                              }
                                                                              onClick={
                                                                                  () =>
                                                                                      openCitation(
                                                                                          citation
                                                                                      )
                                                                              }
                                                                              className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 border border-slate-700 hover:border-blue-500/50 hover:text-blue-300 transition cursor-pointer text-left"
                                                                          >
                                                                              <FileText
                                                                                  size={
                                                                                      9
                                                                                  }
                                                                              />

                                                                              <span className="truncate max-w-[140px]">
                                                                               {citation.document_name.replace(
                                                                                   /\.[^.]+$/i,
                                                                                   ""
                                                                               )}
                                                                              </span>

                                                                              {pageLabel && (
                                                                                  <span className="text-slate-500">
                                                                                      ·
                                                                                      {pageLabel}
                                                                                  </span>
                                                                              )}

                                                                              {citation.section && (
                                                                                  <span className="text-slate-500 truncate max-w-[100px]">
                                                                                      ·
                                                                                      {citation.section}
                                                                                  </span>
                                                                              )}

                                                                              <ExternalLink
                                                                                  size={
                                                                                      8
                                                                                  }
                                                                                  className="shrink-0 text-slate-500"
                                                                              />
                                                                          </button>
                                                                      );
                                                                  }
                                                              )
                                                        : message.sources
                                                              .filter(
                                                                  Boolean
                                                              )
                                                              .filter(
                                                                  (
                                                                      src,
                                                                      index,
                                                                      array
                                                                  ) =>
                                                                      array
                                                                          .indexOf(
                                                                              src
                                                                          ) ===
                                                                      index
                                                              )
                                                              .map(
                                                                  (src) => (
                                                                      <span
                                                                          key={`${message.id}-${src}`}
                                                                          className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 border border-slate-700"
                                                                      >
                                                                          <FileText
                                                                              size={
                                                                                  9
                                                                              }
                                                                          />

                                                                           {src.replace(
                                                                               /\.[^.]+$/i,
                                                                               ""
                                                                           )}
                                                                      </span>
                                                                  )
                                                              )}
                                                </div>
                                            )}


                                            <span className="text-[10px] text-slate-600">

                                                {formatMessageTime(
                                                    message.timestamp
                                                )}

                                            </span>

                                        </div>

                                    </div>

                                )
                            )}


                            {isLoading && (

                                <div className="flex gap-3.5">

                                    <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 text-blue-400 flex items-center justify-center shrink-0">

                                        <Bot
                                            size={15}
                                        />

                                    </div>


                                    <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-slate-800 border border-slate-700 flex items-center gap-2">

                                        <Loader2
                                            size={14}
                                            className="text-blue-400 animate-spin"
                                        />

                                        <span className="text-sm text-slate-400">
                                            Analyzing documents…
                                        </span>

                                    </div>

                                </div>

                            )}


                            <div
                                ref={
                                    messagesEndRef
                                }
                            />

                        </>

                    )}

                </div>


                {/* ========================================================
                   INPUT
                ======================================================== */}

                <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/50">

                    {!canChat && (

                        <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-amber-500/8 border border-amber-500/15 text-amber-400/80 text-xs">

                            <AlertCircle
                                size={13}
                            />

                            Select at least one PDF document to enable chat.

                        </div>

                    )}


                    <form
                        onSubmit={
                            handleSend
                        }
                        className="flex items-end gap-3"
                    >

                        <div className="flex-1 relative">

                            <textarea
                                ref={
                                    inputRef
                                }
                                rows={1}
                                value={
                                    inputValue
                                }
                                onChange={(
                                    event
                                ) =>
                                    setInputValue(
                                        event.target.value
                                    )
                                }
                                onKeyDown={
                                    handleKeyDown
                                }
                                disabled={
                                    !canChat ||
                                    isLoading
                                }
                                placeholder={
                                    canChat
                                        ? "Ask a question about your documents…"
                                        : "Select documents first to start chatting…"
                                }
                                className="w-full resize-none bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 pr-10 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition disabled:opacity-50 disabled:cursor-not-allowed max-h-32"
                                style={{
                                    minHeight:
                                        "48px",
                                }}
                            />

                            <Paperclip
                                size={15}
                                className="absolute right-3 bottom-3.5 text-slate-600"
                            />

                        </div>


                        <button
                            type="submit"
                            disabled={
                                !canChat ||
                                !inputValue.trim() ||
                                isLoading
                            }
                            className="flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition shadow-lg shadow-blue-950/40 active:scale-95 shrink-0"
                        >

                            {isLoading ? (

                                <Loader2
                                    size={18}
                                    className="animate-spin"
                                />

                            ) : (

                                <Send
                                    size={18}
                                />

                            )}

                        </button>

                    </form>


                    <p className="text-[10px] text-slate-600 mt-2 text-center">

                        PatraRekhaAI may produce inaccurate information. Verify important details.

                    </p>

                </div>

            </div>


            {/* ============================================================
               DOCUMENT PANEL
            ============================================================ */}

            <div
                className={`
                    shrink-0
                    border-l
                    border-slate-800
                    bg-slate-900
                    flex
                    flex-col
                    transition-all
                    duration-300
                    overflow-hidden

                    ${
                        isPanelOpen
                            ? "w-72 xl:w-80"
                            : "w-0"
                    }
                `}
            >

                <div className="min-w-[17rem] xl:min-w-[19rem] flex flex-col h-full">


                    {/* Header */}

                    <div className="flex items-center justify-between px-4 py-4 border-b border-slate-800">

                        <div>

                            <h3 className="text-sm font-bold text-foreground">
                                Your Documents
                            </h3>

                            <p className="text-[11px] text-slate-500 mt-0.5">

                                {selectedCount}
                                {" / "}
                                {MAX_SELECTION}
                                {" selected"}

                            </p>

                        </div>


                        <button
                            onClick={
                                toggleAllPDFs
                            }
                            disabled={
                                documents.length ===
                                0
                            }
                            className="text-[11px] font-medium px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition disabled:opacity-40"
                        >

                            {selectedPDFs.size >
                            0

                                ? "Deselect All"

                                : documents.length >
                                  MAX_SELECTION

                                ? `Select ${MAX_SELECTION}`

                                : "Select All"}

                        </button>

                    </div>


                    {/* Search */}

                    <div className="px-4 py-3 border-b border-slate-800/60">

                        <div className="relative">

                            <Search
                                size={14}
                                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
                            />

                            <input
                                type="text"
                                value={
                                    searchQuery
                                }
                                onChange={(
                                    event
                                ) =>
                                    setSearchQuery(
                                        event.target.value
                                    )
                                }
                                placeholder="Search documents..."
                                className="w-full bg-slate-800 border border-slate-700/60 rounded-lg pl-8 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
                            />


                            {searchQuery && (

                                <button
                                    onClick={() =>
                                        setSearchQuery(
                                            ""
                                        )
                                    }
                                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                                >

                                    <X
                                        size={13}
                                    />

                                </button>

                            )}

                        </div>

                    </div>


                    {/* Documents */}

                    <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1.5">

                        {isDocumentsLoading ? (

                            <div className="flex items-center justify-center gap-2 py-10 text-xs text-slate-500">

                                <Loader2
                                    size={14}
                                    className="animate-spin text-blue-400"
                                />

                                Loading documents...

                            </div>

                        ) : documentsError ? (

                            <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">

                                <AlertCircle
                                    size={20}
                                    className="text-amber-400"
                                />

                                <p className="text-xs text-slate-500">
                                    {
                                        documentsError
                                    }
                                </p>

                            </div>

                        ) : filteredPDFs.length >
                          0 ? (

                            filteredPDFs.map(
                                (
                                    pdf
                                ) => {

                                    const isSelected =
                                        selectedPDFs.has(
                                            pdf.id
                                        );

                                    const isAtLimit =
                                        !isSelected &&
                                        selectedPDFs.size >=
                                            MAX_SELECTION;

                                    return (

                                        <button
                                            key={
                                                pdf.id
                                            }
                                            onClick={() =>
                                                togglePDF(
                                                    pdf.id
                                                )
                                            }
                                            disabled={
                                                isAtLimit
                                            }
                                            className={`
                                                w-full
                                                flex
                                                items-start
                                                gap-3
                                                p-3
                                                rounded-xl
                                                text-left
                                                border
                                                transition-all
                                                group

                                                ${
                                                    isSelected
                                                        ? "bg-blue-600/10 border-blue-500/40 shadow-sm"
                                                        : "bg-slate-800/30 border-slate-800/60 hover:border-slate-700 hover:bg-slate-800/60"
                                                }

                                                ${
                                                    isAtLimit
                                                        ? "opacity-60 cursor-not-allowed"
                                                        : ""
                                                }
                                            `}
                                        >

                                            <div
                                                className={`
                                                    shrink-0
                                                    mt-0.5
                                                    transition

                                                    ${
                                                        isSelected
                                                            ? "text-blue-400"
                                                            : "text-slate-600 group-hover:text-slate-400"
                                                    }
                                                `}
                                            >

                                                {isSelected ? (

                                                    <CheckSquare
                                                        size={17}
                                                    />

                                                ) : (

                                                    <Square
                                                        size={17}
                                                    />

                                                )}

                                            </div>


                                            <div
                                                className={`
                                                    shrink-0
                                                    w-8
                                                    h-8
                                                    rounded-lg
                                                    flex
                                                    items-center
                                                    justify-center
                                                    text-xs
                                                    font-bold
                                                    border
                                                    transition

                                                    ${
                                                        isSelected
                                                            ? "bg-blue-600/20 border-blue-500/30 text-blue-400"
                                                            : "bg-slate-800 border-slate-700 text-slate-500"
                                                    }
                                                `}
                                            >

                                                <FileText
                                                    size={14}
                                                />

                                            </div>


                                            <div className="min-w-0 flex-1">

                                                <p
                                                    className={`
                                                        text-xs
                                                        font-medium
                                                        leading-snug
                                                        truncate
                                                        transition

                                                        ${
                                                            isSelected
                                                                ? "text-blue-300"
                                                                : "text-slate-300 group-hover:text-slate-200"
                                                        }
                                                    `}
                                                >
                                                    {
                                                        pdf.label
                                                    }
                                                </p>


                                                <div className="flex items-center gap-2 mt-1">

                                                    <span className="text-[10px] text-slate-600">
                                                        {
                                                            pdf.size
                                                        }
                                                    </span>

                                                    <span className="text-[10px] text-slate-700">
                                                        ·
                                                    </span>

                                                    <span className="text-[10px] text-slate-600 truncate">
                                                        {
                                                            pdf.filename
                                                        }
                                                    </span>

                                                </div>


                                                <p className="text-[10px] text-slate-700 mt-0.5">

                                                    {
                                                        pdf.uploaded
                                                    }

                                                </p>

                                            </div>

                                        </button>
                                    );
                                }
                            )

                        ) : (

                            <div className="flex flex-col items-center justify-center py-10 text-center">

                                <Search
                                    size={20}
                                    className="text-slate-600 mb-2"
                                />

                                <p className="text-xs text-slate-500">
                                    No documents found
                                </p>

                            </div>

                        )}

                    </div>


                    {/* Footer */}

                    <div className="px-4 py-3 border-t border-slate-800 bg-slate-950/50">

                        <button
                            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl border border-dashed border-slate-700 hover:border-blue-600/50 hover:bg-blue-600/5 text-slate-500 hover:text-blue-400 text-xs font-medium transition"
                        >

                            <Upload
                                size={14}
                            />

                            Upload New PDF

                        </button>

                    </div>

                </div>

                {previewUrl && (
                    <CitationPreviewModal
                        document={previewDocument}
                        previewUrl={previewUrl}
                        previewPage={previewPage}
                        previewText={previewText}
                        isPreviewLoading={isPreviewLoading}
                        onClose={closePreview}
                    />
                )}
            </div>

        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Citation preview modal                                                      */
/* -------------------------------------------------------------------------- */

function CitationPreviewModal({
    document,
    previewUrl,
    previewPage,
    previewText,
    isPreviewLoading,
    onClose,
}) {
    if (!document && !isPreviewLoading) {
        return null;
    }

    const pageParam =
        previewPage && previewPage > 0
            ? `#page=${previewPage}`
            : "";

    const iframeSrc =
        previewUrl && pageParam
            ? `${previewUrl}${pageParam}`
            : previewUrl;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
            <div className="flex h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl">

                <div className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-800 bg-slate-900 px-5 py-3">
                    <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-200">
                            {document?.document_name ||
                                document?.filename ||
                                "Document Preview"}
                        </p>

                        {previewPage && (
                            <p className="truncate text-xs text-slate-500">
                                Jumping to page {previewPage}
                                {previewText && " · Matched text shown below"}
                            </p>
                        )}
                    </div>

                    <button
                        type="button"
                        onClick={onClose}
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-800 hover:text-slate-200"
                    >
                        <X size={18} />
                    </button>
                </div>

                <div className="flex min-h-0 flex-1">
                    {previewText && (
                        <div className="w-80 shrink-0 border-r border-slate-800 bg-slate-900/50 overflow-y-auto p-4">
                            <div className="flex items-center gap-2 mb-3">
                                <BookOpen size={14} className="text-blue-400" />
                                <span className="text-xs font-semibold text-slate-300">
                                    Matched Text
                                </span>
                            </div>

                            <p className="text-xs leading-5 text-slate-400 whitespace-pre-wrap">
                                {previewText}
                            </p>
                        </div>
                    )}

                    <div className="flex-1 min-h-0 bg-slate-900">
                        {isPreviewLoading ? (
                            <div className="flex h-full items-center justify-center">
                                <Loader2
                                    size={24}
                                    className="text-blue-400 animate-spin"
                                />
                            </div>
                        ) : (
                            <iframe
                                title="Document Preview"
                                src={iframeSrc}
                                className="h-full w-full border-0"
                            />
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
