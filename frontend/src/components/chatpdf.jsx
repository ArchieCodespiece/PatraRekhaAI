"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";

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
    Download,
} from "lucide-react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
    fetchDocuments,
    authenticatedFetch,
} from "../lib/supabaseAuth";

import { useI18n } from "../lib/i18n/I18nContext";


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


function renderInlineContent(children) {
    if (!children) return children;

    const processItem = (item) => {
        if (typeof item === 'string') {
            const parts = item.split(/<br\s*\/?>/gi);
            if (parts.length <= 1) return item;
            
            return parts.reduce((acc, part, idx) => {
                if (idx > 0) {
                    acc.push(<br key={idx} />);
                }
                acc.push(part);
                return acc;
            }, []);
        }
        if (React.isValidElement(item) && item.props && item.props.children) {
            return React.cloneElement(item, {
                ...item.props,
                children: renderInlineContent(item.props.children)
            });
        }
        if (Array.isArray(item)) {
            return item.map((subItem, index) => (
                <React.Fragment key={index}>
                    {processItem(subItem)}
                </React.Fragment>
            ));
        }
        return item;
    };

    return processItem(children);
}


function normalizeAIResponse(content) {
    if (!content) return "";

    let sanitized = content
        .replace(/<script[^>]*>([\s\S]*?)<\/script>/gi, "")
        .replace(/<iframe[^>]*>([\s\S]*?)<\/iframe>/gi, "")
        .replace(/on\w+\s*=\s*"[^"]*"/gi, "")
        .replace(/on\w+\s*=\s*'[^']*'/gi, "")
        .replace(/javascript:/gi, "");

    const lines = sanitized.split("\n");
    const processedLines = [];

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];

        if (line.trim().startsWith("|")) {
            while (
                i + 1 < lines.length &&
                !lines[i + 1].trim().startsWith("|") &&
                lines[i + 1].trim() !== "" &&
                !lines[i + 1].startsWith("#") &&
                !lines[i + 1].startsWith("-") &&
                !lines[i + 1].startsWith("*")
            ) {
                const nextLine = lines[i + 1].trim();
                const cleanedNextLine = nextLine.replace(/^\s*[•●▪◦]\s*/g, "• ");
                line = line.trim() + " <br /> " + cleanedNextLine;
                i++;
            }

            if (!line.trim().endsWith("|")) {
                line = line.trim() + " |";
            }

            line = line.replace(/([|])\s*[•●▪◦]\s*/g, "$1 • ");
            line = line.replace(/<br\s*\/?>\s*[•●▪◦]\s*/gi, "<br />• ");
        } else {
            line = line.replace(/(?:<br\s*\/?>\s*){2,}/gi, "\n\n");
            line = line.replace(/<br\s*\/?>\s*([•●▪◦])/gi, "\n- ");
            line = line.replace(/^\s*[•●▪◦]\s*/g, "- ");
            line = line.replace(/<br\s*\/?>/gi, "\n");
        }
        processedLines.push(line);
    }

    return processedLines.join("\n");
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
    const { t } = useI18n();

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
                                    "Couldn't load document. Check your connection and try again."
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
                        "Couldn't load documents. Check your connection and try again."
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
       EXPORT CONVERSATION
       ==================================================================== */

    const exportConversation = useCallback(() => {
        if (messages.length === 0) return;

        let markdown = "# Chat Export\n\n";

        for (const msg of messages) {
            const role = msg.role === "user" ? "**You**" : "**Assistant**";
            const timestamp = msg.timestamp
                ? new Date(msg.timestamp).toLocaleString()
                : "";
            markdown += `### ${role}${timestamp ? ` (${timestamp})` : ""}\n\n`;
            markdown += `${msg.content}\n\n`;
            if (msg.sources?.length > 0) {
                markdown += `*Sources: ${msg.sources.join(", ")}*\n\n`;
            }
            markdown += "---\n\n";
        }

        const blob = new Blob([markdown], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `chat-export-${new Date().toISOString().slice(0, 10)}.md`;
        a.click();
        URL.revokeObjectURL(url);
    }, [messages]);


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
                        "/chat/stream",
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


                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(
                        errorData?.detail ||
                        "Unable to get a response from the server."
                    );
                }


                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let streamedAnswer = "";
                let finalPayload = null;
                let buffer = "";


                const aiMessageId = `assistant-${Date.now()}`;

                setMessages(
                    (previous) => [
                        ...previous,
                        {
                            id: aiMessageId,
                            role: "assistant",
                            content: "",
                            timestamp: new Date(),
                            sources: [],
                            citations: [],
                            streaming: true,
                        },
                    ]
                );


                while (true) {
                    const { done, value } = await reader.read();

                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });

                    const lines = buffer.split("\n");
                    buffer = lines.pop() || "";

                    for (const line of lines) {
                        if (!line.startsWith("data: ")) continue;

                        try {
                            const payload = JSON.parse(line.slice(6));

                            if (payload.done) {
                                finalPayload = payload;
                            } else if (payload.token) {
                                streamedAnswer += payload.token;

                                setMessages(
                                    (previous) =>
                                        previous.map((msg) =>
                                            msg.id === aiMessageId
                                                ? { ...msg, content: streamedAnswer }
                                                : msg
                                        )
                                );
                            }
                        } catch {
                            // skip malformed SSE lines
                        }
                    }
                }


                setMessages(
                    (previous) =>
                        previous.map((msg) =>
                            msg.id === aiMessageId
                                ? {
                                    ...msg,
                                    content: streamedAnswer || "I couldn't generate a response.",
                                    streaming: false,
                                    sources: finalPayload?.sources || [],
                                    citations: finalPayload?.citations || [],
                                }
                                : msg
                        )
                );


                if (
                    finalPayload?.conversation_id &&
                    !currentConversationId
                ) {
                    setCurrentConversationId(
                        finalPayload.conversation_id
                    );
                }


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

        <div className="flex h-full w-full overflow-hidden bg-background border border-border/40">


            {/* ============================================================
               RECENT CHATS
            ============================================================ */}

            <div
                className={`
                    shrink-0
                    border-r
                    border-border/50
                    bg-card
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

                    <div className="px-4 py-4 border-b border-border/40">

                        <div className="flex items-center justify-between">

                            <div>

                                <h3 className="text-sm font-bold text-foreground">
                                    {t("chat.recentChats")}
                                </h3>

                                <p className="text-[10px] text-foreground/75 mt-0.5">
                                    {t("chat.conversationHistory")}
                                </p>

                            </div>

                            <button
                                onClick={() =>
                                    setIsHistoryOpen(
                                        false
                                    )
                                }
                                className="p-1.5 rounded-lg hover:bg-border/30 text-foreground/75 hover:text-foreground"
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
                            className="w-full mt-4 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-primary hover:bg-primary/85 text-primary-foreground text-xs font-semibold transition shadow-sm shadow-foreground/15"
                        >

                            <Plus
                                size={14}
                            />

                            {t("chat.newChat")}

                        </button>

                    </div>


                    {/* Conversations */}

                    <div className="flex-1 overflow-y-auto px-2 py-3">

                        {isHistoryLoading &&
                        conversations.length === 0 ? (

                            <div className="flex items-center justify-center gap-2 py-10 text-xs text-foreground/75">

                                <Loader2
                                    size={14}
                                    className="animate-spin"
                                />

                                {t("chat.loadingChats")}

                            </div>

                        ) : conversations.length === 0 ? (

                            <div className="flex flex-col items-center justify-center text-center py-10 px-4">

                                <MessageSquare
                                    size={22}
                                    className="text-muted-foreground mb-2"
                                />

                                <p className="text-xs text-foreground/75">
                                    {t("chat.noConversations")}
                                </p>

                                <p className="text-[10px] text-foreground/70 mt-1">
                                    {t("chat.startNewChat")}
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
                                                            ? "bg-primary/12 border border-primary/30"
                                                            : "border border-transparent hover:bg-border/25"
                                                    }
                                                `}
                                            >

                                                <MessageSquare
                                                    size={14}
                                                    className={`
                                                        shrink-0

                                                        ${
                                                            active
                                                                ? "text-primary"
                                                                : "text-foreground/70"
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
                                                                    ? "text-primary"
                                                                    : "text-foreground/80"
                                                            }
                                                        `}
                                                    >
                                                        {
                                                            conversation.title
                                                        }
                                                    </p>

                                                     <p className="text-[9px] text-foreground/70 mt-0.5">
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
                                                    className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-primary/10 text-foreground/70 hover:text-primary transition"
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

                <div className="flex flex-col gap-2 px-6 py-4 border-b border-border/40 bg-background/90">

                    <div className="flex items-center justify-between gap-3">

                        <div className="flex items-center gap-3 min-w-0">

                            {!isHistoryOpen && (

                                <button
                                    onClick={() =>
                                        setIsHistoryOpen(
                                            true
                                        )
                                    }
                                    className="p-2 rounded-lg bg-card/70 hover:bg-border/30 text-foreground/80"
                                >

                                    <ChevronRight
                                        size={16}
                                    />

                                </button>

                            )}


                            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-primary/12 border border-primary/20 text-primary shrink-0">

                                <MessageSquare
                                    size={18}
                                />

                            </div>


                            <div className="min-w-0">

                                <h2 className="text-sm font-bold text-foreground">
                                    {t("chat.title")}
                                </h2>

                                <p className="text-[11px] text-foreground/80">

                                    {canChat
                                        ? t("chat.selectedCount", "{count} document(s) selected").replace("{count}", selectedCount)
                                        : t("chat.selectToStart")}

                                </p>

                            </div>

                        </div>


                        <div className="flex items-center gap-2">
                            {messages.length > 0 && (
                                <button
                                    onClick={exportConversation}
                                    title={t("chat.exportChat")}
                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-card/70 hover:bg-border/30 text-foreground/80 text-xs font-medium transition shrink-0"
                                >
                                    <Download size={14} />
                                    <span className="hidden sm:inline">{t("chat.export")}</span>
                                </button>
                            )}

                            <button
                                onClick={() =>
                                    setIsPanelOpen(
                                        !isPanelOpen
                                    )
                                }
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-card/70 hover:bg-border/30 text-foreground/80 text-xs font-medium transition shrink-0"
                            >

                            <FileText
                                size={14}
                            />

                            <span className="hidden sm:inline">
                                {t("sidebar.documents")}
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
                                                className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-primary/8 border border-primary/20 text-primary text-[10px] font-medium max-w-[140px] truncate"
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

                                <span className="flex items-center px-2 py-0.5 rounded-md bg-card/70 text-foreground/80 text-[10px] font-medium border border-border/40">

                                    +
                                    {selectedCount - 4}
                                    {" "}
                                    {t("chat.more")}

                                </span>

                            )}

                        </div>

                    )}

                </div>


                {/* ========================================================
                   MESSAGES
                ======================================================== */}

                <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5 scrollbar-thin scrollbar-thumb-[#CABDB2] scrollbar-track-transparent">

                    {messages.length === 0 ? (

                        <div className="flex flex-col items-center justify-center h-full text-center gap-5 py-16">

                            <div className="w-20 h-20 rounded-2xl bg-primary/8 border border-primary/18 flex items-center justify-center">

                                <MessageSquare
                                    size={36}
                                    className="text-primary/50"
                                />

                            </div>


                            <div>

                                <h3 className="text-base font-semibold text-foreground">
                                    {t("chat.askDocuments")}
                                </h3>

                                <p className="text-sm text-foreground/80 mt-1.5 max-w-xs">
                                    {t("chat.selectPdfs")}
                                </p>

                            </div>


                            {!canChat && (

                                <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary/8 border border-primary/18 text-primary text-xs">

                                    <AlertCircle
                                        size={14}
                                    />

                                    {t("chat.noDocumentsSelected")}

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
                                            className="px-3 py-2 text-xs text-foreground/80 border border-border/40 rounded-xl hover:border-primary/40 hover:text-primary hover:bg-primary/6 transition disabled:opacity-40 disabled:cursor-not-allowed text-left"
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
                                                        ? "bg-primary text-primary-foreground"
                                                        : "bg-card border border-border/50 text-primary"
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
                                                w-full
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
                                                    w-full
                                                    px-4
                                                    py-3
                                                    rounded-2xl
                                                    text-sm
                                                    leading-relaxed
                                                    overflow-hidden
                                                    break-words
                                                    
                                                    ${
                                                        message.role ===
                                                        "user"
                                                            ? "bg-primary text-primary-foreground rounded-tr-sm shadow-md shadow-foreground/15"
                                                            : "bg-card/70 border border-border/40 text-foreground rounded-tl-sm backdrop-blur-sm shadow-sm shadow-foreground/5"
                                                    }
                                                `}
                                            >
                                                {message.role === "user" ? (
                                                    <div className="whitespace-pre-wrap break-words">
                                                        {message.content}
                                                    </div>
                                                ) : (
                                                    <ReactMarkdown
                                                        remarkPlugins={[
                                                            remarkGfm,
                                                        ]}
                                                        components={{
                                                            table: ({
                                                                children,
                                                            }) => (
                                                                <div className="w-full overflow-x-auto my-4 rounded-xl border border-border/50 bg-card/30 scrollbar-thin shadow-sm shadow-foreground/5">
                                                                    <table className="w-full border-collapse text-left text-xs text-foreground table-auto min-w-full">
                                                                        {children}
                                                                    </table>
                                                                </div>
                                                            ),
                                                            thead: ({ children }) => (
                                                                <thead className="bg-card/80 border-b border-border/60">
                                                                    {children}
                                                                </thead>
                                                            ),
                                                            tr: ({ children }) => (
                                                                <tr className="border-b border-border/35 last:border-b-0 hover:bg-card/50 transition-colors">
                                                                    {children}
                                                                </tr>
                                                            ),
                                                            th: ({
                                                                children,
                                                            }) => (
                                                                <th className="px-4 py-3 font-semibold text-foreground text-xs tracking-wider">
                                                                    {renderInlineContent(children)}
                                                                </th>
                                                            ),
                                                            td: ({
                                                                children,
                                                            }) => (
                                                                <td className="px-4 py-3 text-foreground align-top whitespace-normal">
                                                                    {renderInlineContent(children)}
                                                                </td>
                                                            ),
                                                            ul: ({
                                                                children,
                                                            }) => (
                                                                <ul className="list-disc pl-6 space-y-1.5 my-3 text-foreground">
                                                                    {children}
                                                                </ul>
                                                            ),
                                                            ol: ({
                                                                children,
                                                            }) => (
                                                                <ol className="list-decimal pl-6 space-y-1.5 my-3 text-foreground">
                                                                    {children}
                                                                </ol>
                                                            ),
                                                            li: ({ children }) => (
                                                                <li className="leading-relaxed pl-1 marker:text-primary">
                                                                    {children}
                                                                </li>
                                                            ),
                                                            p: ({
                                                                children,
                                                            }) => (
                                                                <p className="mb-4 last:mb-0 whitespace-pre-wrap leading-relaxed text-foreground">
                                                                    {renderInlineContent(children)}
                                                                </p>
                                                            ),
                                                             blockquote: ({ children }) => (
                                                                 <blockquote className="pl-3 py-1.5 italic text-foreground/80 my-3 bg-card/30 rounded-r-lg">
                                                                    {children}
                                                                </blockquote>
                                                            ),
                                                            em: ({ children }) => (
                                                                <em className="italic text-foreground/80">
                                                                    {children}
                                                                </em>
                                                            ),
                                                            h1: ({
                                                                children,
                                                            }) => (
                                                                <h1 className="text-xl font-bold font-heading text-foreground mt-6 mb-3 border-b border-border/30 pb-1">
                                                                    {children}
                                                                </h1>
                                                            ),
                                                            h2: ({
                                                                children,
                                                            }) => (
                                                                <h2 className="text-lg font-semibold font-heading text-foreground mt-5 mb-2">
                                                                    {children}
                                                                </h2>
                                                            ),
                                                            h3: ({
                                                                children,
                                                            }) => (
                                                                <h3 className="text-base font-semibold font-heading text-foreground mt-4 mb-2">
                                                                    {children}
                                                                </h3>
                                                            ),
                                                            h4: ({ children }) => (
                                                                <h4 className="text-sm font-semibold text-foreground mt-3 mb-1">
                                                                    {children}
                                                                </h4>
                                                            ),
                                                            strong: ({
                                                                children,
                                                            }) => (
                                                                <strong className="font-semibold text-foreground">
                                                                    {children}
                                                                </strong>
                                                            ),
                                                            a: ({
                                                                href,
                                                                children,
                                                            }) => (
                                                                <a
                                                                    href={href}
                                                                    className="text-primary underline font-medium hover:text-primary transition-colors break-all"
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
                                                                    <code className="bg-card/60 px-1.5 py-0.5 rounded text-primary text-xs font-mono font-semibold">
                                                                        {children}
                                                                    </code>
                                                                ) : (
                                                                    <code className="block bg-primary p-4 rounded-xl text-primary-foreground text-xs font-mono overflow-x-auto my-3 border border-[#413632] scrollbar-thin">
                                                                        {children}
                                                                    </code>
                                                                ),
                                                        }}
                                                    >
                                                        {normalizeAIResponse(message.content)}
                                                    </ReactMarkdown>
                                                )}
                                            </div>


                                            {((message.citations &&
                                                message.citations.length >
                                                0) ||
                                                (message.sources &&
                                                    message.sources
                                                        .length >
                                                    0)) && (
                                                <div className="flex flex-wrap gap-1.5 mt-1.5">
                                                     <span className="text-[10px] text-foreground/70 self-center mr-1">
                                                        {t("chat.sources")}:
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
                                                                              className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-card/70 text-foreground/80 border border-border/40 hover:border-primary/50 hover:text-primary transition cursor-pointer text-left"
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
                                                                                   <span className="text-foreground/80">
                                                                                       ·
                                                                                       {pageLabel}
                                                                                   </span>
                                                                               )}

                                                                                 {citation.section && (
                                                                                     <span className="text-foreground/80 truncate max-w-[100px]">
                                                                                       ·
                                                                                       {citation.section}
                                                                                   </span>
                                                                               )}

                                                                               <ExternalLink
                                                                                   size={
                                                                                       8
                                                                                   }
                                                                                   className="shrink-0 text-foreground/80"
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
                                                                            className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md bg-card/70 text-foreground/80 border border-border/40"
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


                                            <span className="text-[10px] text-foreground/70">

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

                                    <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">

                                        <Bot
                                            size={15}
                                        />

                                    </div>


                                    <div className="px-4 py-3 rounded-xl rounded-tl-sm bg-card border border-border/40 flex items-center gap-2.5 backdrop-blur-sm">

                                        <div className="flex gap-1">
                                            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                                            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse [animation-delay:150ms]" />
                                            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse [animation-delay:300ms]" />
                                        </div>

                                        <span className="text-sm text-muted-foreground">
                                            {t("chat.analyzingDocuments", "Searching documents...")}
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

                <div className="px-6 py-4 border-t border-border/40 bg-background/70">

                    {!canChat && (

                        <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-primary/6 border border-primary/15 text-primary/80 text-xs">

                            <AlertCircle
                                size={13}
                            />

                            {t("chat.selectPdfToEnable")}

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
                                        ? t("chat.askPlaceholderChat")
                                        : t("chat.selectFirst")
                                }
                                className="w-full resize-none bg-card/70 border border-border/60 rounded-xl px-4 py-3 pr-10 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary transition disabled:opacity-50 disabled:cursor-not-allowed max-h-32 backdrop-blur-sm"
                                style={{
                                    minHeight:
                                        "48px",
                                }}
                            />

                            <Paperclip
                                size={15}
                                className="absolute right-3 bottom-3.5 text-foreground/70"
                            />

                        </div>


                        <button
                            type="submit"
                            disabled={
                                !canChat ||
                                !inputValue.trim() ||
                                isLoading
                            }
                            className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary hover:bg-primary/85 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground transition shadow-lg shadow-foreground/15 active:scale-95 shrink-0"
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


                    <p className="text-[10px] text-foreground/70 mt-2 text-center">

                        {t("chat.disclaimer")}

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
                    border-border/50
                    bg-card
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

                    <div className="flex items-center justify-between px-4 py-4 border-b border-border/40">

                        <div>

                            <h3 className="text-sm font-bold text-foreground">
                                {t("chat.yourDocuments")}
                            </h3>

                            <p className="text-[11px] text-foreground/75 mt-0.5">

                                {selectedCount}
                                {" / "}
                                {MAX_SELECTION}

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
                            className="text-[11px] font-medium px-2.5 py-1 rounded-lg bg-card/70 hover:bg-border/30 text-foreground/80 transition disabled:opacity-40"
                        >

                            {selectedPDFs.size >
                            0

                                ? t("chat.deselectAll")

                                : documents.length >
                                  MAX_SELECTION

                                ? t("chat.selectN", "Select {count}").replace("{count}", MAX_SELECTION)

                                : t("chat.selectAll")}

                        </button>

                    </div>


                    {/* Search */}

                    <div className="px-4 py-3 border-b border-border/30">

                        <div className="relative">

                            <Search
                                size={14}
                                className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground/75"
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
                                placeholder={t("docs.searchPlaceholder")}
                                className="w-full bg-card/80 border border-border/60 rounded-lg pl-8 pr-3 py-2 text-xs text-foreground placeholder:text-muted-foreground/45 focus:outline-none focus:border-primary focus:ring-2 focus:ring-[#CA8A78]/15 transition backdrop-blur-sm shadow-sm shadow-foreground/5"
                            />


                            {searchQuery && (

                                <button
                                    onClick={() =>
                                        setSearchQuery(
                                            ""
                                        )
                                    }
                                    className="absolute right-2 top-1/2 -translate-y-1/2 text-foreground/75 hover:text-foreground"
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

                            <div className="flex items-center justify-center gap-2 py-10 text-xs text-foreground/75">

                                <Loader2
                                    size={14}
                                    className="animate-spin text-primary"
                                />

                                {t("common.loading")}

                            </div>

                        ) : documentsError ? (

                            <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">

                                <AlertCircle
                                    size={20}
                                    className="text-primary"
                                />

                                <p className="text-xs text-foreground/75">
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
                                                        ? "bg-primary/10 border-primary/50 shadow-sm shadow-primary/10"
                                                        : "bg-card/70 border-border/50 hover:border-primary/40 hover:bg-card hover:shadow-sm hover:shadow-foreground/5"
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
                                                            ? "text-primary"
                                                             : "text-foreground/70 group-hover:text-foreground/85"
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
                                                            ? "bg-primary/12 border-primary/20 text-primary"
                                                             : "bg-card/60 border-border/40 text-foreground/80"
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
                                                                ? "text-primary"
                                                                : "text-foreground/80 group-hover:text-foreground"
                                                        }
                                                    `}
                                                >
                                                    {
                                                        pdf.label
                                                    }
                                                </p>


                                                <div className="flex items-center gap-2 mt-1">

                                             <span className="text-[10px] text-foreground/70">
                                                        {
                                                            pdf.size
                                                        }
                                                    </span>

                                                    <span className="text-[10px] text-foreground/65">
                                                        ·
                                                    </span>

                                                    <span className="text-[10px] text-foreground/70 truncate">
                                                        {
                                                            pdf.filename
                                                        }
                                                    </span>

                                                </div>


                                                <p className="text-[10px] text-foreground/70 mt-0.5">

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
                                    className="text-foreground/70 mb-2"
                                />

                                <p className="text-xs text-foreground/75">
                                    {t("docs.emptyNoDocuments")}
                                </p>

                            </div>

                        )}

                    </div>


                    {/* Footer */}

                    <div className="px-4 py-3 border-t border-border/30 bg-card/40">

                        <button
                            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl border border-dashed border-border/50 hover:border-primary/50 hover:bg-primary/6 text-foreground/75 hover:text-primary text-xs font-medium transition"
                        >

                            <Upload
                                size={14}
                            />

                            {t("docs.uploadNewPdf")}

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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-primary/60 p-4">
            <div className="flex h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-border/50 bg-background shadow-2xl shadow-foreground/20">

                <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border/40 bg-card px-5 py-3">
                    <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">
                            {document?.document_name ||
                                document?.filename ||
                                "Document Preview"}
                        </p>

                        {previewPage && (
                                <p className="truncate text-xs text-foreground/75">
                                Jumping to page {previewPage}
                                {previewText && " · Matched text shown below"}
                            </p>
                        )}
                    </div>

                    <button
                        type="button"
                        onClick={onClose}
                         className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-foreground/75 transition hover:bg-border/30 hover:text-foreground"
                    >
                        <X size={18} />
                    </button>
                </div>

                <div className="flex min-h-0 flex-1">
                    {previewText && (
                        <div className="w-80 shrink-0 border-r border-border/40 bg-card/40 overflow-y-auto p-4">
                            <div className="flex items-center gap-2 mb-3">
                                <BookOpen size={14} className="text-primary" />
                                <span className="text-xs font-semibold text-foreground/80">
                                    Matched Text
                                </span>
                            </div>

                            <p className="text-xs leading-5 text-foreground/80 whitespace-pre-wrap">
                                {previewText}
                            </p>
                        </div>
                    )}

                        <div className="flex-1 min-h-0 bg-card/30">
                        {isPreviewLoading ? (
                            <div className="flex h-full items-center justify-center">
                                <Loader2
                                    size={24}
                                    className="text-primary animate-spin"
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
