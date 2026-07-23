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
        <aside className="w-64 h-screen bg-sidebar text-sidebar-foreground flex flex-col justify-between border-r border-sidebar-border p-4 select-none">
            {/* Top Section */}
            <div className="space-y-6">
                {/* Brand Logo & Header */}
                <div className="flex items-center gap-3 px-3 py-2">
                    <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-primary text-primary-foreground shadow-md shadow-[#CA8A78]/20">
                        <Sparkles size={20} className="animate-pulse" />
                    </div>
                    <div>
                        <h1 className="text-base font-bold text-sidebar-foreground tracking-wide leading-tight">
                            Patra<span className="text-[#CA8A78]">RekhaAI</span>
                        </h1>
                        <p className="text-[11px] text-[#CABDB2] font-medium">Document Intelligence Suite</p>
                    </div>
                </div>

                {/* Divider */}
                <div className="h-[1px] bg-[#CABDB2]/50 mx-2" />

                {/* Navigation Menu */}
                <nav className="space-y-1.5">
                    <p className="px-3 text-[10px] font-semibold text-[#CABDB2] uppercase tracking-wider mb-2">
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
                                        ? "bg-primary text-primary-foreground shadow-lg shadow-[#CA8A78]/25"
                                        : "text-[#CABDB2] hover:text-sidebar-foreground hover:bg-[#CABDB2]/15"
                                }`}
                            >
                                <div className="flex items-center gap-3">
                                    <Icon
                                        size={18}
                                        className={`transition-colors duration-200 ${
                                            active
                                                ? "text-primary-foreground"
                                                : "text-[#CABDB2] group-hover:text-sidebar-foreground"
                                        }`}
                                    />
                                    <span>{item.title}</span>
                                </div>

                                {/* Optional Badge or Right Arrow Indicator */}
                                {item.badge ? (
                                    <span
                                        className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${
                                            active
                                                ? "bg-primary-foreground/20 text-primary-foreground"
                                                : "bg-[#CABDB2]/15 text-[#CABDB2] border border-[#CABDB2]/30"
                                        }`}
                                    >
                                        {item.badge}
                                    </span>
                                ) : (
                                    <ChevronRight
                                        size={14}
                                        className={`opacity-0 -translate-x-1 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0 ${
                                            active ? "hidden" : "text-[#CABDB2]"
                                        }`}
                                    />
                                )}
                            </Link>
                        );
                    })}
                </nav>
            </div>

            {/* Bottom User / Footer Section */}
            <div className="space-y-3 pt-4 border-t border-[#CABDB2]/50">
                <div className="flex items-center justify-between p-2 rounded-xl bg-[#CABDB2]/10 border border-[#CABDB2]/30">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-[#CABDB2]/20 flex items-center justify-center font-bold text-xs text-sidebar-foreground">
                            AD
                        </div>
                        <div className="text-xs">
                            <p className="font-semibold text-sidebar-foreground">Admin User</p>
                            <p className="text-[#CABDB2] text-[10px]">admin@patrarekha.ai</p>
                        </div>
                    </div>
                    <button
                        title="Logout"
                        className="text-[#CABDB2] hover:text-primary transition-colors p-1.5 rounded-lg hover:bg-[#CABDB2]/20"
                    >
                        <LogOut size={16} />
                    </button>
                </div>
            </div>
        </aside>
    );
}
