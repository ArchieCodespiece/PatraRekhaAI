"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    FileText,
    MessageSquareText,
    CalendarDays,
    Sparkles,
    LogOut,
    ChevronRight,
} from "lucide-react";

const links = [
    {
        title: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
    },
    {
        title: "Documents",
        href: "/documents",
        icon: FileText,
    },
    {
        title: "Chat with PDF",
        href: "/chat",
        icon: MessageSquareText,
        badge: "AI",
    },
    {
        title: "Calendar",
        href: "/calendar",
        icon: CalendarDays,
    },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="w-64 h-screen bg-slate-900 text-slate-300 flex flex-col justify-between border-r border-slate-800 p-4 select-none">
            {/* Top Section */}
            <div className="space-y-6">
                {/* Brand Logo & Header */}
                <div className="flex items-center gap-3 px-3 py-2">
                    <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-600 text-white shadow-md shadow-blue-500/20">
                        <Sparkles size={20} className="animate-pulse" />
                    </div>
                    <div>
                        <h1 className="text-base font-bold text-white tracking-wide leading-tight">
                            KMRL <span className="text-blue-400">AI Hub</span>
                        </h1>
                        <p className="text-[11px] text-slate-400 font-medium">Enterprise Suite</p>
                    </div>
                </div>

                {/* Divider */}
                <div className="h-[1px] bg-slate-800/80 mx-2" />

                {/* Navigation Menu */}
                <nav className="space-y-1.5">
                    <p className="px-3 text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                        Main Navigation
                    </p>
                    {links.map((item) => {
                        const Icon = item.icon;
                        const active = pathname === item.href;

                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`group relative flex items-center justify-between rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all duration-200 ease-in-out ${
                                    active
                                        ? "bg-blue-600 text-white shadow-lg shadow-blue-600/25"
                                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                                }`}
                            >
                                <div className="flex items-center gap-3">
                                    <Icon
                                        size={18}
                                        className={`transition-colors duration-200 ${
                                            active
                                                ? "text-white"
                                                : "text-slate-400 group-hover:text-slate-200"
                                        }`}
                                    />
                                    <span>{item.title}</span>
                                </div>

                                {/* Optional Badge or Right Arrow Indicator */}
                                {item.badge ? (
                                    <span
                                        className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${
                                            active
                                                ? "bg-blue-500 text-white"
                                                : "bg-blue-950/80 text-blue-400 border border-blue-800/50"
                                        }`}
                                    >
                                        {item.badge}
                                    </span>
                                ) : (
                                    <ChevronRight
                                        size={14}
                                        className={`opacity-0 -translate-x-1 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0 ${
                                            active ? "hidden" : "text-slate-500"
                                        }`}
                                    />
                                )}
                            </Link>
                        );
                    })}
                </nav>
            </div>

            {/* Bottom User / Footer Section */}
            <div className="space-y-3 pt-4 border-t border-slate-800/80">
                <div className="flex items-center justify-between p-2 rounded-xl bg-slate-800/40 border border-slate-800">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center font-bold text-xs text-slate-200">
                            AD
                        </div>
                        <div className="text-xs">
                            <p className="font-semibold text-slate-200">Admin User</p>
                            <p className="text-slate-500 text-[10px]">admin@kmrl.co.in</p>
                        </div>
                    </div>
                    <button
                        title="Logout"
                        className="text-slate-400 hover:text-rose-400 transition-colors p-1.5 rounded-lg hover:bg-slate-700/50"
                    >
                        <LogOut size={16} />
                    </button>
                </div>
            </div>
        </aside>
    );
}