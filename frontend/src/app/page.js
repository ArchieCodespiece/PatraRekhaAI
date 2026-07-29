"use client";

import Image from "next/image";
import Link from "next/link";
import {
    Sparkles,
    FileText,
    MessageSquareText,
    CalendarDays,
    Shield,
    Zap,
    Globe,
    ArrowRight,
    Search,
    Brain,
    Lock,
    BarChart3,
    Users,
    Star,
} from "lucide-react";
import {
    BlurText,
    SplitText,
    GradientText,
    AnimatedCounter,
    FadeInOnScroll,
    SpotlightCard,
} from "../components/reactbits";
import ScrollVelocity from "../components/ScrollVelocity";
import PillNav from "../components/PillNav";

const features = [
    {
        icon: MessageSquareText,
        title: "Chat with PDF",
        desc: "Select documents and have intelligent AI conversations. Ask questions, summarize findings, and extract key insights.",
        tag: "AI-Powered",
    },
    {
        icon: Search,
        title: "Smart Document Search",
        desc: "Find exactly what you need across thousands of pages with semantic search that understands context, not just keywords.",
        tag: "Intelligent",
    },
    {
        icon: CalendarDays,
        title: "Priority Calendar",
        desc: "Color-coded priority scheduling with high, medium, and normal urgency levels. Never miss a critical deadline.",
        tag: "Organized",
    },
    {
        icon: Brain,
        title: "AI Summarization",
        desc: "Instantly generate concise summaries from lengthy documents. Save hours of reading with smart AI extraction.",
        tag: "Efficient",
    },
    {
        icon: BarChart3,
        title: "Document Analytics",
        desc: "Track document usage, access patterns, and extract trends across your entire document library.",
        tag: "Insightful",
    },
    {
        icon: Lock,
        title: "Enterprise Security",
        desc: "Bank-grade encryption, role-based access control, and complete audit trails for regulatory compliance.",
        tag: "Secure",
    },
];

const stats = [
    { value: 10000, suffix: "+", label: "Documents Processed" },
    { value: 99, suffix: ".9%", label: "Uptime Guarantee" },
    { value: 50, suffix: "x", label: "Faster Insights" },
    { value: 256, suffix: "-bit", label: "Encryption" },
];

const testimonials = [
    {
        quote: "PatraRekhaAI transformed how we handle document workflows. What took hours now takes minutes.",
        author: "Priya Menon",
        role: "Operations Head",
        org: "Metro Rail Corp",
    },
    {
        quote: "The AI chat feature is incredible. It's like having a research assistant that has read every document.",
        author: "Rajesh Kumar",
        role: "Legal Advisor",
        org: "GovernanceAI Labs",
    },
    {
        quote: "Priority calendar with color coding saved us from missing critical compliance deadlines.",
        author: "Ananya Sharma",
        role: "Project Manager",
        org: "DigitalBridge Solutions",
    },
];

const logoNames = [
    "Enterprise AI", "GovTech", "MetroRail", "DocuSign", "LegalTech",
    "SmartCity", "DataBridge", "CloudFirst", "SecureDoc", "InfoNexus",
];

export default function LandingPage() {
    return (
        <div id="top" className="min-h-screen bg-[#FFFBF0] text-[#413632] font-sans overflow-x-hidden">

            {/* â•â•â•â•â•â•â•â•â•â•â• NAVBAR â•â•â•â•â•â•â•â•â•â•â• */}
            <div className="fixed top-4 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-6xl -translate-x-1/2 items-center justify-between gap-4 px-2 sm:px-0">
                <PillNav
                    className="shrink-0"
                    items={[
                        {
                            label: "PatraRekhaAI",
                            href: "#top",
                            icon: (
                                <Image
                                    src="/patrerekhaai-logo.png"
                                    alt="PatraRekhaAI logo"
                                    width={32}
                                    height={32}
                                    className="h-[32px] w-[32px] object-contain"
                                />
                            ),
                            onClick: (event) => {
                                event.preventDefault();
                                window.scrollTo({ top: 0, behavior: "smooth" });
                            },
                        },
                    ]}
                    itemClassName="px-6 md:px-7 py-3.5 text-base md:text-lg flex items-center gap-3"
                />
                <PillNav
                    className="shrink-0"
                    items={[
                        {
                            label: "Login",
                            href: "/auth",
                            icon: <ArrowRight size={16} />,
                        },
                    ]}
                    itemClassName="px-6 md:px-7 py-3.5 text-base md:text-lg"
                />
            </div>

            {/* â•â•â•â•â•â•â•â•â•â•â• HERO SECTION â•â•â•â•â•â•â•â•â•â•â• */}
            <section className="relative pt-40 pb-20 px-6 overflow-hidden">
                {/* Decorative gradient orbs */}
                <div className="absolute top-20 left-1/4 w-96 h-96 bg-[#CA8A78]/10 rounded-full blur-3xl pointer-events-none" />
                <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-[#FFEAD5]/60 rounded-full blur-3xl pointer-events-none" />

                <div className="relative max-w-5xl mx-auto text-center">
                    {/* Headline with blur text animation */}
                    <FadeInOnScroll delay={100}>
                        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight leading-[1.1] mb-6">
                            Your Documents,{" "}
                            <br className="hidden sm:block" />
                            <GradientText
                                colors={["#CA8A78", "#413632", "#CABDB2", "#CA8A78"]}
                                animationSpeed={5}
                                className="text-5xl md:text-7xl font-extrabold"
                            >
                                Reimagined with AI
                            </GradientText>
                        </h1>
                    </FadeInOnScroll>

                    <FadeInOnScroll delay={200}>
                        <BlurText
                            text="Upload PDFs. Ask questions. Get answers instantly. PatraRekhaAI transforms your static documents into interactive knowledge â€” powering smarter decisions with AI."
                            delay={30}
                            className="text-lg md:text-xl text-[#413632]/70 max-w-2xl mx-auto mb-10 leading-relaxed font-sans"
                        />
                    </FadeInOnScroll>

                    {/* CTA Buttons */}
                    <FadeInOnScroll delay={300}>
                        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                            <Link
                                href="/auth"
                                className="group flex items-center gap-2.5 px-8 py-4 rounded-2xl bg-[#CA8A78] text-[#FFFBF0] font-bold text-base transition-all duration-300 shadow-xl shadow-[#CA8A78]/25 hover:shadow-2xl hover:shadow-[#CA8A78]/30 hover:scale-[1.02] active:scale-95"
                            >
                                <Image
                                    src="/patrerekhaai-logo.png"
                                    alt=""
                                    width={18}
                                    height={18}
                                    className="h-[18px] w-[18px] object-contain mix-blend-multiply"
                                />
                                Get Started Free
                                <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
                            </Link>
                            <a
                                href="#features"
                                className="flex items-center gap-2 px-8 py-4 rounded-2xl border-2 border-[#CABDB2]/60 text-[#413632] font-semibold text-base hover:border-[#CA8A78] hover:bg-[#FFEAD5]/50 transition-all duration-300"
                            >
                                Explore Features
                            </a>
                        </div>
                    </FadeInOnScroll>

                    {/* Hero visual â€“ abstract card mockup */}
                    <FadeInOnScroll delay={500}>
                        <div className="mt-16 relative max-w-4xl mx-auto">
                            <div className="rounded-3xl border border-[#CA8A78]/65 bg-gradient-to-b from-[#FFEAD5] to-[#FFFBF0] p-1 shadow-2xl shadow-[#CA8A78]/15">
                                <div className="rounded-[1.25rem] bg-[#FFFBF0] p-6 md:p-8">
                                    {/* Mock interface */}
                                    <div className="flex items-center gap-3 mb-6">
                                        <div className="flex gap-1.5">
                                            <div className="w-3 h-3 rounded-full bg-[#CA8A78]" />
                                            <div className="w-3 h-3 rounded-full bg-[#CABDB2]" />
                                            <div className="w-3 h-3 rounded-full bg-[#CABDB2]/70" />
                                        </div>
                                        <div className="flex-1 h-8 rounded-lg bg-[#FFEAD5] border border-[#CA8A78]/60 flex items-center px-3">
                                            <Search size={13} className="text-[#413632]/75" />
                                            <span className="ml-2 text-xs text-[#413632]/75">Ask anything about your documents...</span>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                        <div className="col-span-2 space-y-3">
                                            <div className="h-4 bg-[#413632]/30 rounded w-4/5" />
                                            <div className="h-4 bg-[#413632]/22 rounded w-3/5" />
                                            <div className="h-4 bg-[#413632]/16 rounded w-2/3" />
                                            <div className="mt-4 p-4 rounded-xl bg-[#FFEAD5] border border-[#CA8A78]/60">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <Brain size={14} className="text-[#CA8A78]" />
                                                    <span className="text-xs font-semibold text-[#CA8A78]">AI Response</span>
                                                </div>
                                                <div className="h-3 bg-[#CA8A78]/60 rounded w-full mb-1.5" />
                                                <div className="h-3 bg-[#CA8A78]/45 rounded w-4/5" />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            {["Financial Report.pdf", "Tech Spec.pdf", "Proposal.pdf"].map((name) => (
                                                <div key={name} className="flex items-center gap-2 p-2.5 rounded-lg bg-[#FFEAD5] border border-[#CA8A78]/50">
                                                    <FileText size={14} className="text-[#CA8A78] shrink-0" />
                                                    <span className="text-[11px] font-medium text-[#413632]/80 truncate">{name}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </FadeInOnScroll>
                </div>
            </section>

            {/* â•â•â•â•â•â•â•â•â•â•â• TRUSTED BY / MARQUEE â•â•â•â•â•â•â•â•â•â•â• */}
            <section className="py-12 border-y border-[#CABDB2]/20">
                <p className="text-center text-sm md:text-base font-semibold uppercase tracking-widest text-[#413632] mb-8 md:mb-10">
                    Trusted by forward-thinking organizations
                </p>
                <ScrollVelocity
                    texts={[
                        <span key="organizations" className="inline-flex items-center gap-10">
                            {logoNames.map((name) => (
                                <span key={name}>{name}</span>
                            ))}
                        </span>,
                    ]}
                    velocity={48}
                    numCopies={8}
                    className="pr-10 text-xl md:text-2xl font-bold text-[#413632]/75 whitespace-nowrap"
                />
            </section>

            {/* â•â•â•â•â•â•â•â•â•â•â• STATS â•â•â•â•â•â•â•â•â•â•â• */}
            <section className="py-20 px-6">
                <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-10 md:gap-12">
                    {stats.map((s, i) => (
                        <FadeInOnScroll key={s.label} delay={i * 100}>
                            <div className="text-center">
                                <div className="text-4xl md:text-6xl font-extrabold tracking-tight text-[#CA8A78]">
                                    <AnimatedCounter target={s.value} duration={2000} />
                                    {s.suffix}
                                </div>
                                <p className="text-base md:text-lg text-[#413632]/65 mt-2 font-medium">{s.label}</p>
                            </div>
                        </FadeInOnScroll>
                    ))}
                </div>
            </section>

            {/* â•â•â•â•â•â•â•â•â•â•â• FEATURES GRID â•â•â•â•â•â•â•â•â•â•â• */}
            <section id="features" className="py-20 px-6">
                <div className="max-w-6xl mx-auto">
                    <FadeInOnScroll>
                        <div className="text-center mb-14">
                            <SplitText
                                text="Everything you need for intelligent documents"
                                animateBy="words"
                                delay={70}
                                className="text-3xl md:text-5xl font-black tracking-tight text-[#413632] font-heading leading-[1.05]"
                            />
                            <BlurText
                                text="From AI-powered conversations to priority scheduling — PatraRekhaAI brings the future of document management to your fingertips."
                                delay={18}
                                className="text-[#413632]/62 mt-4 max-w-2xl mx-auto text-base md:text-lg leading-relaxed font-sans"
                            />
                        </div>
                    </FadeInOnScroll>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                        {features.map((f, i) => {
                            const Icon = f.icon;
                            return (
                                <FadeInOnScroll key={f.title} delay={i * 80}>
                                    <SpotlightCard className="h-full">
                                        <div className="p-6">
                                            <div className="flex items-center justify-between mb-4">
                                                <div className="w-11 h-11 rounded-xl bg-[#CA8A78]/15 border border-[#CA8A78]/20 flex items-center justify-center">
                                                    <Icon size={20} className="text-[#CA8A78]" />
                                                </div>
                                                <span className="text-[10px] font-bold uppercase tracking-wider text-[#CA8A78] px-2.5 py-1 rounded-full bg-[#CA8A78]/10 border border-[#CA8A78]/20">
                                                    {f.tag}
                                                </span>
                                            </div>
                                            <h3 className="text-base font-bold text-[#413632] mb-2">{f.title}</h3>
                                            <p className="text-sm text-[#413632]/60 leading-relaxed font-sans">{f.desc}</p>
                                        </div>
                                    </SpotlightCard>
                                </FadeInOnScroll>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* â•â•â•â•â•â•â•â•â•â•â• HOW IT WORKS â•â•â•â•â•â•â•â•â•â•â• */}
            <section id="how-it-works" className="py-20 px-6 bg-gradient-to-b from-[#F3E0D0] via-[#F8ECDD] to-[#F9F1E5]">
                <div className="max-w-5xl mx-auto">
                    <FadeInOnScroll>
                        <div className="text-center mb-14">
                            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#413632]">
                                Three steps to smarter documents
                            </h2>
                        </div>
                    </FadeInOnScroll>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                        {[
                            {
                                step: "01",
                                title: "Upload Documents",
                                desc: "Drag and drop your PDFs into PatraRekhaAI. We support all document formats with instant processing.",
                                icon: FileText,
                            },
                            {
                                step: "02",
                                title: "Ask Questions",
                                desc: "Select documents and chat with AI. Get instant answers, summaries, and cross-document insights.",
                                icon: MessageSquareText,
                            },
                            {
                                step: "03",
                                title: "Take Action",
                                desc: "Schedule tasks, set priorities, and collaborate with your team. Turn insights into results.",
                                icon: CalendarDays,
                            },
                        ].map((item, i) => {
                            const Icon = item.icon;
                            return (
                                <FadeInOnScroll key={item.step} delay={i * 150}>
                                    <div className="relative text-center p-8 rounded-2xl bg-[#FBF4EA] border border-[#CABDB2]/45 hover:border-[#CA8A78]/45 transition-all duration-300 hover:shadow-lg hover:shadow-[#CA8A78]/8">
                                        <div className="text-6xl font-extrabold text-[#8C4F3E]/22 absolute top-4 right-6 select-none">
                                            {item.step}
                                        </div>
                                        <div className="w-14 h-14 rounded-2xl bg-[#CA8A78]/10 border border-[#CA8A78]/20 flex items-center justify-center mx-auto mb-5">
                                            <Icon size={24} className="text-[#CA8A78]" />
                                        </div>
                                        <h3 className="text-lg font-bold text-[#413632] mb-2">{item.title}</h3>
                                        <p className="text-sm text-[#413632]/60 leading-relaxed font-sans">{item.desc}</p>
                                    </div>
                                </FadeInOnScroll>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* â•â•â•â•â•â•â•â•â•â•â• TESTIMONIALS â•â•â•â•â•â•â•â•â•â•â• */}
            <section id="testimonials" className="py-20 px-6">
                <div className="max-w-5xl mx-auto">
                    <FadeInOnScroll>
                        <div className="text-center mb-14">
                            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#413632]">
                                Loved by teams everywhere
                            </h2>
                        </div>
                    </FadeInOnScroll>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
                        {testimonials.map((t, i) => (
                            <FadeInOnScroll key={t.author} delay={i * 120}>
                                <SpotlightCard className="group h-full">
                                    <div className="p-6 flex flex-col h-full min-h-[260px] transition-colors duration-300 group-hover:text-[#2E221D]">
                                        <div className="flex gap-1 mb-4">
                                            {[1, 2, 3, 4, 5].map((s) => (
                                                <Star
                                                    key={s}
                                                    className="h-4 w-4 fill-[#CA8A78] text-[#CA8A78] transition-all duration-300 group-hover:fill-[#8C4F3E] group-hover:text-[#8C4F3E] group-hover:drop-shadow-[0_0_8px_rgba(202,138,120,0.55)] group-hover:scale-110"
                                                />
                                            ))}
                                        </div>
                                        <p className="text-sm text-[#413632]/80 leading-relaxed flex-1 italic font-sans">
                                            &ldquo;{t.quote}&rdquo;
                                        </p>
                                        <div className="mt-4 pt-4 border-t border-[#CABDB2]/30">
                                            <p className="text-sm font-bold text-[#413632]">{t.author}</p>
                                            <p className="text-xs text-[#413632]/55 font-sans leading-relaxed">{t.role}, {t.org}</p>
                                        </div>
                                    </div>
                                </SpotlightCard>
                            </FadeInOnScroll>
                        ))}
                    </div>
                </div>
            </section>

            {/* â•â•â•â•â•â•â•â•â•â•â• CTA SECTION â•â•â•â•â•â•â•â•â•â•â• */}
            <section className="py-20 px-6">
                <FadeInOnScroll>
                    <div className="max-w-4xl mx-auto rounded-3xl bg-gradient-to-br from-[#413632] to-[#413632]/90 p-12 md:p-16 text-center relative overflow-hidden">
                        {/* Decorative orb */}
                        <div className="absolute top-0 right-0 w-64 h-64 bg-[#CA8A78]/20 rounded-full blur-3xl pointer-events-none" />
                        <div className="absolute bottom-0 left-0 w-48 h-48 bg-[#CA8A78]/10 rounded-full blur-3xl pointer-events-none" />

                        <div className="relative z-10">
                            <div className="w-14 h-14 rounded-2xl bg-[#CA8A78] flex items-center justify-center mx-auto mb-6 shadow-lg shadow-[#CA8A78]/30">
                                <Image
                                    src="/patrerekhaai-logo.png"
                                    alt=""
                                    width={24}
                                    height={24}
                                    className="h-6 w-6 object-contain mix-blend-multiply"
                                />
                            </div>
                            <h2 className="text-3xl md:text-4xl font-extrabold text-[#FFFBF0] mb-4 tracking-tight">
                                Ready to transform your documents?
                            </h2>
                            <p className="text-[#CABDB2] text-base max-w-lg mx-auto mb-8 font-sans">
                                Join organizations already using PatraRekhaAI to unlock intelligence from their documents.
                            </p>
                            <Link
                                href="/auth"
                                className="group inline-flex items-center gap-2.5 px-8 py-4 rounded-2xl bg-[#CA8A78] text-[#FFFBF0] font-bold text-base transition-all duration-300 shadow-xl shadow-[#CA8A78]/30 hover:shadow-2xl hover:shadow-[#CA8A78]/40 hover:scale-[1.02] active:scale-95"
                            >
                                Start for Free
                                <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
                            </Link>
                        </div>
                    </div>
                </FadeInOnScroll>
            </section>

            {/* â•â•â•â•â•â•â•â•â•â•â• FOOTER â•â•â•â•â•â•â•â•â•â•â• */}
            <footer className="border-t border-[#CABDB2]/30 py-12 px-6">
                <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
                    <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-[#CA8A78] flex items-center justify-center">
                            <Image
                                src="/patrerekhaai-logo.png"
                                alt=""
                                width={14}
                                height={14}
                                className="h-[14px] w-[14px] object-contain"
                            />
                        </div>
                        <span className="font-bold text-sm">
                            Patra<span className="text-[#CA8A78]">RekhaAI</span>
                        </span>
                    </div>
                    <div className="flex items-center gap-6 text-xs text-[#413632]/50 font-medium font-sans">
                        <a href="#features" className="hover:text-[#CA8A78] transition">Features</a>
                        <a href="#how-it-works" className="hover:text-[#CA8A78] transition">How It Works</a>
                        <a href="#testimonials" className="hover:text-[#CA8A78] transition">Testimonials</a>
                    </div>
                    <p className="text-xs text-[#413632]/40 font-sans">
                        Â© 2026 PatraRekhaAI. All rights reserved.
                    </p>
                </div>
            </footer>
        </div>
    );
}

