
"use client";

import { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import Link from "next/link";
import {
    CalendarDays,
    FileText,
    Loader2,
    Mail,
    MessageSquareText,
    Upload,
    AlertTriangle,
    ArrowRight,
    X,
} from "lucide-react";

import {
    buildGmailConnectUrl,
    fetchGmailConnectionStatus,
    getStoredAuthUser,
    startGmailActivityHeartbeat,
} from "../../../lib/supabaseAuth";
import { useI18n } from "../../../lib/i18n/I18nContext";
import { authenticatedFetch } from "../../../lib/supabaseAuth";
import { HelpTooltip } from "../../../components/ui/help-tooltip";

/* -------------------------------------------------------------------------- */
/* Helpers                                                                     */
/* -------------------------------------------------------------------------- */

function timeAgo(date) {
    if (!date) return "";
    const now = new Date();
    const then = new Date(date);
    const seconds = Math.floor((now - then) / 1000);
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days === 1) return "yesterday";
    if (days < 7) return `${days}d ago`;
    return then.toLocaleDateString();
}

function formatDeadline(dateStr) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    const now = new Date();
    const diff = date - now;
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    if (days < 0) return "overdue";
    if (days === 0) return "today";
    if (days === 1) return "tomorrow";
    if (days <= 7) return `${days} days`;
    return date.toLocaleDateString();
}

function getDocumentStatus(doc) {
    if (doc.isProcessing || doc.status === "processing" || doc.status === "uploading") {
        return "processing";
    }
    if (doc.is_summarized && doc.is_vectored) {
        return "ready";
    }
    return "processing";
}

/* -------------------------------------------------------------------------- */
/* Skeleton components                                                         */
/* -------------------------------------------------------------------------- */

function DocumentSkeleton() {
    return (
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-3">
            <div className="h-10 w-10 rounded-lg bg-muted animate-pulse" />
            <div className="flex-1 space-y-2">
                <div className="h-3 w-32 rounded bg-muted animate-pulse" />
                <div className="h-2 w-20 rounded bg-muted animate-pulse" />
            </div>
            <div className="h-5 w-16 rounded-full bg-muted animate-pulse" />
        </div>
    );
}

function DeadlineSkeleton() {
    return (
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-3">
            <div className="h-8 w-8 rounded-lg bg-muted animate-pulse" />
            <div className="flex-1 space-y-2">
                <div className="h-3 w-28 rounded bg-muted animate-pulse" />
                <div className="h-2 w-20 rounded bg-muted animate-pulse" />
            </div>
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Section headers                                                             */
/* -------------------------------------------------------------------------- */

function SectionHeader({ icon: Icon, title, action }) {
    return (
        <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
                <Icon size={14} className="text-muted-foreground" />
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>
            </div>
            {action}
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Status badge                                                                */
/* -------------------------------------------------------------------------- */

function ProcessingBadge({ status }) {
    if (status === "ready") {
        return (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 size={10} />
                Ready
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
            <Loader2 size={10} className="animate-spin" />
            Processing
        </span>
    );
}

/* -------------------------------------------------------------------------- */
/* Main Dashboard                                                              */
/* -------------------------------------------------------------------------- */

export default function DashboardHome() {
    const { t } = useI18n();
    const [user] = useState(() => getStoredAuthUser());

    const [gmailStatus, setGmailStatus] = useState({ connected: false });
    const [gmailLoading, setGmailLoading] = useState(false);
    const [gmailError, setGmailError] = useState("");

    const [documents, setDocuments] = useState([]);
    const [documentsLoading, setDocumentsLoading] = useState(true);

    const [events, setEvents] = useState([]);
    const [eventsLoading, setEventsLoading] = useState(true);

    const [conversations, setConversations] = useState([]);
    const [conversationsLoading, setConversationsLoading] = useState(true);

    const [onboardingDismissed, setOnboardingDismissed] = useState(false);

    /* ---- Data fetching ---- */

    useEffect(() => {
        if (!user?.email) return;

        startGmailActivityHeartbeat();

        fetchGmailConnectionStatus(user.email)
            .then(setGmailStatus)
            .catch((err) => {
                console.warn("Unable to load Gmail status:", err);
            });

        const fetchData = async () => {
            try {
                const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

                const [docsRes, eventsRes, convRes] = await Promise.all([
                    authenticatedFetch("/documents/get-documents"),
                    authenticatedFetch("/calendar/calendar-events"),
                    authenticatedFetch("/conversations"),
                ]);

                if (docsRes.ok) {
                    const docsData = await docsRes.json();
                    setDocuments(docsData.documents || []);
                }
                setDocumentsLoading(false);

                if (eventsRes.ok) {
                    const eventsData = await eventsRes.json();
                    setEvents(eventsData.events || []);
                }
                setEventsLoading(false);

                if (convRes.ok) {
                    const convData = await convRes.json();
                    setConversations(convData.conversations || []);
                }
                setConversationsLoading(false);
            } catch (err) {
                console.warn("Unable to load dashboard data:", err);
                setDocumentsLoading(false);
                setEventsLoading(false);
                setConversationsLoading(false);
            }
        };

        fetchData();
    }, [user?.email]);

    /* ---- Derived data ---- */

    const recentDocuments = useMemo(() => {
        return [...documents]
            .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
            .slice(0, 5);
    }, [documents]);

    const processingDocuments = useMemo(() => {
        return documents.filter((doc) => getDocumentStatus(doc) === "processing");
    }, [documents]);

    const upcomingDeadlines = useMemo(() => {
        const now = new Date();
        return events
            .filter((e) => e.date && new Date(e.date) >= now)
            .sort((a, b) => new Date(a.date) - new Date(b.date))
            .slice(0, 5);
    }, [events]);

    const hasDocuments = documents.length > 0;

    /* ---- Gmail connect ---- */

    const connectGmail = async () => {
        if (!user?.email) return;
        setGmailLoading(true);
        setGmailError("");
        try {
            window.location.href = await buildGmailConnectUrl(user.email);
        } catch (err) {
            setGmailError(err.message || "Unable to start Gmail connect.");
            setGmailLoading(false);
        }
    };

    /* ---- Check onboarding ---- */

    useEffect(() => {
        const dismissed = localStorage.getItem("patrerekha_onboarding_dismissed");
        if (dismissed) setOnboardingDismissed(true);
    }, []);

    const dismissOnboarding = () => {
        localStorage.setItem("patrerekha_onboarding_dismissed", "true");
        setOnboardingDismissed(true);
    };

    /* ---- Render ---- */

    return (
        <div className="h-full bg-background text-foreground">
            <div className="w-full p-5 md:p-8 lg:p-10">

                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
                        {t("dashboard.welcome", "Good to see you.")}
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        {t("dashboard.subtitle", "Your documents, conversations, and deadlines — organized.")}
                    </p>
                </div>

                {/* Getting Started - only if no docs and not dismissed */}
                <AnimatePresence>
                    {!hasDocuments && !documentsLoading && !onboardingDismissed && (
                        <motion.div
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                            className="mb-6 rounded-xl border border-border bg-card p-5"
                        >
                            <div className="flex items-start justify-between">
                                <div>
                                    <h3 className="text-sm font-semibold text-foreground">
                                        {t("dashboard.gettingStarted", "Getting Started")}
                                    </h3>
                                    <ol className="mt-2 space-y-1.5 text-xs text-muted-foreground">
                                        <li className="flex items-center gap-2">
                                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">1</span>
                                            {t("dashboard.step1", "Upload a document")}
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground">2</span>
                                            {t("dashboard.step2", "Wait for processing")}
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground">3</span>
                                            {t("dashboard.step3", "Ask a question")}
                                        </li>
                                        <li className="flex items-center gap-2">
                                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground">4</span>
                                            {t("dashboard.step4", "Review extracted deadlines")}
                                        </li>
                                    </ol>
                                </div>
                                <button
                                    type="button"
                                    onClick={dismissOnboarding}
                                    className="shrink-0 rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                                >
                                    <X size={14} />
                                </button>
                            </div>
                            <Link
                                href="/document"
                                className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90"
                            >
                                <Upload size={14} />
                                {t("dashboard.uploadFirst", "Upload your first document")}
                            </Link>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Main content grid */}
                <div className="grid gap-6 lg:grid-cols-[1fr_320px]">

                    {/* Left column - primary content */}
                    <div className="space-y-6 lg:border-r lg:border-border lg:pr-6">

                        {/* Recent Documents */}
                        <section>
                            <SectionHeader
                                icon={FileText}
                                title={t("dashboard.recentDocuments", "Recent Documents")}
                                action={
                                    hasDocuments ? (
                                        <Link href="/document" className="text-xs text-primary hover:underline">
                                            {t("dashboard.viewAll", "View all")}
                                        </Link>
                                    ) : null
                                }
                            />

                            {documentsLoading ? (
                                <div className="space-y-2">
                                    <DocumentSkeleton />
                                    <DocumentSkeleton />
                                    <DocumentSkeleton />
                                </div>
                            ) : recentDocuments.length > 0 ? (
                                <div className="space-y-2">
                                    {recentDocuments.map((doc) => (
                                        <Link
                                            key={doc.file_id}
                                            href={`/document`}
                                            className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:bg-card/80"
                                        >
                                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                                <FileText size={18} className="text-primary" />
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <p className="truncate text-sm font-medium text-foreground">
                                                    {doc.filename || doc.document_name || "Untitled"}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {timeAgo(doc.created_at)}
                                                </p>
                                            </div>
                                            <ProcessingBadge status={getDocumentStatus(doc)} />
                                        </Link>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-xl border border-dashed border-border bg-card/50 p-6 text-center">
                                    <FileText size={24} className="mx-auto text-muted-foreground/50" />
                                    <p className="mt-2 text-sm text-muted-foreground">
                                        {t("dashboard.noDocuments", "No documents yet.")}
                                    </p>
                                    <p className="mt-1 text-xs text-muted-foreground/70">
                                        {t("dashboard.uploadPrompt", "Upload a PDF, DOCX, or supported document to get started.")}
                                    </p>
                                    <Link
                                        href="/document"
                                        className="mt-3 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition hover:bg-primary/90"
                                    >
                                        <Upload size={14} />
                                        {t("dashboard.uploadDocument", "Upload Document")}
                                    </Link>
                                </div>
                            )}
                        </section>

                        {/* Processing Status - only show if something is processing */}
                        <AnimatePresence>
                            {processingDocuments.length > 0 && (
                                <motion.section
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: "auto" }}
                                    exit={{ opacity: 0, height: 0 }}
                                >
                                    <SectionHeader
                                        icon={Loader2}
                                        title={t("dashboard.processing", "Processing")}
                                    />
                                    <div className="space-y-2">
                                        {processingDocuments.map((doc) => (
                                            <div
                                                key={doc.file_id}
                                                className="flex items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 p-3"
                                            >
                                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                                    <Loader2 size={18} className="animate-spin text-primary" />
                                                </div>
                                                <div className="min-w-0 flex-1">
                                                    <p className="truncate text-sm font-medium text-foreground">
                                                        {doc.filename || "Untitled"}
                                                    </p>
                                                    <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                                                        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                                                            {doc.processingStage || "processing"}
                                                        </span>
                                                        <HelpTooltip content="Document is being processed: text extracted, indexed for search, and summarized for chat." />
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </motion.section>
                            )}
                        </AnimatePresence>

                        {/* Upcoming Deadlines */}
                        <section>
                            <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                    <CalendarDays size={14} className="text-muted-foreground" />
                                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                        {t("dashboard.upcomingDeadlines", "Upcoming Deadlines")}
                                    </h3>
                                    <HelpTooltip content="Important dates detected in your documents. PatraRekhaAI extracts deadlines, tenders, and compliance dates automatically." />
                                </div>
                                {upcomingDeadlines.length > 0 && (
                                    <Link href="/calendar" className="text-xs text-primary hover:underline">
                                        {t("dashboard.viewCalendar", "View calendar")}
                                    </Link>
                                )}
                            </div>

                            {eventsLoading ? (
                                <div className="space-y-2">
                                    <DeadlineSkeleton />
                                    <DeadlineSkeleton />
                                </div>
                            ) : upcomingDeadlines.length > 0 ? (
                                <div className="space-y-2">
                                    {upcomingDeadlines.map((event, idx) => (
                                        <div
                                            key={event.id || idx}
                                            className="flex items-center gap-3 rounded-xl border border-border bg-card p-3"
                                        >
                                            <div className="flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-lg bg-primary/10">
                                                <span className="text-[10px] font-bold text-primary leading-none">
                                                    {formatDeadline(event.date)}
                                                </span>
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <p className="truncate text-sm font-medium text-foreground">
                                                    {event.title || event.event || "Untitled deadline"}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {event.date ? new Date(event.date).toLocaleDateString() : ""}
                                                    {event.source_document ? ` · ${event.source_document}` : ""}
                                                </p>
                                            </div>
                                            {event.priority === "high" && (
                                                <AlertTriangle size={14} className="shrink-0 text-amber-500" />
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-xl border border-dashed border-border bg-card/50 p-6 text-center">
                                    <CalendarDays size={24} className="mx-auto text-muted-foreground/50" />
                                    <p className="mt-2 text-sm text-muted-foreground">
                                        {t("dashboard.noDeadlines", "No upcoming deadlines.")}
                                    </p>
                                    <p className="mt-1 text-xs text-muted-foreground/70">
                                        {t("dashboard.deadlinesHint", "Deadlines detected in your documents will appear here.")}
                                    </p>
                                </div>
                            )}
                        </section>
                    </div>

                    {/* Right column - sidebar */}
                    {/* Right column - secondary content */}
                    <div className="space-y-6">

                        {/* Quick Actions */}
                        <section>
                            <SectionHeader
                                icon={ArrowRight}
                                title={t("dashboard.quickActions", "Quick Actions")}
                            />
                            <div className="space-y-2">
                                <Link
                                    href="/document"
                                    className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:bg-card/80"
                                >
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                        <FileText size={18} className="text-primary" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-foreground">{t("sidebar.documents", "Documents")}</p>
                                        <p className="text-xs text-muted-foreground">{documents.length} {t("dashboard.total", "total")}</p>
                                    </div>
                                </Link>
                                <Link
                                    href="/chat"
                                    className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:bg-card/80"
                                >
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                        <MessageSquareText size={18} className="text-primary" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-foreground">{t("sidebar.chat", "Chat")}</p>
                                        <p className="text-xs text-muted-foreground">{t("dashboard.askQuestions", "Ask questions")}</p>
                                    </div>
                                </Link>
                                <Link
                                    href="/calendar"
                                    className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:bg-card/80"
                                >
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                        <CalendarDays size={18} className="text-primary" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-foreground">{t("sidebar.calendar", "Calendar")}</p>
                                        <p className="text-xs text-muted-foreground">{upcomingDeadlines.length} {t("dashboard.deadlines", "deadlines")}</p>
                                    </div>
                                </Link>
                            </div>
                        </section>

                        {/* Gmail Integration */}
                        <section>
                            <SectionHeader
                                icon={Mail}
                                title={t("dashboard.integrations", "Integrations")}
                            />
                            <div className="rounded-xl border border-border bg-card p-4">
                                <div className="flex items-center gap-3">
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                        <Mail size={18} className="text-primary" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-medium text-foreground">Gmail</p>
                                        <p className="truncate text-xs text-muted-foreground">
                                            {gmailStatus.connected
                                                ? gmailStatus.connection?.google_email || user?.email
                                                : t("dashboard.notConnected", "Not connected")}
                                        </p>
                                    </div>
                                    <StatusBadgeInline connected={gmailStatus.connected} />
                                </div>
                                {!gmailStatus.connected && (
                                    <button
                                        type="button"
                                        onClick={connectGmail}
                                        disabled={gmailLoading || !user?.email}
                                        className="mt-3 w-full rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        {gmailLoading ? t("dashboard.connecting", "Connecting...") : t("dashboard.connectGmail", "Connect Gmail")}
                                    </button>
                                )}
                                {gmailError && (
                                    <p className="mt-2 text-xs text-destructive">{gmailError}</p>
                                )}
                            </div>
                        </section>

                        {/* Recent Conversations */}
                        <section>
                            <SectionHeader
                                icon={MessageSquareText}
                                title={t("dashboard.recentChats", "Recent Chats")}
                                action={
                                    conversations.length > 0 ? (
                                        <Link href="/chat" className="text-xs text-primary hover:underline">
                                            {t("dashboard.viewAll", "View all")}
                                        </Link>
                                    ) : null
                                }
                            />

                            {conversationsLoading ? (
                                <div className="space-y-2">
                                    <DocumentSkeleton />
                                </div>
                            ) : conversations.length > 0 ? (
                                <div className="space-y-2">
                                    {conversations.slice(0, 3).map((conv) => (
                                        <Link
                                            key={conv.id}
                                            href="/chat"
                                            className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:bg-card/80"
                                        >
                                            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                                                <MessageSquareText size={18} className="text-primary" />
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <p className="truncate text-sm font-medium text-foreground">
                                                    {conv.title || "Untitled conversation"}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {timeAgo(conv.updated_at || conv.created_at)}
                                                </p>
                                            </div>
                                        </Link>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-xl border border-dashed border-border bg-card/50 p-4 text-center">
                                    <MessageSquareText size={20} className="mx-auto text-muted-foreground/50" />
                                    <p className="mt-2 text-xs text-muted-foreground">
                                        {t("dashboard.noChats", "No conversations yet.")}
                                    </p>
                                </div>
                            )}
                        </section>
                    </div>
                </div>
            </div>
        </div>
    );
}

/* -------------------------------------------------------------------------- */
/* Small inline components                                                     */
/* -------------------------------------------------------------------------- */

function StatusBadgeInline({ connected }) {
    return (
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
            connected
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : "bg-muted text-muted-foreground"
        }`}>
            <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-muted-foreground/50"}`} />
            {connected ? "Connected" : "Off"}
        </span>
    );
}
