import React from "react";
import { motion, AnimatePresence } from "motion/react";
import { Mail, RefreshCw, Trash2, Loader2 } from "lucide-react";
import { Skeleton } from "./ui/skeleton";

function formatDate(isoString) {
    if (!isoString) return "";
    try {
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return "";
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return "";
    }
}

function formatTime(isoString) {
    if (!isoString) return "";
    try {
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return "";
        return d.toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return "";
    }
}

function EmailAvatar({ email }) {
    const subject = email?.subject || "";
    const sender = email?.sender || "";
    const initials = (subject || sender || "?").charAt(0).toUpperCase();

    return (
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-border bg-muted text-xs font-bold text-muted-foreground">
            {initials}
        </div>
    );
}

export default function EmailList({
    emails = [],
    isLoading = false,
    selectedEmail = null,
    onSelect,
    onDelete,
    onRefresh,
}) {
    return (
        <div className="flex h-full flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-card">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                <div className="flex items-center gap-2">
                    <Mail size={16} className="text-muted-foreground" />
                    <span className="text-sm font-semibold text-foreground">
                        Emails
                    </span>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                        {emails.length}
                    </span>
                </div>
                <button
                    type="button"
                    onClick={onRefresh}
                    disabled={isLoading}
                    className="grid h-8 w-8 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:opacity-50"
                    aria-label="Refresh emails"
                >
                    {isLoading ? (
                        <Loader2 size={16} className="animate-spin" />
                    ) : (
                        <RefreshCw size={14} />
                    )}
                </button>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
                <AnimatePresence mode="popLayout">
                    {isLoading && emails.length === 0 ? (
                        Array.from({ length: 5 }).map((_, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="flex items-center gap-3 rounded-xl border border-border/50 bg-card p-3"
                            >
                                <Skeleton className="h-10 w-10 rounded-full" />
                                <div className="flex-1 space-y-2">
                                    <Skeleton className="h-3.5 w-3/5" />
                                    <Skeleton className="h-3 w-1/3" />
                                </div>
                            </motion.div>
                        ))
                    ) : emails.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-center">
                            <div className="grid h-12 w-12 place-items-center rounded-full bg-muted mb-3">
                                <Mail size={20} className="text-muted-foreground" />
                            </div>
                            <p className="text-sm font-medium text-muted-foreground">No emails yet</p>
                            <p className="text-xs text-muted-foreground/60 mt-1">
                                Emails without attachments will appear here
                            </p>
                        </div>
                    ) : (
                        emails.map((email) => {
                            const isSelected =
                                selectedEmail?.email_id === email.email_id;
                            return (
                                <motion.div
                                    key={email.email_id}
                                    layout
                                    initial={{ opacity: 0, y: 6 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0 }}
                                    onClick={() => onSelect(email)}
                                    className={`group flex w-full cursor-pointer items-start gap-3 rounded-xl border p-3 text-left transition ${
                                        isSelected
                                            ? "border-primary/60 bg-primary/5"
                                            : "border-border/60 bg-card hover:border-primary/30 hover:bg-muted/50"
                                    }`}
                                >
                                    <EmailAvatar email={email} />
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center justify-between gap-2">
                                            <p className="truncate text-sm font-semibold text-foreground">
                                                {email.subject || "(No subject)"}
                                            </p>
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    onDelete(email);
                                                }}
                                                className="shrink-0 grid h-7 w-7 place-items-center rounded-lg text-muted-foreground opacity-0 transition hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                                                aria-label="Delete email"
                                            >
                                                <Trash2 size={13} />
                                            </button>
                                        </div>
                                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                                            {email.sender || "Unknown sender"}
                                        </p>
                                        <p className="mt-0.5 text-[10px] text-muted-foreground/60">
                                            {formatDate(email.received_at)}
                                            {formatDate(email.received_at) && formatTime(email.received_at) ? " · " : ""}
                                            {formatTime(email.received_at)}
                                        </p>
                                    </div>
                                </motion.div>
                            );
                        })
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
