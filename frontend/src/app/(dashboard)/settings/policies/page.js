"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import {
    ShieldCheck,
    ShieldAlert,
    Save,
    RefreshCw,
    Loader2,
    Eye,
    Ban,
    CheckCircle2,
    Inbox,
    FileText,
} from "lucide-react";

import {
    authenticatedFetch,
    getStoredAuthUser,
} from "../../../../lib/supabaseAuth";
import { useI18n } from "../../../../lib/i18n/I18nContext";

const DEFAULT_DECISION = "REVIEW";

function decisionFor(assignments, categoryId, defaultDecision) {
    return assignments[categoryId] || defaultDecision;
}

function decisionTone(decision) {
    if (decision === "ALLOW") {
        return {
            active: "border-emerald-500/60 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
            dot: "bg-emerald-500",
        };
    }
    if (decision === "BLOCK") {
        return {
            active: "border-rose-500/60 bg-rose-500/10 text-rose-600 dark:text-rose-400",
            dot: "bg-rose-500",
        };
    }
    return {
        active: "border-amber-500/60 bg-amber-500/10 text-amber-600 dark:text-amber-400",
        dot: "bg-amber-500",
    };
}

function DecisionBadge({ decision }) {
    const { t } = useI18n();
    const tone = decisionTone(decision);
    const label =
        decision === "ALLOW"
            ? t("intake.decisions.allow")
            : decision === "BLOCK"
                ? t("intake.decisions.block")
                : t("intake.decisions.review");
    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${tone.active}`}
        >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
            {label}
        </span>
    );
}

export default function IntakePoliciesPage() {
    const { t, isRTL } = useI18n();

    const [categories, setCategories] = useState([]);
    const [policy, setPolicy] = useState(null);
    const [workspaceId, setWorkspaceId] = useState("");
    const [assignments, setAssignments] = useState({});
    const [name, setName] = useState("");
    const [enabled, setEnabled] = useState(false);
    const [defaultDecision, setDefaultDecision] = useState(DEFAULT_DECISION);
    const [minConfidence, setMinConfidence] = useState(0);
    const [decisions, setDecisions] = useState([]);

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState(null);
    const [error, setError] = useState(null);
    const [workingFile, setWorkingFile] = useState(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const user = getStoredAuthUser();
            const wsId = user?.id || user?.email?.toLowerCase() || "default";

            const [categoryRes, policyRes, decisionRes] = await Promise.all([
                authenticatedFetch("/intake/categories"),
                authenticatedFetch("/intake/policies"),
                authenticatedFetch("/intake/decisions?limit=100"),
            ]);

            const categoryData = await categoryRes.json();
            const policyData = await policyRes.json();
            const decisionData = await decisionRes.json();

            setCategories(categoryData.categories || []);

            const policies = policyData.policies || [];
            const own =
                policies.find((p) => p.workspace_id === wsId) ||
                policies.find(
                    (p) =>
                        p.workspace_id !== "default" &&
                        p.workspace_id !== wsId,
                ) ||
                null;

            setWorkspaceId(own?.workspace_id || wsId);
            setPolicy(own);
            setName(own?.name || "");
            setEnabled(Boolean(own?.enabled));
            setDefaultDecision(own?.default_decision || DEFAULT_DECISION);
            setMinConfidence(Number(own?.min_confidence) || 0);

            const nextAssignments = {};
            for (const c of own?.allowed_categories || []) nextAssignments[c] = "ALLOW";
            for (const c of own?.review_categories || []) nextAssignments[c] = "REVIEW";
            for (const c of own?.blocked_categories || []) nextAssignments[c] = "BLOCK";
            setAssignments(nextAssignments);

            setDecisions(decisionData.decisions || []);
        } catch (err) {
            console.error("Failed to load intake policy:", err);
            setError(t("intake.error.load"));
        } finally {
            setLoading(false);
        }
    }, [t]);

    useEffect(() => {
        load();
    }, [load]);

    const unresolvedCategories = useMemo(
        () =>
            categories.filter(
                (c) => c.id !== "other" && !assignments[c.id],
            ).length,
        [categories, assignments],
    );

    const handleSave = useCallback(async () => {
        setSaving(true);
        setMessage(null);
        setError(null);
        try {
            const allowed = [];
            const review = [];
            const blocked = [];
            for (const category of categories) {
                if (category.id === "other") continue;
                const decision = assignments[category.id];
                if (decision === "ALLOW") allowed.push(category.id);
                else if (decision === "REVIEW") review.push(category.id);
                else if (decision === "BLOCK") blocked.push(category.id);
            }

            const response = await authenticatedFetch("/intake/policies", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    workspace_id: workspaceId,
                    name: name.trim() || "My intake policy",
                    allowed_categories: allowed,
                    review_categories: review,
                    blocked_categories: blocked,
                    sender_rules: policy?.sender_rules || [],
                    keyword_rules: policy?.keyword_rules || [],
                    min_confidence: Math.max(0, Math.min(1, Number(minConfidence) || 0)),
                    default_decision: defaultDecision,
                    enabled: enabled,
                }),
            });

            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data?.detail || t("intake.error.save"));
            }

            setPolicy(data.policy);
            setMessage(t("intake.saved"));
            await load();
        } catch (err) {
            console.error("Failed to save intake policy:", err);
            setError(err?.message || t("intake.error.save"));
        } finally {
            setSaving(false);
        }
    }, [
        workspaceId,
        name,
        enabled,
        defaultDecision,
        minConfidence,
        assignments,
        categories,
        policy,
        t,
        load,
    ]);

    const handleOverride = useCallback(
        async (fileId, decision) => {
            setWorkingFile(fileId);
            setError(null);
            setMessage(null);
            try {
                const response = await authenticatedFetch(
                    `/intake/decisions/${encodeURIComponent(fileId)}/override`,
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ decision }),
                    },
                );
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data?.detail || t("intake.error.override"));
                }
                setMessage(
                    decision === "ALLOW"
                        ? t("intake.decisions.releaseQueued")
                        : t("intake.decisions.heldBlocked"),
                );
                await load();
            } catch (err) {
                console.error("Override failed:", err);
                setError(err?.message || t("intake.error.override"));
            } finally {
                setWorkingFile(null);
            }
        },
        [t, load],
    );

    const quarantined = useMemo(
        () =>
            decisions
                .filter((d) => ["REVIEW", "BLOCK"].includes(d.decision))
                .slice(0, 50),
        [decisions],
    );

    if (loading) {
        return (
            <div className="mx-auto max-w-5xl space-y-6 p-6">
                <div className="flex items-center gap-3">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                        {t("common.loading")}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div dir={isRTL ? "rtl" : "ltr"} className="mx-auto max-w-5xl space-y-6 p-6">
            {/* Header */}
            <header className="space-y-1">
                <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-border bg-card shadow-sm">
                        <ShieldCheck className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold tracking-tight">
                            {t("intake.title")}
                        </h1>
                        <p className="text-sm text-muted-foreground">
                            {t("intake.subtitle")}
                        </p>
                    </div>
                </div>
            </header>

            {/* Status banner */}
            <div
                className={`flex items-center justify-between gap-3 rounded-xl border p-4 ${
                    enabled
                        ? "border-emerald-500/30 bg-emerald-500/5"
                        : "border-border bg-card"
                }`}
            >
                <div className="flex items-center gap-3">
                    <ShieldAlert
                        className={`h-5 w-5 ${
                            enabled
                                ? "text-emerald-500"
                                : "text-muted-foreground"
                        }`}
                    />
                    <div>
                        <p className="text-sm font-semibold">
                            {enabled
                                ? t("intake.policy.status.active")
                                : t("intake.policy.status.inactive")}
                        </p>
                        <p className="text-xs text-muted-foreground">
                            {enabled
                                ? t("intake.policy.status.activeHint")
                                : t("intake.policy.status.inactiveHint")}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        onClick={() => load()}
                        disabled={saving}
                        className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium transition-colors hover:bg-muted disabled:opacity-50"
                    >
                        <RefreshCw className="h-3.5 w-3.5" />
                        {t("docs.refresh")}
                    </button>
                    <button
                        type="button"
                        onClick={handleSave}
                        disabled={saving}
                        className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                        {saving ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <Save className="h-3.5 w-3.5" />
                        )}
                        {t("intake.policy.save")}
                    </button>
                </div>
            </div>

            {message && (
                <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="h-4 w-4" />
                    {message}
                </div>
            )}
            {error && (
                <div className="flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/5 px-4 py-3 text-sm text-rose-600 dark:text-rose-400">
                    <ShieldAlert className="h-4 w-4" />
                    {error}
                </div>
            )}

            {/* Policy settings */}
            <section className="space-y-5 rounded-2xl border border-border bg-card p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <h2 className="text-base font-semibold">
                            {t("intake.policy.title")}
                        </h2>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                            {t("intake.policy.matrixHint")}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => setEnabled((prev) => !prev)}
                        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                            enabled ? "bg-emerald-500" : "bg-muted"
                        }`}
                        aria-pressed={enabled}
                        title={
                            enabled
                                ? t("intake.policy.status.active")
                                : t("intake.policy.status.inactive")
                        }
                    >
                        <motion.span
                            animate={{ x: enabled ? (isRTL ? -18 : 18) : 0 }}
                            transition={{ type: "spring", stiffness: 500, damping: 32 }}
                            className="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow"
                        />
                    </button>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <label className="space-y-1.5">
                        <span className="text-xs font-medium text-muted-foreground">
                            {t("intake.policy.name")}
                        </span>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="My intake policy"
                            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                        />
                    </label>
                    <label className="space-y-1.5">
                        <span className="text-xs font-medium text-muted-foreground">
                            {t("intake.policy.defaultDecision")}
                        </span>
                        <select
                            value={defaultDecision}
                            onChange={(e) => setDefaultDecision(e.target.value)}
                            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                        >
                            <option value="REVIEW">
                                {t("intake.decisions.review")}
                            </option>
                            <option value="ALLOW">
                                {t("intake.decisions.allow")}
                            </option>
                            <option value="BLOCK">
                                {t("intake.decisions.block")}
                            </option>
                        </select>
                    </label>
                    <label className="space-y-1.5">
                        <span className="text-xs font-medium text-muted-foreground">
                            {t("intake.policy.minConfidence")}
                        </span>
                        <input
                            type="number"
                            min="0"
                            max="1"
                            step="0.05"
                            value={minConfidence}
                            onChange={(e) => setMinConfidence(e.target.value)}
                            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
                        />
                    </label>
                </div>

                {/* Document type matrix */}
                <div className="overflow-hidden rounded-xl border border-border">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-border bg-muted/50 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                <th className="px-4 py-3">
                                    {t("intake.matrix.header.docType")}
                                </th>
                                <th className="px-4 py-3 text-center">
                                    {t("intake.matrix.header.allow")}
                                </th>
                                <th className="px-4 py-3 text-center">
                                    {t("intake.matrix.header.review")}
                                </th>
                                <th className="px-4 py-3 text-center">
                                    {t("intake.matrix.header.block")}
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {categories
                                .filter((c) => c.id !== "other")
                                .map((category) => {
                                    const active = decisionFor(
                                        assignments,
                                        category.id,
                                        defaultDecision,
                                    );
                                    const set = (decision) =>
                                        setAssignments((prev) => ({
                                            ...prev,
                                            [category.id]: decision,
                                        }));
                                    return (
                                        <tr
                                            key={category.id}
                                            className="border-b border-border/60 last:border-0"
                                        >
                                            <td className="px-4 py-2.5">
                                                <span className="flex items-center gap-2 font-medium">
                                                    <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                                                    {category.label}
                                                </span>
                                            </td>
                                            {["ALLOW", "REVIEW", "BLOCK"].map(
                                                (option) => {
                                                    const tone =
                                                        decisionTone(option);
                                                    const selected =
                                                        active === option;
                                                    return (
                                                        <td
                                                            key={option}
                                                            className="px-3 py-2 text-center"
                                                        >
                                                            <button
                                                                type="button"
                                                                onClick={() =>
                                                                    set(option)
                                                                }
                                                                aria-pressed={selected}
                                                                className={`inline-flex w-full max-w-[110px] items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-xs font-semibold transition-all ${
                                                                    selected
                                                                        ? tone.active
                                                                        : "border-transparent text-muted-foreground/70 hover:border-border hover:bg-muted/60"
                                                                }`}
                                                            >
                                                                <span
                                                                    className={`h-1.5 w-1.5 rounded-full ${tone.dot}`}
                                                                />
                                                                {option ===
                                                                "ALLOW"
                                                                    ? t(
                                                                          "intake.matrix.header.allow",
                                                                      )
                                                                    : option ===
                                                                        "REVIEW"
                                                                        ? t(
                                                                              "intake.matrix.header.review",
                                                                          )
                                                                        : t(
                                                                              "intake.matrix.header.block",
                                                                          )}
                                                            </button>
                                                        </td>
                                                    );
                                                },
                                            )}
                                        </tr>
                                    );
                                })}
                        </tbody>
                    </table>
                </div>

                {unresolvedCategories > 0 && (
                    <p className="text-xs text-muted-foreground">
                        {t("intake.policy.unresolved").replace(
                            "{count}",
                            unresolvedCategories,
                        )}
                    </p>
                )}
            </section>

            {/* Quarantine / audit */}
            <section className="space-y-3 rounded-2xl border border-border bg-card p-5 shadow-sm">
                <div className="flex items-center gap-2">
                    <Eye className="h-4 w-4 text-muted-foreground" />
                    <h2 className="text-base font-semibold">
                        {t("intake.decisions.title")}
                    </h2>
                </div>

                {quarantined.length === 0 ? (
                    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border py-10 text-center">
                        <Inbox className="h-8 w-8 text-muted-foreground/50" />
                        <p className="text-sm text-muted-foreground">
                            {t("intake.decisions.empty")}
                        </p>
                    </div>
                ) : (
                    <ul className="space-y-2">
                        {quarantined.map((d) => {
                            const busy = workingFile === d.file_id;
                            return (
                                <li
                                    key={d.id || d.file_id}
                                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border px-4 py-3"
                                >
                                    <div className="min-w-0 flex-1">
                                        <p className="truncate text-sm font-medium">
                                            {d.filename || d.file_id}
                                        </p>
                                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                                            {d.category}
                                            {d.reason ? ` — ${d.reason}` : ""}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <DecisionBadge decision={d.decision} />
                                        <button
                                            type="button"
                                            disabled={busy}
                                            onClick={() =>
                                                handleOverride(d.file_id, "ALLOW")
                                            }
                                            className="flex items-center gap-1.5 rounded-lg border border-emerald-500/40 px-3 py-1.5 text-xs font-semibold text-emerald-600 transition-colors hover:bg-emerald-500/10 disabled:opacity-50 dark:text-emerald-400"
                                        >
                                            {busy ? (
                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                            ) : (
                                                <CheckCircle2 className="h-3.5 w-3.5" />
                                            )}
                                            {t("intake.decisions.overrideAllow")}
                                        </button>
                                        <button
                                            type="button"
                                            disabled={busy}
                                            onClick={() =>
                                                handleOverride(d.file_id, "BLOCK")
                                            }
                                            className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 px-3 py-1.5 text-xs font-semibold text-rose-600 transition-colors hover:bg-rose-500/10 disabled:opacity-50 dark:text-rose-400"
                                        >
                                            <Ban className="h-3.5 w-3.5" />
                                            {t("intake.decisions.overrideBlock")}
                                        </button>
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </section>
        </div>
    );
}