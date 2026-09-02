"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getCurrentSession, fetchDocuments } from "../lib/supabaseAuth";

const STAGES = [
    { key: "uploaded", label: "Uploaded", desc: "Document received and queued" },
    { key: "extracted", label: "Extracted", desc: "Text extracted and cleaned" },
    { key: "summarized", label: "Summarised", desc: "AI summarisation complete" },
    { key: "deadlines", label: "Deadlines", desc: "Dates and deadlines extracted" },
    { key: "embedded", label: "Embedded", desc: "Content embedded for semantic search" },
    { key: "indexed", label: "Indexed", desc: "Vector index built and ready" },
    { key: "processed", label: "Processed", desc: "Document fully ready for query" },
];

function deriveStageStatuses(doc) {
    if (!doc) {
        return STAGES.map((s) => ({ ...s, status: "pending" }));
    }

    const isSummarized = Boolean(doc.is_summarized);
    const isVectored = Boolean(doc.is_vectored);
    const timelineJson = doc.timeline_json || doc.metadata?.timeline_json || null;
    const hasTimeline = Boolean(
        timelineJson &&
        (Array.isArray(timelineJson) ? timelineJson.length > 0 : true)
    );
    const isFailed = doc.status === "failed";
    const isActivelyProcessing =
        doc.status === "processing" ||
        doc.isProcessing === true ||
        (doc.isProcessing !== false && (!isSummarized || !isVectored));

    const flags = {
        uploaded: true,
        extracted: isSummarized,
        summarized: isSummarized,
        deadlines: hasTimeline,
        embedded: isSummarized,
        indexed: isVectored,
        processed: isSummarized && isVectored && hasTimeline,
    };

    let firstIncompleteIndex = STAGES.findIndex((s) => !flags[s.key]);
    if (firstIncompleteIndex === -1) {
        firstIncompleteIndex = STAGES.length;
    }

    return STAGES.map((stage, index) => {
        const done = flags[stage.key];
        const isFirstIncomplete = index === firstIncompleteIndex;

        if (done) {
            return { ...stage, status: "completed" };
        }

        if (isFailed && isFirstIncomplete) {
            return {
                ...stage,
                status: "failed",
                detail: doc.error || "Processing failed.",
            };
        }

        if (isActivelyProcessing && isFirstIncomplete) {
            return { ...stage, status: "processing" };
        }

        return { ...stage, status: "pending" };
    });
}

function selectDocument(documents) {
    if (!documents || documents.length === 0) {
        return null;
    }

    const processing = documents.find(
        (d) => d.status === "processing" || d.isProcessing === true
    );
    if (processing) {
        return processing;
    }

    const incomplete = documents.find(
        (d) => !d.is_summarized || !d.is_vectored
    );
    if (incomplete) {
        return incomplete;
    }

    return documents[0];
}

export default function useLandingPageProcessingState() {
    const [stages, setStages] = useState(() =>
        deriveStageStatuses(null)
    );
    const [isPolling, setIsPolling] = useState(false);
    const [error, setError] = useState(null);
    const [fileName, setFileName] = useState("Document.pdf");

    const intervalRef = useRef(null);
    const mountedRef = useRef(true);
    const inFlightRef = useRef(false);
    const previousFileIdRef = useRef(null);

    const resetForDocument = useCallback((doc) => {
        setStages(deriveStageStatuses(doc));
        setFileName(doc?.filename || "Document.pdf");
        setError(null);
    }, []);

    const poll = useCallback(async () => {
        if (inFlightRef.current) {
            return;
        }

        inFlightRef.current = true;

        try {
            const session = await getCurrentSession();

            if (!mountedRef.current) {
                return;
            }

            if (!session) {
                setStages(deriveStageStatuses(null));
                setFileName("Document.pdf");
                setIsPolling(false);
                setError(null);
                return;
            }

            const response = await fetchDocuments();
            const documents = response.documents || [];
            const doc = selectDocument(documents);

            if (!mountedRef.current) {
                return;
            }

            const currentFileId = doc?.file_id || null;

            if (currentFileId !== previousFileIdRef.current) {
                previousFileIdRef.current = currentFileId;
                resetForDocument(doc);
            } else if (doc) {
                setStages((prev) => {
                    const next = deriveStageStatuses(doc);
                    if (JSON.stringify(prev) !== JSON.stringify(next)) {
                        return next;
                    }
                    return prev;
                });
                setFileName((prev) =>
                    doc.filename && doc.filename !== prev
                        ? doc.filename
                        : prev
                );
            }

            const allCompleted = doc
                ? deriveStageStatuses(doc).every((s) => s.status === "completed")
                : false;
            const anyFailed = doc
                ? deriveStageStatuses(doc).some((s) => s.status === "failed")
                : false;

            if (allCompleted || anyFailed || documents.length === 0) {
                setIsPolling(false);
                clearInterval(intervalRef.current);
                intervalRef.current = null;
                if (!allCompleted && !anyFailed && documents.length === 0) {
                    setStages(deriveStageStatuses(null));
                    setFileName("Document.pdf");
                }
            } else {
                if (!intervalRef.current) {
                    setIsPolling(true);
                }
            }
        } catch (err) {
            if (!mountedRef.current) {
                return;
            }
            setError(err.message || "Unable to load document status.");
            setIsPolling(false);
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        } finally {
            inFlightRef.current = false;
        }
    }, [resetForDocument]);

    useEffect(() => {
        mountedRef.current = true;

        poll();

        return () => {
            mountedRef.current = false;
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        };
    }, [poll]);

    useEffect(() => {
        if (!isPolling) {
            return;
        }

        intervalRef.current = window.setInterval(() => {
            if (
                typeof document !== "undefined" &&
                document.hidden
            ) {
                return;
            }
            poll();
        }, 2500);

        return () => {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        };
    }, [isPolling, poll]);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }

        const handleVisibility = () => {
            if (
                !document.hidden &&
                isPolling &&
                !inFlightRef.current
            ) {
                poll();
            }
        };

        document.addEventListener("visibilitychange", handleVisibility);

        return () => {
            document.removeEventListener("visibilitychange", handleVisibility);
        };
    }, [isPolling, poll]);

    return {
        stages,
        isPolling,
        error,
        fileName,
    };
}
