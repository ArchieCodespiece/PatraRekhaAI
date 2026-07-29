"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Globe, Sparkles, ShieldCheck, Mail } from "lucide-react";
import { buildSupabaseOAuthUrl, exchangeSupabaseSessionFromHash, getStoredAuthUser } from "../../lib/supabaseAuth";

export default function AuthPage() {
    const router = useRouter();
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const [user, setUser] = useState(() => getStoredAuthUser());

    useEffect(() => {
        if (user) {
            router.replace("/dashboard");
            return;
        }

        exchangeSupabaseSessionFromHash()
            .then((sessionUser) => {
                if (sessionUser) {
                    setUser(sessionUser);
                    router.replace("/dashboard");
                }
            })
            .catch((err) => setError(err.message || "Unable to complete sign in."));
    }, [router, user]);

    const signInWithGoogle = async () => {
        setLoading(true);
        setError("");

        try {
            window.location.href = buildSupabaseOAuthUrl("google");
        } catch (err) {
            setError(err.message || "Unable to start Google sign in.");
            setLoading(false);
        }
    };

    return (
        <main className="min-h-screen bg-[radial-gradient(circle_at_top,#FFEAD5_0%,#FFFBF0_45%,#F8EFE4_100%)] text-[#413632] flex items-center justify-center p-6">
            <div className="absolute inset-0 pointer-events-none opacity-70 bg-[linear-gradient(120deg,transparent_0%,rgba(202,138,120,0.08)_35%,transparent_70%)]" />

            <div className="relative z-10 w-full max-w-6xl grid lg:grid-cols-[1.1fr_0.9fr] gap-8 items-stretch">
                <section className="rounded-[2rem] border border-[#CABDB2]/70 bg-white/60 backdrop-blur-md shadow-2xl shadow-[#CA8A78]/10 p-8 md:p-12">
                    <Link href="/" className="inline-flex items-center gap-3">
                        <Image src="/patrerekhaai-logo.png" alt="PatraRekhaAI" width={40} height={40} className="h-10 w-10" />
                        <span className="text-lg font-bold">Patra<span className="text-[#CA8A78]">RekhaAI</span></span>
                    </Link>

                    <div className="mt-14 max-w-xl">
                        <span className="inline-flex items-center gap-2 rounded-full border border-[#CA8A78]/20 bg-[#CA8A78]/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-[#8C4F3E]">
                            <Sparkles size={14} />
                            Secure Gmail access
                        </span>
                        <h1 className="mt-6 text-4xl md:text-6xl font-black leading-[1.05]">
                            Sign in to connect your inbox and documents.
                        </h1>
                        <p className="mt-5 text-base md:text-lg text-[#413632]/70 max-w-2xl leading-relaxed">
                            Use Google OAuth through Supabase so the app can identify the exact Gmail account you used to log in and keep your inbox-driven workflow personal.
                        </p>

                        <div className="mt-8 flex flex-col sm:flex-row gap-4">
                            <button
                                onClick={signInWithGoogle}
                                disabled={loading}
                                className="inline-flex items-center justify-center gap-3 rounded-2xl bg-[#CA8A78] px-6 py-4 font-bold text-[#FFFBF0] shadow-lg shadow-[#CA8A78]/25 transition hover:scale-[1.01] disabled:opacity-60"
                            >
                                <Globe size={18} />
                                {loading ? "Redirecting..." : "Sign in with Google"}
                                <ArrowRight size={16} />
                            </button>
                            <Link
                                href="/auth#signup"
                                className="inline-flex items-center justify-center gap-3 rounded-2xl border-2 border-[#CABDB2]/70 px-6 py-4 font-semibold text-[#413632] hover:border-[#CA8A78] hover:bg-[#FFEAD5]/60 transition"
                            >
                                Don&apos;t have an account? Sign up now
                            </Link>
                        </div>

                        {error ? (
                            <p className="mt-5 rounded-xl border border-[#CA8A78]/25 bg-[#CA8A78]/10 px-4 py-3 text-sm text-[#8C4F3E]">
                                {error}
                            </p>
                        ) : null}

                        {user ? (
                            <div className="mt-6 rounded-2xl border border-[#CABDB2]/70 bg-[#FFFBF0] p-5">
                                <div className="flex items-center gap-3">
                                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#CA8A78]/15 text-[#CA8A78]">
                                        <Mail size={18} />
                                    </div>
                                    <div>
                                        <p className="text-xs uppercase tracking-[0.2em] text-[#413632]/55">Signed in as</p>
                                        <p className="font-semibold">{user.displayName}</p>
                                        <p className="text-sm text-[#413632]/70">{user.email}</p>
                                    </div>
                                </div>
                            </div>
                        ) : null}
                    </div>
                </section>

                <section className="rounded-[2rem] bg-[#413632] text-[#FFFBF0] p-8 md:p-12 shadow-2xl shadow-[#413632]/20 relative overflow-hidden">
                    <div className="absolute -top-10 -right-10 h-48 w-48 rounded-full bg-[#CA8A78]/20 blur-3xl" />
                    <div className="absolute -bottom-10 -left-10 h-56 w-56 rounded-full bg-[#FFEAD5]/10 blur-3xl" />

                    <div className="relative z-10 space-y-6">
                        <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-[#CABDB2]">
                            <ShieldCheck size={14} />
                            Supabase OAuth
                        </div>
                        <h2 className="text-3xl md:text-4xl font-black leading-tight">
                            One login. One Gmail identity. Full inbox context.
                        </h2>
                        <p className="text-[#CABDB2] leading-relaxed">
                            After Google sign-in, we read the authenticated Supabase user profile and use that email everywhere the app needs it, instead of a hardcoded address.
                        </p>

                        <div className="grid gap-4 pt-4">
                            {[
                                "Google OAuth via Supabase",
                                "User email stored from the active session",
                                "Sidebar and inbox-aware views stay in sync",
                            ].map((item) => (
                                <div key={item} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm">
                                    {item}
                                </div>
                            ))}
                        </div>
                    </div>
                </section>
            </div>
        </main>
    );
}
