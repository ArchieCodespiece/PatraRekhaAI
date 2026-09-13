import React from "react";
import { motion, AnimatePresence } from "motion/react";
import { X, Trash2, Mail, CalendarClock } from "lucide-react";

function formatDate(isoString) {
    if (!isoString) return "";
    try {
        return new Date(isoString).toLocaleDateString("en-US", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
        });
    } catch {
        return "";
    }
}

function formatDateTime(isoString) {
    if (!isoString) return "";
    try {
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return "";
        return d.toLocaleString("en-US", {
            weekday: "short",
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return "";
    }
}

export default function EmailDetailPanel({ email, onClose, onDelete }) {
    return (
        <AnimatePresence>
            {email && (
                <motion.div
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ duration: 0.2 }}
                    className="w-80 xl:w-96 shrink-0 overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
                >
                    {/* Header */}
                    <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                        <div className="flex items-center gap-2">
                            <Mail size={14} className="text-muted-foreground" />
                            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                Email Detail
                            </span>
                        </div>
                        <button
                            type="button"
                            onClick={onClose}
                            className="grid h-7 w-7 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                            aria-label="Close"
                        >
                            <X size={14} />
                        </button>
                    </div>

                    {/* Body */}
                    <div className="px-5 py-4 space-y-4 overflow-y-auto max-h-[calc(100%-60px)]">
                        <div>
                            <h3 className="text-sm font-bold text-foreground leading-snug">
                                {email.subject || "(No subject)"}
                            </h3>
                        </div>

                        <div className="space-y-2 text-xs">
                            <div className="flex items-start gap-2">
                                <Mail size={12} className="mt-0.5 text-muted-foreground shrink-0" />
                                <div>
                                    <p className="text-muted-foreground">From</p>
                                    <p className="font-medium text-foreground">{email.sender || "Unknown"}</p>
                                </div>
                            </div>

                            <div className="flex items-start gap-2">
                                <CalendarClock size={12} className="mt-0.5 text-muted-foreground shrink-0" />
                                <div>
                                    <p className="text-muted-foreground">Received</p>
                                    <p className="font-medium text-foreground">
                                        {formatDateTime(email.received_at) || "Unknown"}
                                    </p>
                                </div>
                            </div>

                            {email.email_intent && (
                                <div className="flex items-start gap-2">
                                    <span className="mt-0.5 text-muted-foreground shrink-0">🏷</span>
                                    <div>
                                        <p className="text-muted-foreground">Intent</p>
                                        <p className="font-medium text-foreground">{email.email_intent}</p>
                                    </div>
                                </div>
                            )}
                        </div>

                        {email.body_text && (
                            <div className="border-t border-border/60 pt-3">
                                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                                    Body
                                </p>
                                <p className="text-xs text-foreground/80 leading-relaxed whitespace-pre-wrap">
                                    {email.body_text}
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="px-5 py-3 border-t border-border">
                        <button
                            type="button"
                            onClick={() => onDelete(email)}
                            className="flex w-full items-center justify-center gap-2 rounded-xl border border-destructive/30 px-4 py-2.5 text-xs font-semibold text-destructive transition hover:bg-destructive/10"
                        >
                            <Trash2 size={14} />
                            Delete Email
                        </button>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
