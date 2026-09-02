"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";

const STATUS_COPY = {
    completed: "Completed",
    processing: "In progress",
    pending: "Pending",
    failed: "Failed",
};

function StagePopoverInner({ stage, anchorRect, onClose }) {
    const popoverRef = useRef(null);
    const triggerRef = useRef(null);

    useEffect(() => {
        if (!anchorRect || !popoverRef.current) {
            return;
        }

        const popover = popoverRef.current;
        const arrowSize = 8;
        const gap = 12;
        const viewportWidth = typeof window !== "undefined" ? window.innerWidth : 1200;
        const popoverWidth = Math.min(280, viewportWidth - 32);

        let top = anchorRect.bottom + gap;
        let left = anchorRect.left + anchorRect.width / 2 - popoverWidth / 2;

        if (left < 16) {
            left = 16;
        }
        if (left + popoverWidth > viewportWidth - 16) {
            left = viewportWidth - 16 - popoverWidth;
        }
        if (top + 180 > (typeof window !== "undefined" ? window.innerHeight : 800)) {
            top = anchorRect.top - gap - 180;
        }

        popover.style.top = `${top}px`;
        popover.style.left = `${left}px`;
        popover.style.width = `${popoverWidth}px`;

        if (triggerRef.current) {
            triggerRef.current.focus();
        }
    }, [anchorRect, onClose]);

    useEffect(() => {
        if (!stage) {
            return;
        }

        const handleKey = (event) => {
            if (event.key === "Escape") {
                onClose();
            }
        };

        document.addEventListener("keydown", handleKey);

        return () => {
            document.removeEventListener("keydown", handleKey);
        };
    }, [stage, onClose]);

    if (!stage || !anchorRect) {
        return null;
    }

    const statusColors = {
        completed: "bg-primary/15 text-primary border-primary/30",
        processing: "bg-primary/10 text-primary border-primary/40",
        pending: "bg-muted text-muted-foreground border-border",
        failed: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
    };

    return (
        <motion.div
            ref={popoverRef}
            role="dialog"
            aria-modal="true"
            aria-label={`${stage.label} details`}
            initial={{ opacity: 0, scale: 0.95, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 4 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="fixed z-[60] rounded-xl border border-border bg-popover/95 backdrop-blur-md shadow-xl shadow-foreground/10 p-4"
            onClick={(e) => e.stopPropagation()}
        >
            <div className="flex items-start justify-between gap-3 mb-2">
                <h4 className="text-sm font-bold text-popover-foreground leading-tight">
                    {stage.label}
                </h4>
                <span
                    className={`shrink-0 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${statusColors[stage.status]}`}
                >
                    {STATUS_COPY[stage.status]}
                </span>
            </div>

            <p className="text-xs text-popover-foreground/75 leading-relaxed mb-1">
                {stage.desc}
            </p>

            {stage.detail && (
                <p className="text-[11px] text-popover-foreground/65 leading-relaxed mt-2 pt-2 border-t border-border">
                    {stage.detail}
                </p>
            )}

            <button
                ref={triggerRef}
                type="button"
                onClick={onClose}
                className="mt-3 w-full text-center text-[11px] font-semibold text-popover-foreground/65 hover:text-popover-foreground transition-colors"
            >
                Close
            </button>
        </motion.div>
    );
}

export default function StagePopover({ stage, anchorRect, onClose }) {
    const backdropRef = useRef(null);

    useEffect(() => {
        if (!stage) {
            return;
        }

        const handleKey = (event) => {
            if (event.key === "Escape") {
                onClose();
            }
        };

        document.addEventListener("keydown", handleKey);

        return () => {
            document.removeEventListener("keydown", handleKey);
        };
    }, [stage, onClose]);

    if (!stage || !anchorRect) {
        return null;
    }

    return (
        <AnimatePresence>
            {stage && anchorRect && (
                <motion.div
                    ref={backdropRef}
                    className="fixed inset-0 z-[55]"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={onClose}
                >
                    <StagePopoverInner
                        stage={stage}
                        anchorRect={anchorRect}
                        onClose={onClose}
                    />
                </motion.div>
            )}
        </AnimatePresence>
    );
}