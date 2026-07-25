import Image from "next/image";
import Link from "next/link";
import { FileText, MessageSquareText, CalendarDays, LayoutDashboard, ArrowRight } from "lucide-react";

export default function DashboardHome() {
    const features = [
        {
            icon: FileText,
            title: "Documents",
            desc: "Browse, upload, and manage your document library with ease.",
            href: "/documents",
            color: "text-[#CA8A78]",
            bg: "bg-[#CA8A78]/10 border-[#CA8A78]/20",
        },
        {
            icon: MessageSquareText,
            title: "Chat with PDF",
            desc: "Select PDFs and ask AI-powered questions in real time.",
            href: "/chat",
            color: "text-[#CA8A78]",
            bg: "bg-[#CA8A78]/10 border-[#CA8A78]/20",
        },
        {
            icon: CalendarDays,
            title: "Calendar",
            desc: "Schedule events with priority highlighting and smart reminders.",
            href: "/calendar",
            color: "text-[#CA8A78]",
            bg: "bg-[#CA8A78]/10 border-[#CA8A78]/20",
        },
    ];

    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-10 font-sans">
            <div className="flex flex-col items-center text-center max-w-2xl gap-6 mb-14">
                <div className="flex items-center justify-center w-20 h-20 rounded-2xl bg-[#FFFBF0] border border-[#CABDB2] shadow-xl shadow-[#CA8A78]/10 p-2">
                    <Image src="/patrerekhaai-logo.png" alt="PatraRekhaAI" width={56} height={56} className="h-14 w-14 object-contain" />
                </div>
                <h1 className="text-4xl font-extrabold tracking-tight text-[#413632]">
                    Welcome to <span className="text-[#CA8A78]">PatraRekhaAI</span>
                </h1>
                <p className="text-[#413632]/80 text-lg leading-relaxed font-sans">
                    Your AI-powered document intelligence suite.
                </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full max-w-4xl">
                {features.map((f) => {
                    const Icon = f.icon;
                    return (
                        <Link
                            key={f.href}
                            href={f.href}
                            className="group flex items-start gap-4 p-5 rounded-2xl border border-[#CABDB2]/60 bg-card hover:border-[#CA8A78] hover:bg-[#FFEAD5]/80 transition-all duration-200"
                        >
                            <div className={`p-2.5 rounded-xl border ${f.bg} shrink-0`}>
                                <Icon size={20} className={f.color} />
                            </div>
                            <div className="min-w-0">
                                <h2 className="text-sm font-bold text-[#413632] flex items-center gap-2">
                                    {f.title}
                                    <ArrowRight
                                        size={13}
                                        className="text-[#CA8A78] opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all"
                                    />
                                </h2>
                                <p className="text-xs text-[#413632]/70 mt-1 leading-relaxed font-sans">{f.desc}</p>
                            </div>
                        </Link>
                    );
                })}
            </div>
        </div>
    );
}
