"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { useRouter } from "next/navigation";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    FileText,
    MessageSquareText,
    CalendarDays,
    LogOut,
    ChevronRight,
    Menu,
    X,
    Sun,
    Moon,
} from "lucide-react";

import { getStoredAuthUser, signOut } from "../lib/supabaseAuth";
import { useI18n } from "../lib/i18n/I18nContext";
import LanguageSelector from "./LanguageSelector";


const links = (t) => [
    {
        title: t("sidebar.dashboard"),
        href: "/dashboard",
        icon: LayoutDashboard,
    },
    {
        title: t("sidebar.documents"),
        href: "/document",
        icon: FileText,
    },
    {
        title: t("sidebar.chatWithPdf"),
        href: "/chat",
        icon: MessageSquareText,
    },
    {
        title: t("sidebar.calendar"),
        href: "/calendar",
        icon: CalendarDays,
    },
];

export default function Sidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const { t, isRTL } = useI18n();
    const [user, setUser] = useState(null);
    const [isLoggingOut, setIsLoggingOut] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);

    const navLinks = links(t);

    useEffect(() => {
        const onStorage = () => setUser(getStoredAuthUser());
        window.addEventListener("storage", onStorage);
        window.addEventListener("focus", onStorage);

        const timeoutId = setTimeout(() => {
            setUser(getStoredAuthUser());
        }, 0);

        return () => {
            window.removeEventListener("storage", onStorage);
            window.removeEventListener("focus", onStorage);
            clearTimeout(timeoutId);
        };
    }, []);

    useEffect(() => {
        setMobileOpen(false);
    }, [pathname]);

    const closeMobile = useCallback(() => setMobileOpen(false), []);

    const [darkMode, setDarkMode] = useState(() => {
        if (typeof window === "undefined") return false;
        return localStorage.getItem("patrerekha:theme") === "dark"
            || (!localStorage.getItem("patrerekha:theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
    });

    useEffect(() => {
        if (darkMode) {
            document.documentElement.classList.add("dark");
        } else {
            document.documentElement.classList.remove("dark");
        }
        localStorage.setItem("patrerekha:theme", darkMode ? "dark" : "light");
    }, [darkMode]);

    const toggleDarkMode = useCallback(() => setDarkMode((prev) => !prev), []);

    const sidebarContent = (
        <>
            <div className="space-y-6">
                <Link href="/dashboard" className="group flex items-center gap-3 rounded-2xl px-2 py-2 transition-colors hover:bg-white/5">
                    <motion.div
                        whileHover={{ rotate: -3, scale: 1.03 }}
                        className="flex h-11 w-11 items-center justify-center rounded-xl border border-sidebar-border bg-background p-1 shadow-md shadow-black/10"
                    >
                        <Image src="/patrerekhaai-logo.png" alt="PatraRekhaAI" width={40} height={40} className="h-10 w-10 object-contain" />
                    </motion.div>
                    <div className="min-w-0">
                        <h1 className="text-base font-bold tracking-wide leading-tight text-sidebar-foreground">
                            Patra<span className="text-primary">RekhaAI</span>
                        </h1>
                        <p className="truncate text-[10px] font-medium text-sidebar-foreground/70">{t("sidebar.documentIntelligence")}</p>
                    </div>
                </Link>

                <LanguageSelector />

                <div className="h-px bg-gradient-to-r from-sidebar-border via-sidebar-border/40 to-transparent" />

                <nav className="space-y-1.5">
                    <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/60">{t("sidebar.workspace")}</p>
                    {navLinks.map((item) => {
                        const Icon = item.icon;
                        const active = pathname === item.href;
                        return (
                            <Link key={item.href} href={item.href} className="group relative block rounded-xl">
                                {active && (
                                    <motion.div
                                        layoutId="sidebar-active"
                                        className="absolute inset-0 rounded-xl bg-sidebar-primary shadow-lg shadow-sidebar-primary/25"
                                        transition={{ type: "spring", stiffness: 420, damping: 32 }}
                                    />
                                )}
                                <div className={`relative flex items-center justify-between rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors duration-200 ${active ? "text-sidebar-primary-foreground" : "text-sidebar-foreground/75 hover:bg-white/5 hover:text-sidebar-foreground"}`}>
                                    <div className="flex items-center gap-3">
                                        <motion.div animate={{ scale: active ? 1.03 : 1 }} transition={{ duration: 0.15 }}>
                                            <Icon size={18} />
                                        </motion.div>
                                        <span>{item.title}</span>
                                    </div>
                                    <ChevronRight size={14} className="opacity-0 -translate-x-1 text-sidebar-foreground/60 transition-all duration-200 group-hover:translate-x-0 group-hover:opacity-100" />
                                </div>
                            </Link>
                        );
                    })}
                </nav>
            </div>

            <div className="border-t border-sidebar-border pt-4">
                <div className="flex items-center gap-3 rounded-2xl border border-sidebar-border bg-white/[0.035] p-2.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sidebar-primary/20 text-xs font-bold text-sidebar-foreground">
                        {user?.displayName?.slice(0, 2)?.toUpperCase() || "GU"}
                    </div>
                    <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-semibold text-sidebar-foreground">{user?.displayName || t("sidebar.guest")}</p>
                        <p className="truncate text-[10px] text-sidebar-foreground/65">{user?.email || t("sidebar.signIn")}</p>
                    </div>
                    <motion.button
                        type="button"
                        title={t("sidebar.logout")}
                        whileHover={isLoggingOut ? {} : { scale: 1.05 }}
                        whileTap={isLoggingOut ? {} : { scale: 0.95 }}
                        onClick={async () => {
                            if (isLoggingOut) return;
                            setIsLoggingOut(true);
                            try {
                                await signOut();
                            } catch (err) {
                                console.error("Logout failed:", err);
                            } finally {
                                router.push("/");
                                setIsLoggingOut(false);
                            }
                        }}
                        disabled={isLoggingOut}
                        className="rounded-lg p-1.5 text-sidebar-foreground/70 transition-colors hover:bg-white/10 hover:text-sidebar-foreground disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isLoggingOut ? (
                            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                        ) : (
                            <LogOut size={16} />
                        )}
                    </motion.button>
                    <motion.button
                        type="button"
                        title={darkMode ? "Light mode" : "Dark mode"}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={toggleDarkMode}
                        className="rounded-lg p-1.5 text-sidebar-foreground/70 transition-colors hover:bg-white/10 hover:text-sidebar-foreground"
                    >
                        {darkMode ? <Sun size={16} /> : <Moon size={16} />}
                    </motion.button>
                </div>
            </div>
        </>
    );

    return (
        <>
            {/* Mobile hamburger */}
            <button
                type="button"
                onClick={() => setMobileOpen(true)}
                className="fixed left-4 top-4 z-50 flex h-10 w-10 items-center justify-center rounded-xl border border-sidebar-border bg-sidebar text-sidebar-foreground/80 shadow-lg lg:hidden"
                aria-label="Open menu"
            >
                <Menu size={20} />
            </button>

            {/* Desktop sidebar */}
            <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col justify-between border-r border-sidebar-border bg-sidebar p-4 text-sidebar-foreground select-none lg:flex">
                {sidebarContent}
            </aside>

            {/* Mobile drawer */}
            <AnimatePresence>
                {mobileOpen && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={closeMobile}
                            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
                        />
                        <motion.aside
                            initial={{ x: -280 }}
                            animate={{ x: 0 }}
                            exit={{ x: -280 }}
                            transition={{ type: "spring", stiffness: 300, damping: 30 }}
                            className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col justify-between border-r border-sidebar-border bg-sidebar p-4 text-sidebar-foreground select-none lg:hidden"
                        >
                            <button
                                type="button"
                                onClick={closeMobile}
                                className="absolute right-3 top-3 rounded-lg p-1.5 text-sidebar-foreground/70 hover:bg-white/10"
                                aria-label="Close menu"
                            >
                                <X size={18} />
                            </button>
                            {sidebarContent}
                        </motion.aside>
                    </>
                )}
            </AnimatePresence>
        </>
    );

}