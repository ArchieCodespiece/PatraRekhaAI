
"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import {
    ArrowRight,
    CalendarDays,
    CheckCircle2,
    FileText,
    Mail,
    MessageSquareText,
} from "lucide-react";

import {
    buildGmailConnectUrl,
    fetchGmailConnectionStatus,
    getStoredAuthUser,
    startGmailActivityHeartbeat,
} from "../../../lib/supabaseAuth";

export default function DashboardHome() {
    const [user] = useState(() => getStoredAuthUser());

    const [gmailStatus, setGmailStatus] = useState({
        connected: false,
    });

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (!user?.email) {
            return;
        }

        /*
         * IMPORTANT:
         *
         * Start the Gmail heartbeat whenever the dashboard
         * is loaded.
         *
         * This also happens after a browser refresh.
         *
         * If Gmail was previously marked inactive because the
         * browser was minimized for more than 180 seconds:
         *
         *     dashboard refresh
         *          ↓
         *     heartbeat starts
         *          ↓
         *     backend touch_gmail_connection()
         *          ↓
         *     Gmail becomes ACTIVE again
         *
         * No new Google OAuth connection is created.
         */
        startGmailActivityHeartbeat();

        /*
         * Load the current Gmail connection information.
         */
        fetchGmailConnectionStatus(user.email)
            .then(setGmailStatus)
            .catch((err) =>
                setError(
                    err.message ||
                    "Unable to load Gmail status."
                )
            );
    }, [user?.email]);

    const connectGmail = async () => {
        if (!user?.email) {
            return;
        }

        setLoading(true);
        setError("");

        try {
            window.location.href =
                await buildGmailConnectUrl(
                    user.email
                );
        } catch (err) {
            setError(
                err.message ||
                "Unable to start Gmail connect."
            );

            setLoading(false);
        }
    };

    const features = [
        {
            icon: FileText,
            title: "Documents",
            desc: "Browse, upload, and manage your document library with ease.",
            href: "/document",
        },
        {
            icon: MessageSquareText,
            title: "Chat with PDF",
            desc: "Select PDFs and ask AI-powered questions in real time.",
            href: "/chat",
        },
        {
            icon: CalendarDays,
            title: "Calendar",
            desc: "Schedule events with priority highlighting and smart reminders.",
            href: "/calendar",
        },
    ];

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-6 md:p-10 font-sans">

            <div className="w-full max-w-5xl grid gap-6">

                <div className="rounded-[2rem] border border-[#CABDB2]/70 bg-white/70 backdrop-blur-md shadow-2xl shadow-[#CA8A78]/10 p-6 md:p-8">

                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">

                        <div className="flex items-center gap-4">

                            <div className="flex items-center justify-center w-20 h-20 rounded-2xl bg-[#FFFBF0] border border-[#CABDB2] shadow-xl shadow-[#CA8A78]/10 p-2">

                                <Image
                                    src="/patrerekhaai-logo.png"
                                    alt="PatraRekhaAI"
                                    width={56}
                                    height={56}
                                    className="h-14 w-14 object-contain"
                                />

                            </div>

                            <div>

                                <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#413632]">
                                    Welcome to{" "}
                                    <span className="text-[#CA8A78]">
                                        PatraRekhaAI
                                    </span>
                                </h1>

                                <p className="text-[#413632]/80 text-base md:text-lg leading-relaxed font-sans mt-2">
                                    Your AI-powered document intelligence suite.
                                </p>

                                {user?.email ? (
                                    <p className="mt-2 text-sm text-[#413632]/60">
                                        Signed in as {user.email}
                                    </p>
                                ) : null}

                            </div>

                        </div>

                        <div className="rounded-2xl border border-[#CABDB2]/70 bg-[#FFFBF0] p-4 min-w-[280px]">

                            <div className="flex items-center gap-3">

                                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#CA8A78]/15 text-[#CA8A78]">
                                    <Mail size={18} />
                                </div>

                                <div className="min-w-0">

                                    <p className="text-xs uppercase tracking-[0.2em] text-[#413632]/55">
                                        Gmail connection
                                    </p>

                                    <p className="font-semibold text-sm">
                                        {gmailStatus.connected
                                            ? "Connected"
                                            : "Not connected"}
                                    </p>

                                    <p className="text-xs text-[#413632]/70 truncate">
                                        {gmailStatus.connection?.google_email ||
                                            user?.email ||
                                            "No inbox linked yet"}
                                    </p>

                                </div>

                            </div>

                            <button
                                onClick={connectGmail}
                                disabled={
                                    !user?.email ||
                                    loading
                                }
                                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#CA8A78] px-4 py-3 text-sm font-bold text-[#FFFBF0] shadow-lg shadow-[#CA8A78]/20 transition hover:scale-[1.01] disabled:opacity-50"
                            >
                                <CheckCircle2 size={16} />

                                {loading
                                    ? "Opening Google..."
                                    : gmailStatus.connected
                                        ? "Reconnect Gmail"
                                        : "Connect Gmail"}
                            </button>

                            {error ? (
                                <p className="mt-3 text-xs text-[#8C4F3E]">
                                    {error}
                                </p>
                            ) : null}

                        </div>

                    </div>

                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full">

                    {features.map((f) => {

                        const Icon = f.icon;

                        return (
                            <Link
                                key={f.href}
                                href={f.href}
                                className="group flex items-start gap-4 p-5 rounded-2xl border border-[#CABDB2]/60 bg-card hover:border-[#CA8A78] hover:bg-[#FFEAD5]/80 transition-all duration-200"
                            >

                                <div className="p-2.5 rounded-xl border bg-[#CA8A78]/10 border-[#CA8A78]/20 shrink-0">

                                    <Icon
                                        size={20}
                                        className="text-[#CA8A78]"
                                    />

                                </div>

                                <div className="min-w-0">

                                    <h2 className="text-sm font-bold text-[#413632] flex items-center gap-2">

                                        {f.title}

                                        <ArrowRight
                                            size={13}
                                            className="text-[#CA8A78] opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all"
                                        />

                                    </h2>

                                    <p className="text-xs text-[#413632]/70 mt-1 leading-relaxed font-sans">
                                        {f.desc}
                                    </p>

                                </div>

                            </Link>
                        );
                    })}

                </div>

            </div>

        </div>
    );
}

