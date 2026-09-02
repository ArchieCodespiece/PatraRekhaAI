"use client";

import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";

import {
    AlertTriangle,
    AlertCircle,
    CheckCircle2,
    CalendarClock,
    Eye,
    FileText,
    Grid3X3,
    List,
    Loader2,
    RefreshCw,
    Search,
    Trash2,
    Upload,
    X,
} from "lucide-react";

import { motion, AnimatePresence } from "motion/react";

import {
    authenticatedFetch,
    getStoredAuthUser,
} from "../lib/supabaseAuth";

import {
    DocumentCard,
    ProcessingPipeline,
    Skeleton,
    CardSkeleton,
} from "./ui";
import { HelpTooltip } from "./ui/help-tooltip";
import { useI18n } from "../lib/i18n/I18nContext";

/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

function parseTimeline(value) {
    if (!value) {
        return [];
    }

    if (Array.isArray(value)) {
        return value;
    }

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
    return (
        document?.file_heading ||
        `${cleanFilename(document?.filename)}`
    );
}

function formatBytes(bytes) {
    const size = Number(bytes || 0);

    if (!size) {
        return "Unknown size";
    }

    const units = ["B", "KB", "MB", "GB"];

    const index = Math.min(
        Math.floor(Math.log(size) / Math.log(1024)),
        units.length - 1
    );

    return `${(
        size /
        1024 ** index
    ).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function deduplicateDocuments(docs) {
    const seen = new Set();
    return docs.filter((doc) => {
        const id = doc.file_id;
        if (!id || seen.has(id)) return false;
        seen.add(id);
        return true;
    });
}

/* -------------------------------------------------------------------------- */
/* API helpers                                                                */
/* -------------------------------------------------------------------------- */

async function parseResponse(response) {
    const text = await response.text();

    if (!text) {
        return {};
    }

    try {
        return JSON.parse(text);
    } catch {
        return {
            detail: text,
        };
    }
}

async function fetchDocumentList() {
    const response = await authenticatedFetch(
        "/get-documents"
    );

    const data = await parseResponse(response);

    if (!response.ok) {
        throw new Error(
            data?.detail ||
                "Unable to load documents."
        );
    }

    return Array.isArray(data?.documents)
        ? data.documents
        : [];
}

async function fetchSemanticDocuments(query) {
    const response = await authenticatedFetch(
        "/semantic-document-search",
        {
            method: "POST",
            body: JSON.stringify({
                query,
            }),
        }
    );

    const data = await parseResponse(response);

    if (!response.ok) {
        throw new Error(
            data?.detail ||
                "Unable to search documents."
        );
    }

    return Array.isArray(data?.documents)
        ? data.documents
        : [];
}

async function deleteDocumentOnServer(fileId) {
    if (!fileId) {
        throw new Error(
            "Missing document ID."
        );
    }

    const response = await authenticatedFetch(
        `/documents/${encodeURIComponent(fileId)}`,
        {
            method: "DELETE",
        }
    );

    const data = await parseResponse(response);

    if (!response.ok) {
        throw new Error(
            data?.detail ||
                "Unable to delete document."
        );
    }

    return data;
}

async function reprocessDocumentOnServer(fileId) {
    if (!fileId) {
        throw new Error("Missing document ID.");
    }

    const response = await authenticatedFetch(
        `/documents/${encodeURIComponent(fileId)}/reprocess`,
        {
            method: "POST",
        }
    );

    const data = await parseResponse(response);

    if (!response.ok) {
        throw new Error(
            data?.detail ||
                "Unable to re-process document."
        );
    }

    return data;
}

async function uploadDocumentToServer(file) {
    if (!file) {
        throw new Error(
            "No file selected."
        );
    }

    const formData = new FormData();

    formData.append(
        "file",
        file
    );

    /*
     * Do NOT append owner_email here.
     *
     * The backend gets the authenticated user's
     * Supabase UUID from the Authorization JWT.
     */

    const response = await authenticatedFetch(
        "/upload-document",
        {
            method: "POST",
            body: formData,
        }
    );

    const data = await parseResponse(response);

    if (!response.ok) {
        throw new Error(
            data?.detail ||
                "Unable to upload document."
        );
    }

    return data;
}

/* -------------------------------------------------------------------------- */
/* Processing state helpers                                                   */
/* -------------------------------------------------------------------------- */

export function isDocumentProcessing(document) {
    if (!document) return false;

    // Explicit optimistic / upload flag
    if (document.isProcessing || document.status === "processing" || document.status === "uploading") {
        return true;
    }

    // Temporary optimistic document
    if (typeof document.file_id === "string" && document.file_id.startsWith("temp-")) {
        return true;
    }

    // Real backend database state:
    // A document is only considered fully processed once BOTH summarization (metadata) AND vector indexing are complete.
    const hasSummarization = Boolean(document.summarization || document.is_summarized);
    const hasVectored = Boolean(document.is_vectored);

    return !hasSummarization || !hasVectored;
}

// Stage definitions. minDwell = minimum ms to show before advancing.
// gate = backend condition that must be TRUE before we START the dwell timer for this stage.
// (i.e. we wait at the previous stage until this gate opens, then tick through minDwell, then advance)
const STAGE_SEQUENCE = [
    { key: "upload",    minDwell: 900,   gate: () => true },
    { key: "extract",   minDwell: 2500,  gate: () => true },
    { key: "ner",       minDwell: 2000,  gate: () => true },
    { key: "summarize", minDwell: 2500,  gate: () => true },
    { key: "embed",     minDwell: 2000,  gate: (doc) => Boolean(doc?.is_summarized || doc?.summarization) },
    { key: "index",     minDwell: 1500,  gate: (doc) => Boolean(doc?.is_vectored) },
];

/**
 * Returns the current visual pipeline stage key, or `null` once the pipeline is
 * fully complete (backend confirmed + all visual stages shown).
 *
 * Design rules:
 * - Walks stage-by-stage via timers. Never skips embed/index visually.
 * - Gated stages (embed, index): timer only STARTS once the backend flag is true.
 *   Until then, the stage label is shown as "waiting" (the pulsing dot stays on it).
 * - Returns null only when we've reached the last stage, dwell elapsed, AND
 *   isDocumentProcessing() is false. DocumentRow uses null to switch to ✓ Processed.
 * - Already-processed documents (isDocumentProcessing false on first render): return
 *   null immediately → show ✓ Processed with no pipeline shown.
 */
export function useDocumentPipelineStage(doc) {
    // null = fully done (show ✓ Processed); number = index into STAGE_SEQUENCE
    const [stageIdx, setStageIdx] = useState(() =>
        isDocumentProcessing(doc) ? 0 : null
    );

    // Refs so timer callbacks always read the latest values without re-registering
    const docRef       = useRef(doc);
    const stageIdxRef  = useRef(stageIdx);
    docRef.current     = doc;
    stageIdxRef.current = stageIdx;

    // Track document identity so we can reset on new upload
    const prevFileIdRef = useRef(doc?.file_id);

    // Reset to stage 0 when a new document is passed in (new upload)
    useEffect(() => {
        const currentId = doc?.file_id;
        if (currentId !== prevFileIdRef.current) {
            prevFileIdRef.current = currentId;
            if (isDocumentProcessing(doc)) {
                setStageIdx(0);
                stageIdxRef.current = 0;
            } else {
                setStageIdx(null);
                stageIdxRef.current = null;
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [doc?.file_id]);

    useEffect(() => {
        if (stageIdx === null) return; // already done — nothing to do

        const stage = STAGE_SEQUENCE[stageIdx];
        if (!stage) {
            // Past the end — transition to done if backend agrees
            if (!isDocumentProcessing(docRef.current)) setStageIdx(null);
            return;
        }

        const isLastStage = stageIdx === STAGE_SEQUENCE.length - 1;

        // --- Gated stages: don't start timer until gate is open ---
        if (!stage.gate(docRef.current)) {
            // Gate not open yet. Stay on this stage (pulsing dot visible).
            // Effect will re-run when is_summarized / is_vectored changes via deps.
            return;
        }

        // Gate is open — dwell for minDwell ms, then advance (or finish)
        const timerId = setTimeout(() => {
            if (isLastStage) {
                // We've walked through all stages. Only mark done when backend confirms.
                if (!isDocumentProcessing(docRef.current)) {
                    setStageIdx(null);
                    stageIdxRef.current = null;
                }
                // If backend isn't done yet, stay at last stage and wait for is_vectored dep to trigger
            } else {
                const next = stageIdxRef.current + 1;
                setStageIdx(next);
                stageIdxRef.current = next;
            }
        }, stage.minDwell);

        return () => clearTimeout(timerId);

    // Re-run when: stage advances, OR backend flags update, OR temp-doc's isProcessing flips
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [stageIdx, doc?.is_summarized, doc?.is_vectored, doc?.isProcessing]);

    if (stageIdx === null) return null;
    return STAGE_SEQUENCE[stageIdx]?.key ?? STAGE_SEQUENCE[0].key;
}

/* -------------------------------------------------------------------------- */
/* Main component                                                             */
/* -------------------------------------------------------------------------- */

export default function Documents() {
    const { t } = useI18n();
    const [documents, setDocuments] = useState([]);

    const [selectedDocument, setSelectedDocument] =
        useState(null);

    const [viewMode, setViewMode] =
        useState("row");

    const [searchMode, setSearchMode] =
        useState("normal");

    const [searchQuery, setSearchQuery] =
        useState("");

    const [semanticDocuments, setSemanticDocuments] =
        useState([]);

    const [isSemanticLoading, setIsSemanticLoading] =
        useState(false);

    const [semanticError, setSemanticError] =
        useState("");

    const [isLoading, setIsLoading] =
        useState(true);

    const [error, setError] =
        useState("");

    const [previewUrl, setPreviewUrl] =
        useState("");

    const [documentToDelete, setDocumentToDelete] =
        useState(null);

    const [isDeleting, setIsDeleting] =
        useState(false);

    const [deleteError, setDeleteError] =
        useState("");

    const [toasts, setToasts] = useState([]);
    const [deletingFileIds, setDeletingFileIds] = useState(new Set());

    const addToast = useCallback((message, type = "info", fileId = null, filename = "", errorObj = null) => {
        const id = Math.random().toString(36).substr(2, 9);
        setToasts((prev) => [
            ...prev.filter(t => !(t.fileId === fileId && t.type === type)),
            { id, message, type, fileId, filename, errorObj }
        ]);
        if (type !== "deleting" && type !== "error") {
            setTimeout(() => {
                setToasts((prev) => prev.filter((t) => t.id !== id));
            }, 4000);
        }
        return id;
    }, []);

    const removeToast = useCallback((id) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    const removeToastByFileId = useCallback((fileId, type) => {
        setToasts((prev) => prev.filter((t) => !(t.fileId === fileId && t.type === type)));
    }, []);

    const [isUploading, setIsUploading] =
        useState(false);

    const [uploadError, setUploadError] =
        useState("");

    const [uploadSuccess, setUploadSuccess] =
        useState("");

    const [isDragging, setIsDragging] = useState(false);

    const fileInputRef =
        useRef(null);

    const searchInputRef =
        useRef(null);

    const [authUser, setAuthUser] =
        useState(() => getStoredAuthUser());

    const [docPage, setDocPage] = useState(1);
    const DOCS_PER_PAGE = 12;

    const [batchSelected, setBatchSelected] = useState(new Set());
    const [isBatchDeleting, setIsBatchDeleting] = useState(false);

    /* ---------------------------------------------------------------------- */
    /* Refresh documents                                                      */
    /* ---------------------------------------------------------------------- */

    const refreshDocuments =
        useCallback(async () => {
            setError("");

            try {
                const nextDocuments =
                    await fetchDocumentList();

                setDocuments((prevDocs) => {
                    const pendingOptimistic = prevDocs.filter(
                        (d) => d.file_id?.startsWith?.("temp-") && !nextDocuments.some((nd) => nd.filename === d.filename)
                    );
                    return deduplicateDocuments([...pendingOptimistic, ...nextDocuments]);
                });
            } catch (fetchError) {
                setError(
                    fetchError?.message ||
                        t("docs.loadError")
                );
            } finally {
                setIsLoading(false);
            }
        }, [t]);

    /* ---------------------------------------------------------------------- */
    /* Keyboard shortcuts                                                      */
    /* ---------------------------------------------------------------------- */

    useEffect(() => {
        const handleKeyDown = (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                e.preventDefault();
                searchInputRef.current?.focus();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === "u") {
                e.preventDefault();
                openFilePicker();
            }
            if (e.key === "Escape" && selectedDocument) {
                onClose();
            }
        };
        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [selectedDocument]);

    /* ---------------------------------------------------------------------- */
    /* Dynamic polling: fast (2.5s) while processing, standard (12s) otherwise */
    /* ---------------------------------------------------------------------- */

    const hasProcessingDocuments = useMemo(() => {
        return documents.some(isDocumentProcessing);
    }, [documents]);

    // --- Initial load (runs once when auth user is available) ---
    useEffect(() => {
        if (!authUser?.id) return;

        let isMounted = true;
        setIsLoading(true);
        setError("");

        fetchDocumentList()
            .then((nextDocuments) => {
                if (isMounted) setDocuments(deduplicateDocuments(nextDocuments));
            })
            .catch((fetchError) => {
                if (isMounted) setError(fetchError?.message || t("docs.loadError"));
            })
            .finally(() => {
                if (isMounted) setIsLoading(false);
            });

        return () => { isMounted = false; };
    }, [authUser?.id]);

    // --- Adaptive polling interval: 2.5s while processing, 12s otherwise ---
    useEffect(() => {
        if (!authUser?.id) return;

        let isRefreshing = false;
        let isMounted = true;

        const silentRefresh = async () => {
            if (!isMounted || isRefreshing) return;
            // Don't poll while tab is hidden
            if (typeof document !== "undefined" && document.hidden) return;

            isRefreshing = true;
            try {
                const nextDocuments = await fetchDocumentList();
                if (isMounted) {
                    setDocuments((prevDocs) => {
                        const pendingOptimistic = prevDocs.filter(
                            (d) => d.file_id?.startsWith?.("temp-") &&
                                   !nextDocuments.some((nd) => nd.filename === d.filename)
                        );
                        return deduplicateDocuments([...pendingOptimistic, ...nextDocuments]);
                    });
                }
            } catch {
                /* Background refresh failures are intentionally silent */
            } finally {
                isRefreshing = false;
            }
        };

        const handleFocus = () => { silentRefresh(); };

        const pollInterval = hasProcessingDocuments ? 2500 : 12000;
        const intervalId = window.setInterval(silentRefresh, pollInterval);
        window.addEventListener("focus", handleFocus);

        return () => {
            isMounted = false;
            window.clearInterval(intervalId);
            window.removeEventListener("focus", handleFocus);
        };
    }, [authUser?.id, hasProcessingDocuments]);

    /* ---------------------------------------------------------------------- */
    /* Filter documents                                                       */
    /* ---------------------------------------------------------------------- */

    const filteredDocuments =
        useMemo(() => {
            let result;

            if (
                searchMode ===
                "semantic"
            ) {
                result = searchQuery.trim()
                    ? semanticDocuments
                    : documents;
            } else {
                const query =
                    searchQuery
                        .trim()
                        .toLowerCase();

                if (!query) {
                    result = documents;
                } else {
                    result = documents.filter(
                        (document) => {
                            const title =
                                documentTitle(
                                    document
                                ).toLowerCase();

                            const filename =
                                cleanFilename(
                                    document.filename
                                ).toLowerCase();

                            return (
                                title.includes(
                                    query
                                ) ||
                                filename.includes(
                                    query
                                )
                            );
                        }
                    );
                }
            }

            return deduplicateDocuments(result);
        }, [
            documents,
            searchMode,
            searchQuery,
            semanticDocuments,
        ]);

    /* ---------------------------------------------------------------------- */
    /* Pagination                                                             */
    /* ---------------------------------------------------------------------- */

    const totalDocPages = Math.max(1, Math.ceil(filteredDocuments.length / DOCS_PER_PAGE));

    useEffect(() => {
        setDocPage(1);
    }, [searchQuery, searchMode, documents.length]);

    const paginatedDocuments = useMemo(() => {
        const start = (docPage - 1) * DOCS_PER_PAGE;
        return filteredDocuments.slice(start, start + DOCS_PER_PAGE);
    }, [filteredDocuments, docPage]);

    /* ---------------------------------------------------------------------- */
    /* Document actions                                                       */
    /* ---------------------------------------------------------------------- */

    const openDocument =
        useCallback(
            (document) => {
                setSelectedDocument(
                    document
                );
                setPreviewUrl("");
            },
            []
        );

    const closeDocument =
        useCallback(() => {
            setSelectedDocument(
                null
            );
            setPreviewUrl("");
        }, []);

    const closePreview =
        useCallback(() => {
            setPreviewUrl("");
        }, []);

    /* ---------------------------------------------------------------------- */
    /* Delete                                                                  */
    /* ---------------------------------------------------------------------- */

    const confirmDeleteDocument =
        useCallback(
            (document) => {
                setDeleteError("");

                setDocumentToDelete(
                    document
                );
            },
            []
        );

    const cancelDeleteDocument =
        useCallback(() => {
            if (isDeleting) {
                return;
            }

            setDocumentToDelete(
                null
            );

            setDeleteError("");
        }, [isDeleting]);

    const handleDeleteDocument =
        useCallback(async (docArg = null) => {
            const doc = (docArg && docArg.file_id) ? docArg : documentToDelete;
            if (!doc?.file_id) {
                return;
            }

            const fileId = doc.file_id;
            const filename = doc.filename || "document";

            // Prevent duplicate delete requests
            if (deletingFileIds.has(fileId)) {
                return;
            }

            // Immediately close the confirmation modal & clear state
            setDocumentToDelete(null);
            setDeleteError("");

            // Mark as deleting
            setDeletingFileIds((prev) => {
                const next = new Set(prev);
                next.add(fileId);
                return next;
            });

            // Keep backups for rollback
            const originalDoc = { ...doc };
            let originalIndex = -1;
            let originalSemanticIndex = -1;

            // Remove immediately from documents lists (optimistic update)
            setDocuments((current) => {
                originalIndex = current.findIndex((d) => d.file_id === fileId);
                return current.filter((d) => d.file_id !== fileId);
            });

            setSemanticDocuments((current) => {
                originalSemanticIndex = current.findIndex((d) => d.file_id === fileId);
                return current.filter((d) => d.file_id !== fileId);
            });

            // Close selected/preview if it was the deleted one
            if (selectedDocument?.file_id === fileId) {
                setSelectedDocument(null);
                setPreviewUrl("");
            }

            // Add deleting toast
            addToast(t("docs.deletingProgress", "Deleting \"{name}\"...").replace("{name}", cleanFilename(filename)), "deleting", fileId, filename);

            // Asynchronously run server deletion in the background
            try {
                await deleteDocumentOnServer(fileId);
                
                // Remove deleting toast and add success toast
                removeToastByFileId(fileId, "deleting");
                addToast(t("docs.deletedSuccess", "\"{name}\" deleted successfully.").replace("{name}", cleanFilename(filename)), "success", fileId, filename);
                
                // Cleanup deleting file ID
                setDeletingFileIds((prev) => {
                    const next = new Set(prev);
                    next.delete(fileId);
                    return next;
                });
            } catch (err) {
                // Rollback on failure
                const errorMessage = err?.message || t("docs.deleteError");
                
                // Restore document to original position
                setDocuments((current) => {
                    if (current.some((d) => d.file_id === fileId)) {
                        return current;
                    }
                    const next = [...current];
                    if (originalIndex >= 0 && originalIndex <= next.length) {
                        next.splice(originalIndex, 0, originalDoc);
                    } else {
                        next.push(originalDoc);
                    }
                    return next;
                });

                setSemanticDocuments((current) => {
                    if (current.some((d) => d.file_id === fileId)) {
                        return current;
                    }
                    const next = [...current];
                    if (originalSemanticIndex >= 0 && originalSemanticIndex <= next.length) {
                        next.splice(originalSemanticIndex, 0, originalDoc);
                    } else {
                        next.push(originalDoc);
                    }
                    return next;
                });

                // Remove deleting toast, add error toast with retry info
                removeToastByFileId(fileId, "deleting");
                addToast(
                    t("docs.failedToDelete", "Failed to delete \"{name}\": {error}").replace("{name}", cleanFilename(filename)).replace("{error}", errorMessage),
                    "error",
                    fileId,
                    filename,
                    originalDoc
                );

                // Cleanup deleting file ID
                setDeletingFileIds((prev) => {
                    const next = new Set(prev);
                    next.delete(fileId);
                    return next;
                });
            }
        }, [
            documentToDelete,
            selectedDocument,
            deletingFileIds,
            addToast,
            removeToastByFileId
        ]);

    /* ---------------------------------------------------------------------- */
    /* Batch operations                                                        */
    /* ---------------------------------------------------------------------- */

    const toggleBatchSelect = useCallback((fileId) => {
        setBatchSelected((prev) => {
            const next = new Set(prev);
            if (next.has(fileId)) {
                next.delete(fileId);
            } else {
                next.add(fileId);
            }
            return next;
        });
    }, []);

    const selectAllBatch = useCallback(() => {
        setBatchSelected((prev) => {
            if (prev.size === paginatedDocuments.length) {
                return new Set();
            }
            return new Set(paginatedDocuments.map((d) => d.file_id).filter(Boolean));
        });
    }, [paginatedDocuments]);

    const handleBatchDelete = useCallback(async () => {
        if (batchSelected.size === 0 || isBatchDeleting) return;

        const fileIds = [...batchSelected];
        setIsBatchDeleting(true);

        for (const fileId of fileIds) {
            const doc = documents.find((d) => d.file_id === fileId);
            const filename = doc?.filename || "document";

            setDocuments((current) => current.filter((d) => d.file_id !== fileId));
            setSemanticDocuments((current) => current.filter((d) => d.file_id !== fileId));
            addToast(t("docs.deletingProgress", "Deleting \"{name}\"...").replace("{name}", cleanFilename(filename)), "deleting", fileId, filename);

            try {
                await deleteDocumentOnServer(fileId);
                removeToastByFileId(fileId, "deleting");
                addToast(t("docs.deleted", "\"{name}\" deleted.").replace("{name}", cleanFilename(filename)), "success", fileId, filename);
            } catch {
                removeToastByFileId(fileId, "deleting");
                addToast(t("docs.failedToDeleteSimple", "Failed to delete \"{name}\".").replace("{name}", cleanFilename(filename)), "error", fileId, filename);
            }
        }

        setBatchSelected(new Set());
        setIsBatchDeleting(false);
    }, [batchSelected, isBatchDeleting, documents, addToast, removeToastByFileId]);

    const handleReprocess = useCallback(async (doc) => {
        if (!doc?.file_id) return;

        const fileId = doc.file_id;
        const filename = doc.filename || "document";

        addToast(t("docs.reprocessingProgress", "Re-processing \"{name}\"...").replace("{name}", cleanFilename(filename)), "info", fileId, filename);

        try {
            await reprocessDocumentOnServer(fileId);
            addToast(t("docs.queuedForReprocessing", "\"{name}\" queued for re-processing.").replace("{name}", cleanFilename(filename)), "success", fileId, filename);
            refreshDocuments();
        } catch (err) {
            addToast(t("docs.failedToReprocess", "Failed to re-process: {error}").replace("{error}", err.message), "error", fileId, filename);
        }
    }, [addToast, refreshDocuments]);

    /* ---------------------------------------------------------------------- */
    /* Upload                                                                  */
    /* ---------------------------------------------------------------------- */

    const openFilePicker =
        useCallback(() => {
            fileInputRef.current?.click();
        }, []);

    const handleFileSelected =
        useCallback(
            async (event) => {
                const file =
                    event.target.files?.[0];

                event.target.value = "";

                if (!file) {
                    return;
                }

                if (
                    !file.name
                        .toLowerCase()
                        .match(/\.(pdf|docx|doc|pptx|ppt|xlsx|xls|txt|csv)$/i)
                ) {
                    setUploadError(
                        t("docs.unsupportedFileType")
                    );

                    return;
                }

                setIsUploading(true);
                setUploadError("");
                setUploadSuccess("");

                // Optimistic processing document row so processing is shown immediately inline
                const tempId = `temp-${Date.now()}`;
                const optimisticDoc = {
                    file_id: tempId,
                    filename: file.name,
                    file_size: file.size,
                    file_type: file.type || "application/pdf",
                    is_summarized: false,
                    is_vectored: false,
                    isProcessing: true,
                    processingStage: "upload",
                };

                setDocuments((prev) => [optimisticDoc, ...prev]);

                try {
                    const result = await uploadDocumentToServer(
                        file
                    );

                    // Update optimistic doc with actual returned file_id and transition stage
                    if (result?.file_id) {
                        setDocuments((prev) =>
                            prev.map((doc) =>
                                doc.file_id === tempId
                                    ? {
                                          ...doc,
                                          file_id: result.file_id,
                                          filename: result.filename || doc.filename,
                                          processingStage: "extract",
                                      }
                                    : doc
                            )
                        );
                    }

                    setUploadSuccess(
                        t("docs.uploadedProcessing")
                    );

                    await refreshDocuments();
                } catch (uploadErr) {
                    // Remove optimistic document on failure
                    setDocuments((prev) => prev.filter((doc) => doc.file_id !== tempId));
                    setUploadError(
                        uploadErr?.message ||
                            t("docs.uploadError")
                    );
                } finally {
                    setIsUploading(false);
                }
            },
            [refreshDocuments]
        );

    /* ---------------------------------------------------------------------- */
    /* Drag and drop                                                           */
    /* ---------------------------------------------------------------------- */

    const handleDragOver = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback(
        async (e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragging(false);

            const files = Array.from(e.dataTransfer.files);
            if (files.length === 0) return;

            for (const file of files) {
                if (
                    !file.name
                        .toLowerCase()
                        .match(/\.(pdf|docx|doc|pptx|ppt|xlsx|xls|txt|csv)$/i)
                ) {
                    setUploadError(
                        t("docs.unsupportedFileType")
                    );
                    continue;
                }

                setIsUploading(true);
                setUploadError("");
                setUploadSuccess("");

                const tempId = `temp-${Date.now()}-${file.name}`;
                const optimisticDoc = {
                    file_id: tempId,
                    filename: file.name,
                    file_size: file.size,
                    file_type: file.type || "application/pdf",
                    is_summarized: false,
                    is_vectored: false,
                    isProcessing: true,
                    processingStage: "upload",
                };

                setDocuments((prev) => [optimisticDoc, ...prev]);

                try {
                    const result = await uploadDocumentToServer(file);

                    if (result?.file_id) {
                        setDocuments((prev) =>
                            prev.map((doc) =>
                                doc.file_id === tempId
                                    ? {
                                          ...doc,
                                          file_id: result.file_id,
                                          filename: result.filename || doc.filename,
                                          processingStage: "extract",
                                      }
                                    : doc
                            )
                        );
                    }

                    setUploadSuccess(
                        t("docs.uploadedProcessing")
                    );

                    await refreshDocuments();
                } catch (uploadErr) {
                    setDocuments((prev) => prev.filter((doc) => doc.file_id !== tempId));
                    setUploadError(
                        uploadErr?.message ||
                            t("docs.uploadError")
                    );
                } finally {
                    setIsUploading(false);
                }
            }
        },
        [refreshDocuments]
    );

    /* ---------------------------------------------------------------------- */
    /* Semantic search                                                        */
    /* ---------------------------------------------------------------------- */

    const handleSearchSubmit =
        useCallback(
            async (event) => {
                event.preventDefault();

                if (
                    searchMode !==
                    "semantic"
                ) {
                    return;
                }

                const query =
                    searchQuery.trim();

                if (!query) {
                    setSemanticDocuments(
                        []
                    );

                    setSemanticError(
                        ""
                    );

                    return;
                }

                setIsSemanticLoading(
                    true
                );

                setSemanticError("");

                try {
                    const results =
                        await fetchSemanticDocuments(
                            query
                        );

                    setSemanticDocuments(
                        results
                    );

                    setSelectedDocument(
                        results[0] ||
                            null
                    );

                    setPreviewUrl("");
                } catch (searchError) {
                    setSemanticDocuments(
                        []
                    );

                    setSemanticError(
                        searchError?.message ||
                            "Unable to search documents."
                    );
                } finally {
                    setIsSemanticLoading(
                        false
                    );
                }
            },
            [
                searchMode,
                searchQuery,
            ]
        );

    /* ---------------------------------------------------------------------- */
    /* Render                                                                  */
    /* ---------------------------------------------------------------------- */

    return (
        <div
            className="flex h-full min-h-0 w-full overflow-hidden rounded-2xl border border-border bg-background shadow-2xl relative"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {isDragging && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 z-50 flex items-center justify-center bg-primary/5 backdrop-blur-sm border-2 border-dashed border-primary rounded-xl"
                >
                    <div className="flex flex-col items-center gap-3">
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ type: "spring", stiffness: 300, damping: 20 }}
                        >
                            <Upload size={48} className="text-primary" />
                        </motion.div>
                        <p className="text-lg font-semibold text-primary">Drop files here to upload</p>
                        <p className="text-sm text-muted-foreground">PDF, DOCX, PPTX, XLSX, TXT, CSV</p>
                    </div>
                </motion.div>
            )}
            {!authUser ? (
                <div className="flex h-full min-h-0 w-full items-center justify-center">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2
                            size={18}
                            className="animate-spin text-primary"
                        />

                        {t("docs.loadingSession")}
                    </div>
                </div>
            ) : (
                <section className="flex min-w-0 flex-1 flex-col">
                {/* Header */}

                <header className="flex flex-col gap-4 border-b border-border bg-card/70 px-6 py-5">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                            <div>
                                <h2 className="text-lg font-bold text-foreground">
                                    {t("docs.title")}
                                </h2>

                                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                    {documents.length === 1
                                        ? t("docs.documentCountSingular", "{count} document ready").replace("{count}", documents.length)
                                        : t("docs.documentCount", "{count} documents ready").replace("{count}", documents.length)
                                    }
                                    <HelpTooltip content="Documents that have been uploaded and fully processed (extracted, indexed, and summarized) are ready for search and chat." />
                                </p>
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                                <button
                                    type="button"
                                    onClick={
                                        openFilePicker
                                    }
                                    disabled={
                                        isUploading
                                    }
                                    className="flex h-9 items-center gap-2 rounded-lg bg-primary px-3 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    {isUploading ? (
                                        <Loader2
                                            size={
                                                14
                                            }
                                            className="animate-spin"
                                        />
                                    ) : (
                                        <Upload
                                            size={
                                                14
                                            }
                                        />
                                    )}

                                    {isUploading
                                        ? t("docs.uploading")
                                        : t("docs.upload")}
                                </button>

                            <input
                                ref={
                                    fileInputRef
                                }
                                type="file"
                                accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.txt,.csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/plain,text/csv"
                                onChange={
                                    handleFileSelected
                                }
                                className="hidden"
                            />

                            <button
                                type="button"
                                onClick={
                                    refreshDocuments
                                }
                                disabled={
                                    isLoading
                                }
                                    className="flex h-9 items-center gap-2 rounded-lg border border-border bg-background px-3 text-xs font-semibold text-muted-foreground transition hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                <RefreshCw
                                    size={
                                        14
                                    }
                                    className={
                                        isLoading
                                            ? "animate-spin"
                                            : ""
                                    }
                                />

                                {t("docs.refresh")}
                            </button>

                            <div className="flex h-9 rounded-lg border border-border bg-background p-1">
                                <button
                                    type="button"
                                    title={t("docs.rowView")}
                                    onClick={() =>
                                        setViewMode(
                                            "row"
                                        )
                                    }
                                    className={`flex h-7 w-8 items-center justify-center rounded-md transition ${
                                        viewMode ===
                                        "row"
                                            ? "bg-primary text-primary-foreground"
                                            : "text-muted-foreground hover:text-foreground"
                                    }`}
                                >
                                    <List
                                        size={
                                            15
                                        }
                                    />
                                </button>

                                <button
                                    type="button"
                                    title={t("docs.gridView")}
                                    onClick={() =>
                                        setViewMode(
                                            "grid"
                                        )
                                    }
                                    className={`flex h-7 w-8 items-center justify-center rounded-md transition ${
                                        viewMode ===
                                        "grid"
                                            ? "bg-primary text-primary-foreground"
                                            : "text-muted-foreground hover:text-foreground"
                                    }`}
                                >
                                    <Grid3X3
                                        size={
                                            14
                                        }
                                    />
                                </button>
                            </div>

                            <button
                                type="button"
                                onClick={() => {
                                    if (batchSelected.size > 0) {
                                        handleBatchDelete();
                                    } else {
                                        selectAllBatch();
                                    }
                                }}
                                disabled={isBatchDeleting}
                                className={`flex h-9 items-center gap-1.5 rounded-lg border px-3 text-xs font-semibold transition ${
                                    batchSelected.size > 0
                                        ? "border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20"
                                        : "border-border bg-background text-muted-foreground hover:text-foreground"
                                } disabled:opacity-50`}
                            >
                                {isBatchDeleting ? (
                                    <Loader2 size={13} className="animate-spin" />
                                ) : null}
                                {batchSelected.size > 0
                                    ? `${t("docs.delete")} (${batchSelected.size})`
                                    : t("docs.select")
                                }
                            </button>
                        </div>
                    </div>

                    {/* Search */}

                    <form
                        onSubmit={
                            handleSearchSubmit
                        }
                        className="flex max-w-3xl flex-col gap-2 lg:flex-row lg:items-center"
                    >
                        <div className="flex h-10 shrink-0 rounded-lg border border-border bg-background p-1">
                            <button
                                type="button"
                                onClick={() => {
                                    setSearchMode(
                                        "normal"
                                    );

                                    setSemanticError(
                                        ""
                                    );

                                    setSemanticDocuments(
                                        []
                                    );
                                }}
                                className={`flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold transition ${
                                    searchMode ===
                                    "normal"
                                        ? "bg-primary text-primary-foreground"
                                        : "text-muted-foreground hover:text-foreground"
                                }`}
                            >
                                <Search
                                    size={
                                        13
                                    }
                                />

                                {t("docs.searchModeNormal")}
                            </button>

                            <button
                                type="button"
                                onClick={() =>
                                    setSearchMode(
                                        "semantic"
                                    )
                                }
                                className={`flex h-8 items-center gap-1.5 rounded-md px-3 text-xs font-semibold transition ${
                                    searchMode ===
                                    "semantic"
                                        ? "bg-primary text-primary-foreground"
                                        : "text-muted-foreground hover:text-foreground"
                                }`}
                            >
                                {t("docs.searchModeSemantic")}
                            </button>
                        </div>

                            <div className="relative min-w-0 flex-1">
                            <Search
                                size={15}
                                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                            />

                            <input
                                ref={searchInputRef}
                                value={
                                    searchQuery
                                }
                                onChange={(
                                    event
                                ) => {
                                    setSearchQuery(
                                        event
                                            .target
                                            .value
                                    );

                                    if (
                                        searchMode ===
                                        "normal"
                                    ) {
                                        setSemanticDocuments(
                                            []
                                        );

                                        setSemanticError(
                                            ""
                                        );
                                    }
                                }}
                                placeholder={
                                    searchMode ===
                                    "semantic"
                                        ? t("docs.searchPlaceholderSemantic")
                                        : t("docs.searchPlaceholderNormal")
                                }
                                className="h-10 w-full rounded-lg border border-border bg-background px-9 pr-20 text-sm text-foreground placeholder-muted-foreground outline-none transition focus:border-primary"
                            />

                            {searchQuery && (
                                <button
                                    type="button"
                                    onClick={() => {
                                        setSearchQuery(
                                            ""
                                        );

                                        setSemanticDocuments(
                                            []
                                        );

                                        setSemanticError(
                                            ""
                                        );
                                    }}
                                    className="absolute right-12 top-1/2 -translate-y-1/2 text-muted-foreground transition hover:text-foreground"
                                >
                                    <X
                                        size={
                                            14
                                        }
                                    />
                                </button>
                            )}

                            <button
                                type="submit"
                                disabled={
                                    searchMode !==
                                        "semantic" ||
                                    !searchQuery.trim() ||
                                    isSemanticLoading
                                }
                                className="absolute right-1 top-1/2 flex h-8 w-9 -translate-y-1/2 items-center justify-center rounded-md bg-primary text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
                                title={t("docs.runSemanticSearch")}
                            >
                                <Loader2
                                    size={
                                        14
                                    }
                                    className={isSemanticLoading ? "animate-spin" : "opacity-0"}
                                />
                            </button>
                        </div>
                    </form>

                    <AnimatePresence>
                        {semanticError && (
                            <motion.p
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="text-xs text-destructive font-medium"
                            >
                                {semanticError}
                            </motion.p>
                        )}

                        {uploadError && (
                            <motion.p
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="text-xs text-destructive font-medium"
                            >
                                {uploadError}
                            </motion.p>
                        )}

                        {uploadSuccess && (
                            <motion.p
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="text-xs text-emerald-600 font-medium"
                            >
                                {uploadSuccess}
                            </motion.p>
                        )}
                    </AnimatePresence>
                </header>

                {/* Document list */}

                <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                    {isLoading ? (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between pb-2">
                                <Skeleton className="h-4 w-36" />
                                <Skeleton className="h-4 w-20" />
                            </div>
                            {viewMode === "row" ? (
                                <div className="space-y-2.5">
                                    {[...Array(5)].map((_, i) => (
                                        <div
                                            key={i}
                                            className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-card/50 p-4"
                                        >
                                            <div className="flex items-center gap-3 flex-1 min-w-0">
                                                <Skeleton className="h-10 w-10 shrink-0 rounded-xl" />
                                                <div className="space-y-2 flex-1 min-w-0">
                                                    <Skeleton className="h-4 w-2/5" />
                                                    <Skeleton className="h-3 w-1/4" />
                                                </div>
                                            </div>
                                            <Skeleton className="h-7 w-20 rounded-full shrink-0" />
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                                    {[...Array(6)].map((_, i) => (
                                        <CardSkeleton
                                            key={i}
                                            className="border-border bg-card/50"
                                        />
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : error ? (
                        <div className="flex h-full items-center justify-center">
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95 }}
                                animate={{ opacity: 1, scale: 1 }}
                                className="max-w-sm rounded-2xl border border-destructive/30 bg-destructive/10 p-5 text-center shadow-sm"
                            >
                                <AlertTriangle className="mx-auto mb-2 text-destructive" size={24} />
                                <p className="text-sm font-semibold text-destructive">{t("docs.failedToLoad")}</p>
                                <p className="mt-1 text-xs text-muted-foreground">{error}</p>
                                <button
                                    type="button"
                                    onClick={refreshDocuments}
                                    className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90"
                                >
                                    <RefreshCw size={12} />
                                    {t("docs.tryAgain")}
                                </button>
                            </motion.div>
                        </div>
                    ) : isSemanticLoading ? (
                        <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                            <Loader2
                                size={24}
                                className="animate-spin text-primary"
                            />
                            <div>
                                <p className="text-sm font-semibold text-foreground">{t("docs.searchingSemantic")}</p>
                                <p className="mt-1 text-xs text-muted-foreground">{t("docs.scanningEmbeddings")}</p>
                            </div>
                        </div>
                    ) : filteredDocuments.length ===
                      0 ? (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="flex h-full flex-col items-center justify-center gap-3 text-center p-8"
                        >
                            <div className="grid h-14 w-14 place-items-center rounded-2xl border border-border bg-card/80 text-muted-foreground">
                                <FileText
                                    size={28}
                                />
                            </div>

                            <div className="max-w-xs">
                                <p className="text-sm font-semibold text-foreground">
                                    {searchMode ===
                                        "semantic" &&
                                    searchQuery.trim()
                                        ? t("docs.noSemanticMatches")
                                        : t("docs.emptyNoDocuments")}
                                </p>

                                <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                                    {searchMode ===
                                        "semantic" &&
                                    searchQuery.trim()
                                        ? t("docs.tryDifferentPhrase")
                                        : t("docs.emptyUploadPrompt")}
                                </p>
                            </div>

                            {searchMode === "normal" && !searchQuery.trim() && (
                                <button
                                    type="button"
                                    onClick={openFilePicker}
                                    className="mt-2 flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90"
                                >
                                    <Upload size={14} />
                                    {t("docs.upload")}
                                </button>
                            )}
                        </motion.div>
                    ) : viewMode ===
                      "row" ? (
                        <div className="space-y-2">
                            <AnimatePresence mode="popLayout">
                                {paginatedDocuments.map(
                                    (
                                        document,
                                        index
                                    ) => (
                                        <motion.div
                                            key={
                                                document.file_id ||
                                                `doc-row-${index}`
                                            }
                                            initial={{ opacity: 0, y: 8 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            exit={{ opacity: 0, y: -8, scale: 0.95 }}
                                            transition={{ duration: 0.2 }}
                                            className="flex items-center gap-2"
                                        >
                                            <input
                                                type="checkbox"
                                                checked={batchSelected.has(document.file_id)}
                                                onChange={() => toggleBatchSelect(document.file_id)}
                                                onClick={(e) => e.stopPropagation()}
                                                className="h-4 w-4 shrink-0 rounded border-border bg-background text-primary focus:ring-primary"
                                            />
                                            <div className="flex-1 min-w-0">
                                            <DocumentRow
                                                document={
                                                    document
                                                }
                                                isSelected={
                                                    selectedDocument?.file_id ===
                                                    document.file_id
                                                }
                                                onOpen={() =>
                                                    openDocument(
                                                        document
                                                    )
                                                }
                                                onDelete={
                                                    confirmDeleteDocument
                                                }
                                            />
                                            </div>
                                            {isDocumentProcessing(document) && (
                                                <button
                                                    type="button"
                                                    title={t("docs.reprocessDocumentTooltip")}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleReprocess(document);
                                                    }}
                                                    className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:bg-card hover:text-primary transition-colors"
                                                >
                                                    <RefreshCw size={14} />
                                                </button>
                                            )}
                                        </motion.div>
                                    )
                                )}
                            </AnimatePresence>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                            <AnimatePresence mode="popLayout">
                                {paginatedDocuments.map(
                                    (
                                        document,
                                        index
                                    ) => {
                                        const docType = (document.filename || "").split(".").pop()?.toUpperCase() || "PDF";
                                        const deadLinesCount = parseTimeline(document.timeline_json).length;
                                        const metaText = `${cleanFilename(document.filename)} · ${formatBytes(document.file_size)}${deadLinesCount > 0 ? ` · ${deadLinesCount} ${deadLinesCount > 1 ? t("docs.deadlineCountPlural", "{count} deadlines").replace("{count}", deadLinesCount) : t("docs.deadlineCount", "{count} deadline").replace("{count}", deadLinesCount)}` : ''}`;
                                        const isProc = isDocumentProcessing(document);
                                        const procStage = document.processingStage || "upload";
                                        const docStatus = isProc ? "processing" : "processed";

                                        return (
                                            <motion.div
                                                key={
                                                    document.file_id ||
                                                    `doc-tile-${index}`
                                                }
                                                initial={{ opacity: 0, scale: 0.96 }}
                                                animate={{ opacity: 1, scale: 1 }}
                                                exit={{ opacity: 0, scale: 0.9, y: 10 }}
                                                transition={{ duration: 0.2 }}
                                            >
                                                <DocumentCard
                                                    name={documentTitle(document)}
                                                    type={docType}
                                                    meta={metaText}
                                                    status={docStatus}
                                                    processingStage={procStage}
                                                    onClick={() => openDocument(document)}
                                                    onAction={() => confirmDeleteDocument(document)}
                                                        className={`cursor-pointer transition-all ${
                                                        selectedDocument?.file_id === document.file_id
                                                            ? "ring-2 ring-primary/80 border-primary/50"
                                                            : ""
                                                    }`}
                                                />
                                            </motion.div>
                                        );
                                    }
                                )}
                            </AnimatePresence>
                        </div>
                    )}

                    {filteredDocuments.length > DOCS_PER_PAGE && (
                        <div className="flex items-center justify-center gap-2 pt-4">
                            <button
                                type="button"
                                onClick={() => setDocPage((p) => Math.max(1, p - 1))}
                                disabled={docPage === 1}
                                className="rounded-lg px-3 py-1.5 text-xs font-medium text-foreground border border-border hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                                {t("docs.previous")}
                            </button>
                            <span className="text-xs text-muted-foreground">
                                {t("docs.pageOf", "Page {current} of {total}").replace("{current}", docPage).replace("{total}", totalDocPages)}
                            </span>
                            <button
                                type="button"
                                onClick={() => setDocPage((p) => Math.min(totalDocPages, p + 1))}
                                disabled={docPage === totalDocPages}
                                className="rounded-lg px-3 py-1.5 text-xs font-medium text-foreground border border-border hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                            >
                                {t("docs.next")}
                            </button>
                        </div>
                    )}
                </div>
            </section>
            )}

            {selectedDocument && (
                <DocumentDetails
                    document={
                        selectedDocument
                    }
                    onPreview={() =>
                        setPreviewUrl(
                            selectedDocument.file_url ||
                                ""
                        )
                    }
                    onClose={
                        closeDocument
                    }
                    onDelete={
                        confirmDeleteDocument
                    }
                />
            )}

            {previewUrl &&
                selectedDocument && (
                    <PdfPreviewModal
                        document={
                            selectedDocument
                        }
                        previewUrl={
                            previewUrl
                        }
                        onClose={
                            closePreview
                        }
                    />
                )}

            {documentToDelete && (
                <DeleteDocumentModal
                    document={
                        documentToDelete
                    }
                    isDeleting={
                        isDeleting
                    }
                    error={
                        deleteError
                    }
                    onCancel={
                        cancelDeleteDocument
                    }
                    onConfirm={
                        handleDeleteDocument
                    }
                />
            )}

            <ToastContainer
                toasts={toasts}
                onRemove={removeToast}
                onRetry={handleDeleteDocument}
            />
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Document row                                                               */
/* -------------------------------------------------------------------------- */

function DocumentRow({
    document,
    isSelected,
    onOpen,
    onDelete,
}) {
    const { t } = useI18n();
    const deadlines =
        parseTimeline(
            document.timeline_json
        );

    // null = fully processed (show ✓ Processed badge); string = active pipeline stage key
    const processingStage = useDocumentPipelineStage(document);
    const isShowingPipeline = processingStage !== null;

    return (
        <div
            role="button"
            tabIndex={0}
            onClick={onOpen}
            onKeyDown={(
                event
            ) => {
                if (
                    event.key ===
                        "Enter" ||
                    event.key ===
                        " "
                ) {
                    event.preventDefault();
                    onOpen();
                }
            }}
            className={`grid w-full cursor-pointer grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-xl border p-2.5 sm:p-3 text-left transition ${
                isSelected
                    ? "border-primary/50 bg-primary/10"
                    : "border-border bg-card/55 hover:border-primary/70 hover:bg-card"
            }`}
        >
            <div className="flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-lg border border-border bg-background text-primary shrink-0">
                <FileText
                    size={17}
                />
            </div>

            <div className="min-w-0 pr-2">
                <p className="truncate text-xs sm:text-sm font-semibold text-foreground">
                    {documentTitle(
                        document
                    )}
                </p>

                <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    {cleanFilename(
                        document.filename
                    )}{" "}
                    ·{" "}
                    {formatBytes(
                        document.file_size
                    )}
                </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
                {/* Inline Processing Pipeline or Collapsed Processed Status */}
                {isShowingPipeline ? (
                    <ProcessingPipeline
                        active={processingStage}
                        compact={true}
                    />
                ) : (
                    <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-emerald-500/20 bg-emerald-500/10 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                        <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">✓</span>
                        {t("docs.processedBadge")}
                    </span>
                )}

                {deadlines.length >
                    0 && (
                    <span className="flex h-7 sm:h-8 items-center gap-1.5 rounded-lg border border-amber-500/50 bg-amber-500/20 px-2 text-xs font-bold text-amber-700 dark:text-amber-300">
                        <AlertTriangle
                            size={
                                13
                            }
                        />

                        {
                            deadlines.length
                        }
                    </span>
                )}

                <button
                    type="button"
                    title={t("docs.deleteDocumentTooltip")}
                    onClick={(
                        event
                    ) => {
                        event.stopPropagation();

                        onDelete(
                            document
                        );
                    }}
                    className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-lg bg-background text-muted-foreground transition hover:bg-destructive/20 hover:text-destructive"
                >
                    <Trash2
                        size={14}
                    />
                </button>

                <span className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-lg bg-background text-muted-foreground">
                    <Eye
                        size={14}
                    />
                </span>
            </div>
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Document tile                                                              */
/* -------------------------------------------------------------------------- */

function DocumentTile({
    document,
    isSelected,
    onOpen,
    onDelete,
}) {
    const { t } = useI18n();
    const deadlines =
        parseTimeline(
            document.timeline_json
        );

    return (
        <div
            className={`flex aspect-[4/3] min-h-44 flex-col justify-between rounded-xl border p-4 text-left transition ${
                isSelected
                    ? "border-primary/50 bg-primary/10"
                    : "border-border bg-card/55 hover:border-primary/70 hover:bg-card"
            }`}
        >
            <div className="flex items-start justify-between gap-3">
                <button
                    type="button"
                    onClick={
                        onOpen
                    }
                    className="flex h-20 w-20 items-center justify-center rounded-xl border border-border bg-background text-primary shadow-sm"
                >
                    <FileText
                        size={46}
                        strokeWidth={
                            1.6
                        }
                    />
                </button>

                <div className="flex flex-col items-end gap-2">
                    {deadlines.length >
                        0 && (
                        <span className="flex h-7 items-center gap-1 rounded-lg border border-amber-500/50 bg-amber-500/20 px-2 text-xs font-bold text-amber-700 dark:text-amber-300">
                            <AlertTriangle
                                size={
                                    12
                                }
                            />

                            {
                                deadlines.length
                            }
                        </span>
                    )}

                    <button
                        type="button"
                        title={t("docs.deleteDocumentTooltip")}
                        onClick={(
                            event
                        ) => {
                            event.stopPropagation();

                            onDelete(
                                document
                            );
                        }}
                        className="flex h-7 w-7 items-center justify-center rounded-lg bg-background text-muted-foreground transition hover:bg-destructive/20 hover:text-destructive"
                    >
                        <Trash2
                            size={
                                13
                            }
                        />
                    </button>
                </div>
            </div>

            <div className="min-w-0">
                <button
                    type="button"
                    onClick={
                        onOpen
                    }
                    className="block w-full text-left"
                >
                    <p className="line-clamp-2 text-sm font-semibold leading-snug text-foreground">
                        {documentTitle(
                            document
                        )}
                    </p>
                </button>

                <p className="mt-2 truncate text-xs text-muted-foreground">
                    {cleanFilename(
                        document.filename
                    )}
                </p>

                <p className="mt-1 text-xs text-muted-foreground/60">
                    {formatBytes(
                        document.file_size
                    )}
                </p>
            </div>
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Document details                                                           */
/* -------------------------------------------------------------------------- */

function DocumentDetails({
    document,
    onPreview,
    onClose,
    onDelete,
}) {
    const { t } = useI18n();
    const deadlines =
        parseTimeline(
            document.timeline_json
        );

    return (
        <div className="fixed inset-0 z-50 bg-black/50 md:static md:z-auto md:bg-transparent">
            <aside className="flex h-full w-full flex-col border-l border-border bg-background md:w-[420px] md:bg-card">
                <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
                    <div className="min-w-0">
                        <p className="text-[11px] font-semibold uppercase text-muted-foreground">
                            {t("docs.documentDetails")}
                        </p>

                        <h3 className="mt-1 line-clamp-2 text-base font-bold leading-snug text-foreground">
                            {documentTitle(
                                document
                            )}
                        </h3>

                        <p className="mt-1 truncate text-xs text-muted-foreground">
                            {cleanFilename(
                                document.filename
                            )}
                        </p>
                    </div>

                    <div className="flex shrink-0 items-center gap-1">
                        <button
                            type="button"
                            title={t("docs.deleteDocumentTooltip")}
                            onClick={() =>
                                onDelete(
                                    document
                                )
                            }
                            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-destructive/20 hover:text-destructive"
                        >
                            <Trash2
                                size={
                                    16
                                }
                            />
                        </button>

                        <button
                            type="button"
                            title={t("docs.closeTooltip")}
                            onClick={
                                onClose
                            }
                            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                        >
                            <X
                                size={16}
                            />
                        </button>
                    </div>
                </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
                {deadlines.length >
                    0 && (
                    <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-500/50 bg-amber-500/20 px-3 py-2 text-xs font-semibold text-amber-700 dark:text-amber-300">
                        <AlertTriangle
                            size={
                                15
                            }
                            className="mt-0.5 shrink-0 text-amber-600"
                        />

                        <span>
                            {t("docs.importantDeadlinesPresent")}
                        </span>
                    </div>
                )}

                <section>
                    <h4 className="text-xs font-bold uppercase text-muted-foreground">
                        {t("docs.summary")}
                    </h4>

                    <p className="mt-2 text-sm leading-6 text-foreground">
                        {document.summarization ||
                            t("docs.noSummaryAvailable")}
                    </p>
                </section>

                <section className="mt-6">
                    <div className="flex items-center justify-between gap-2">
                        <h4 className="text-xs font-bold uppercase text-muted-foreground">
                            {t("docs.importantDeadlines")}
                        </h4>

                        <CalendarClock
                            size={
                                15
                            }
                            className="text-primary"
                        />
                    </div>

                    {deadlines.length >
                    0 ? (
                        <ol className="mt-3 space-y-3">
                            {deadlines.map(
                                (
                                    item,
                                    index
                                ) => (
                                    <li
                                        key={`${item.date}-${item.event}-${index}`}
                                        className="grid grid-cols-[auto_minmax(0,1fr)] gap-3"
                                    >
                                        <div className="flex flex-col items-center">
                                            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />

                                            {index <
                                                deadlines.length -
                                                    1 && (
                                                <span className="mt-1 h-full min-h-10 w-px bg-border" />
                                            )}
                                        </div>

                                        <div className="pb-1">
                                            <p className="inline-flex rounded-md bg-amber-500/20 px-2 py-1 text-xs font-bold text-amber-700 dark:text-amber-300">
                                                {item.date ||
                                                    t("docs.dateNotSpecified")}
                                            </p>

                                            <p className="mt-1 text-sm leading-5 text-foreground">
                                                {item.event ||
                                                    t("docs.eventNotSpecified")}
                                            </p>
                                        </div>
                                    </li>
                                )
                            )}
                        </ol>
                    ) : (
                        <p className="mt-2 text-sm text-muted-foreground">
                            {t("docs.noDeadlinesExtracted")}
                        </p>
                    )}
                </section>

                <section className="mt-6">
                    <button
                        type="button"
                        onClick={
                            onPreview
                        }
                        disabled={
                            !document.file_url
                        }
                        className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <Eye
                            size={
                                16
                            }
                        />

                        {t("docs.viewPdf")}
                    </button>
                </section>
            </div>
        </aside>
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* PDF preview                                                                */
/* -------------------------------------------------------------------------- */

function PdfPreviewModal({
    document,
    previewUrl,
    onClose,
}) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
            <div className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
                <div className="flex shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-5 py-3">
                    <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">
                            {documentTitle(
                                document
                            )}
                        </p>

                        <p className="truncate text-xs text-muted-foreground">
                            {cleanFilename(
                                document.filename
                            )}
                        </p>
                    </div>

                    <button
                        type="button"
                        onClick={
                            onClose
                        }
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                    >
                        <X
                            size={18}
                        />
                    </button>
                </div>

                <div className="min-h-0 flex-1 bg-card">
                    <iframe
                        title={documentTitle(
                            document
                        )}
                        src={
                            previewUrl
                        }
                        className="h-full w-full border-0"
                    />
                </div>
            </div>
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Delete modal                                                               */
/* -------------------------------------------------------------------------- */

function DeleteDocumentModal({
    document,
    isDeleting,
    error,
    onCancel,
    onConfirm,
}) {
    const { t } = useI18n();
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="w-full max-w-md overflow-hidden rounded-2xl border border-border bg-background shadow-2xl">
                <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
                    <div>
                        <h3 className="text-base font-bold text-foreground">
                            {t("docs.deleteModalTitle")}
                        </h3>

                        <p className="mt-1 text-xs text-muted-foreground">
                            {documentTitle(
                                document
                            )}{" "}
                            ·{" "}
                            {cleanFilename(
                                document.filename
                            )}
                        </p>
                    </div>

                    <button
                        type="button"
                        onClick={
                            onCancel
                        }
                        disabled={
                            isDeleting
                        }
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        <X
                            size={16}
                        />
                    </button>
                </div>

                <div className="px-5 py-4">
                    <p className="text-sm leading-6 text-foreground">
                        {t("docs.deleteModalDescription")}
                    </p>

                    {error && (
                        <p className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                            {error}
                        </p>
                    )}

                    <div className="mt-5 flex items-center justify-end gap-2">
                        <button
                            type="button"
                            onClick={
                                onCancel
                            }
                            disabled={
                                isDeleting
                            }
                            className="flex h-9 items-center rounded-lg border border-border bg-background px-4 text-xs font-semibold text-muted-foreground transition hover:border-border hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {t("docs.cancel")}
                        </button>

                        <button
                            type="button"
                            onClick={
                                onConfirm
                            }
                            disabled={
                                isDeleting
                            }
                            className="flex h-9 items-center gap-2 rounded-lg bg-destructive px-4 text-xs font-semibold text-white transition hover:bg-destructive/90 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {isDeleting && (
                                <Loader2
                                    size={
                                        13
                                    }
                                    className="animate-spin"
                                />
                            )}

                            {isDeleting
                                ? t("docs.deleting")
                                : t("docs.delete")}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Toast Container & Toasts (21st.dev inspired style)                         */
/* -------------------------------------------------------------------------- */

function ToastContainer({ toasts, onRemove, onRetry }) {
    return (
        <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-3 w-full max-w-sm pointer-events-none">
            <AnimatePresence>
                {toasts.map((toast) => (
                    <motion.div
                        key={toast.id}
                        initial={{ opacity: 0, y: 20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -20, scale: 0.95 }}
                        transition={{ type: "spring", stiffness: 350, damping: 25 }}
                        className="pointer-events-auto flex w-full flex-col overflow-hidden rounded-xl border border-border bg-background/90 shadow-2xl backdrop-blur-md transition-all duration-300"
                    >
                        <div className="flex items-start gap-3 p-4">
                            <div className="shrink-0 mt-0.5">
                                {toast.type === "deleting" && (
                                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                )}
                                {toast.type === "success" && (
                                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                                )}
                                {toast.type === "error" && (
                                    <AlertCircle className="h-4 w-4 text-destructive" />
                                )}
                                {toast.type === "info" && (
                                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                                )}
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium text-foreground leading-normal break-words">
                                    {toast.message}
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => onRemove(toast.id)}
                                className="shrink-0 rounded-lg p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                            >
                                <X size={14} />
                            </button>
                        </div>
                        {toast.type === "error" && toast.errorObj && (
                            <div className="border-t border-border/60 bg-destructive/5 px-4 py-2 flex justify-end">
                                <button
                                    type="button"
                                    onClick={() => {
                                        onRetry(toast.errorObj);
                                        onRemove(toast.id);
                                    }}
                                    className="rounded-lg bg-destructive/20 px-2.5 py-1 text-[11px] font-bold text-destructive hover:bg-destructive/30 transition-colors"
                                >
                                    Retry Deletion
                                </button>
                            </div>
                        )}
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    );
}
