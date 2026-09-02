
"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
    ArrowRight,
    ShieldCheck,
    Mail,
    FileText,
    Search,
    MessageSquareText,
    Loader2,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

import {
    buildSupabaseOAuthUrl,
    exchangeSupabaseSessionFromHash,
    getStoredAuthUser,
} from "../../lib/supabaseAuth";

import {
    authCardVariant,
    fadeUp,
    slideInLeft,
    staggerContainerSlow,
    errorVariant,
    fadeIn,
} from "../../components/motionVariants";

/* ─── Left panel bullet points ─────────────────────────────────────────── */
const highlights = [
    { icon: FileText, text: "Understand your institutional documents" },
    { icon: Search, text: "Semantic search across all your content" },
    { icon: MessageSquareText, text: "Conversational AI over multiple documents" },
    { icon: ShieldCheck, text: "Secure OAuth — no passwords stored" },
];

/* ─── Google Logo SVG (inline, no external dep) ────────────────────────── */
function GoogleLogo({ size = 18 }) {
    return (
        <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.6 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.5-.4-3.5z" />
            <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 16 19 13 24 13c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34.1 6.5 29.3 4 24 4 16.3 4 9.7 8.4 6.3 14.7z" />
            <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.1l-6.2-5.2C29.2 35.3 26.7 36 24 36c-5.2 0-9.5-3.3-11.3-8H6.1C9.5 35.7 16.2 44 24 44z" />
            <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.2 5.7l6.2 5.2C37 37.3 44 32 44 24c0-1.3-.1-2.5-.4-3.5z" />
        </svg>
    );
}

/* ─── Auth Page ─────────────────────────────────────────────────────────── */

export default function AuthPage() {
    const router = useRouter();

    // ── All auth logic preserved exactly as-is ──
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const [user, setUser] = useState(null);

    useEffect(() => {
        let mounted = true;

        async function initializeAuth() {
            try {
                /*
                 * IMPORTANT:
                 *
                 * Always check the real Supabase session when /auth
                 * loads, even if a user already exists in localStorage.
                 *
                 * This is important after a browser refresh.
                 *
                 * exchangeSupabaseSessionFromHash() will:
                 *
                 * 1. Restore the Supabase session.
                 * 2. Build the frontend user.
                 * 3. Start the Gmail heartbeat.
                 * 4. Immediately send a heartbeat.
                 *
                 * Therefore:
                 *
                 * INACTIVE Gmail
                 *        ↓
                 * browser refresh
                 *        ↓
                 * Supabase session restored
                 *        ↓
                 * Gmail heartbeat starts
                 *        ↓
                 * Gmail becomes ACTIVE
                 */
                const sessionUser =
                    await exchangeSupabaseSessionFromHash();

                if (!mounted) {
                    return;
                }

                if (sessionUser) {
                    setUser(sessionUser);

                    router.replace("/dashboard");

                    return;
                }

                /*
                 * There is no valid Supabase session.
                 *
                 * Clear stale local user state so the login page
                 * is shown correctly.
                 */
                setUser(null);
            } catch (err) {
                if (!mounted) {
                    return;
                }

                setError(
                    err?.message ||
                    "Unable to complete sign in."
                );
            }
        }

        initializeAuth();

        return () => {
            mounted = false;
        };
    }, [router]);

    const signInWithGoogle = async () => {
        setLoading(true);
        setError("");

        try {
            window.location.href =
                buildSupabaseOAuthUrl("google");
        } catch (err) {
            setError(
                err?.message ||
                "Unable to start Google sign in."
            );

            setLoading(false);
        }
    };

    // ── Presentation only below this line ──

    return (
        <main className="min-h-screen bg-background text-foreground overflow-hidden flex">

            {/* ── Left panel (brand / dark) ── */}
            <motion.aside
                variants={slideInLeft}
                initial="hidden"
                animate="visible"
                className="hidden lg:flex flex-col justify-between w-[42%] xl:w-[38%] bg-sidebar text-sidebar-foreground p-10 xl:p-14 relative overflow-hidden shrink-0"
                aria-hidden="true"
            >
                {/* Background texture */}
                <div className="absolute -top-16 -right-16 w-72 h-72 rounded-full bg-primary/12 blur-3xl pointer-events-none" />
                <div className="absolute -bottom-16 -left-16 w-64 h-64 rounded-full bg-primary/6 blur-3xl pointer-events-none" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full bg-primary/4 blur-3xl pointer-events-none" />

                {/* Top: logo */}
                <div className="relative z-10">
                    <Link href="/" className="inline-flex items-center gap-2.5 group">
                        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow transition-transform duration-200 group-hover:scale-105">
                            <Image
                                src="/patrerekhaai-logo.png"
                                alt="PatraRekha AI"
                                width={18}
                                height={18}
                                className="h-[18px] w-[18px] object-contain"
                            />
                        </div>
                        <span className="font-bold text-[15px] tracking-tight text-sidebar-foreground">
                            Patra<span className="text-primary">Rekha</span>
                            <span className="text-sidebar-foreground/40 font-semibold text-xs ml-0.5">AI</span>
                        </span>
                    </Link>
                </div>

                {/* Middle: headline + bullets */}
                <motion.div
                    variants={staggerContainerSlow}
                    initial="hidden"
                    animate="visible"
                    className="relative z-10 space-y-8"
                >
                    <motion.div variants={fadeUp}>
                        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary mb-4">
                            Institutional Knowledge Platform
                        </p>
                        <h2 className="text-3xl xl:text-4xl font-extrabold leading-tight tracking-tight">
                            Institutional knowledge,{" "}
                            <span className="text-primary">made accessible.</span>
                        </h2>
                    </motion.div>

                    <motion.div variants={fadeUp} className="space-y-3">
                        {highlights.map((h) => {
                            const Icon = h.icon;
                            return (
                                <div
                                    key={h.text}
                                    className="flex items-center gap-3 px-4 py-3 rounded-xl border border-white/8 bg-white/4"
                                >
                                    <div className="w-8 h-8 rounded-lg bg-primary/18 flex items-center justify-center shrink-0">
                                        <Icon size={14} className="text-primary" />
                                    </div>
                                    <span className="text-sm text-sidebar-foreground/80">{h.text}</span>
                                </div>
                            );
                        })}
                    </motion.div>
                </motion.div>

                {/* Bottom: footer note */}
                <div className="relative z-10">
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/5">
                        <ShieldCheck size={12} className="text-primary" />
                        <span className="text-[10px] font-semibold text-sidebar-foreground/70 tracking-wide">
                            Secured via Supabase OAuth
                        </span>
                    </div>
                </div>
            </motion.aside>

            {/* ── Right panel (auth form) ── */}
            <div className="flex-1 flex flex-col items-center justify-center p-6 md:p-10 min-h-screen">

                {/* Mobile-only logo */}
                <div className="lg:hidden mb-8 w-full max-w-md">
                    <Link href="/" className="inline-flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                            <Image src="/patrerekhaai-logo.png" alt="" width={18} height={18} className="h-[18px] w-[18px] object-contain" />
                        </div>
                        <span className="font-bold text-[15px] text-foreground">
                            Patra<span className="text-primary">Rekha</span>
                            <span className="text-foreground/40 text-xs font-medium">AI</span>
                        </span>
                    </Link>
                </div>

                <motion.div
                    variants={authCardVariant}
                    initial="hidden"
                    animate="visible"
                    className="w-full max-w-md"
                >
                    {/* Card */}
                    <div className="rounded-2xl border border-border bg-background/80 dark:bg-card/70 backdrop-blur-sm shadow-xl shadow-foreground/6 p-8 md:p-10">

                        {/* Header */}
                        <div className="mb-8">
                            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/22 bg-primary/10 mb-5">
                                <span className="text-[10px] font-semibold uppercase tracking-widest text-[#8C4F3E] dark:text-primary">
                                    Secure Access
                                </span>
                            </div>
                            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-foreground leading-tight">
                                Sign in to continue.
                            </h1>
                            <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                                Use your Google account to access PatraRekha. Your identity is verified securely through Supabase.
                            </p>
                        </div>

                        {/* Google sign-in button */}
                        <div className="space-y-3">
                            <motion.button
                                id="google-signin-btn"
                                onClick={signInWithGoogle}
                                disabled={loading}
                                whileHover={loading ? {} : { scale: 1.01, y: -1 }}
                                whileTap={loading ? {} : { scale: 0.98 }}
                                transition={{ duration: 0.15 }}
                                className="w-full flex items-center justify-center gap-3 px-5 py-3.5 rounded-xl border border-border bg-card text-foreground shadow-sm hover:shadow-md hover:border-primary/40 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                aria-label={loading ? "Redirecting to Google" : "Sign in with Google"}
                            >
                                {loading ? (
                                    <Loader2 size={18} className="animate-spin text-primary" />
                                ) : (
                                    <GoogleLogo size={18} />
                                )}
                                {loading ? "Redirecting…" : "Continue with Google"}
                            </motion.button>

                            {/* Divider */}
                            <div className="relative flex items-center gap-3 py-1">
                                <div className="flex-1 h-px bg-border" />
                                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
                                    or
                                </span>
                                <div className="flex-1 h-px bg-border" />
                            </div>

                            {/* Sign up link */}
                            <Link
                                href="/auth#signup"
                                id="signup-link"
                                className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl border border-border text-sm font-semibold text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-primary/5 transition-all duration-200"
                            >
                                Don&apos;t have an account? Sign up
                            </Link>
                        </div>

                        {/* Error */}
                        <AnimatePresence>
                            {error && (
                                <motion.div
                                    variants={errorVariant}
                                    initial="hidden"
                                    animate="visible"
                                    exit="exit"
                                    role="alert"
                                    aria-live="polite"
                                    className="mt-4 overflow-hidden"
                                >
                                    <div className="px-4 py-3 rounded-xl border border-destructive/30 bg-destructive/10 text-sm text-[#8C4F3E] dark:text-destructive">
                                        {error}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Signed-in user display */}
                        <AnimatePresence>
                            {user && (
                                <motion.div
                                    variants={fadeUp}
                                    initial="hidden"
                                    animate="visible"
                                    exit="hidden"
                                    className="mt-4"
                                >
                                    <div className="flex items-center gap-3 px-4 py-3.5 rounded-xl border border-primary/30 bg-primary/10">
                                        <div className="w-9 h-9 rounded-lg bg-primary/15 flex items-center justify-center shrink-0">
                                            <Mail size={15} className="text-primary" />
                                        </div>
                                        <div className="min-w-0">
                                            <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground font-semibold">
                                                Signed in as
                                            </p>
                                            <p className="text-sm font-semibold text-foreground truncate">{user.displayName}</p>
                                            <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Footer note */}
                        <p className="mt-6 text-center text-[10px] text-muted-foreground leading-relaxed">
                            By continuing, you agree to PatraRekha&apos;s terms of use.<br />
                            Your Gmail identity is only used to personalise your workspace.
                        </p>
                    </div>
                </motion.div>
            </div>
        </main>
    );
}
