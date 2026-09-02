"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import {
    motion,
    useInView,
    AnimatePresence,
} from "motion/react";
import {
    MessageSquareText,
    CalendarDays,
    Brain,
    Search,
    Globe,
    ShieldCheck,
    ArrowRight,
    Layers,
    ChevronDown,
    Menu,
    X,
} from "lucide-react";

import {
    AnimatedCounter,
    SpotlightCard,
    GradientText,
} from "../components/reactbits";
import ScrollVelocity from "../components/ScrollVelocity";
import {
    fadeUp,
    fadeIn,
    staggerContainer,
    slideInLeft,
    slideInRight,
    navbarVariant,
} from "../components/motionVariants";
import PatraRekhaDemo from "../components/ui/patrarekha-demo";

/* ─── Data ─────────────────────────────────────────────────────────────── */

const features = [
    {
        icon: MessageSquareText,
        title: "Multi-Document Conversations",
        desc: "Ask questions across multiple institutional documents simultaneously. Get synthesised answers with source attribution.",
        tag: "AI-Powered",
    },
    {
        icon: Brain,
        title: "Intelligent Summarisation",
        desc: "Extract the essential information instead of forcing users to read everything. Both extractive and abstractive modes.",
        tag: "Efficient",
    },
    {
        icon: CalendarDays,
        title: "Deadline & Date Intelligence",
        desc: "Automatically identify important dates and deadlines from documents. Never miss a critical compliance window.",
        tag: "Organised",
    },
    {
        icon: Search,
        title: "Semantic Search",
        desc: "Find relevant information based on meaning, not just keywords. Powered by vector embeddings across your document library.",
        tag: "Intelligent",
    },
    {
        icon: Globe,
        title: "Multilingual Knowledge",
        desc: "Support institutional documents across languages. PatraRekha processes and understands content regardless of language.",
        tag: "Global",
    },
    {
        icon: ShieldCheck,
        title: "Secure Document Processing",
        desc: "Documents are processed in isolated pipelines. Your institutional knowledge remains within your organisation.",
        tag: "Secure",
    },
];

const stats = [
    { value: 10000, suffix: "+", label: "Documents Processed" },
    { value: 99, suffix: ".9%", label: "Pipeline Uptime" },
    { value: 50, suffix: "x", label: "Faster Insights" },
    { value: 6, suffix: "", label: "AI Capabilities" },
];

const workflowSteps = [
    { step: "01", title: "Upload Documents", desc: "Drag-and-drop PDFs, circulars, notices, and reports into PatraRekha. We handle all common document formats with instant processing." },
    { step: "02", title: "Extract & Clean", desc: "Our pipeline extracts text, handles OCR for scanned documents, and cleans the content ready for AI processing." },
    { step: "03", title: "Understand & Analyse", desc: "Named entity recognition, date extraction, and semantic analysis surface the structure hidden inside your documents." },
    { step: "04", title: "Summarise & Index", desc: "Key information is summarised and embedded into a vector index — making every detail instantly searchable." },
    { step: "05", title: "Ask Questions", desc: "Select documents and start a conversation. PatraRekha retrieves the most relevant passages and generates precise answers." },
    { step: "06", title: "Take Action", desc: "Schedule tasks, track deadlines, and share insights. Turn institutional knowledge into organisational action." },
];

const knowledgeSources = [
    "Notices", "Circulars", "Policy Documents", "Annual Reports",
    "Internal Memos", "Compliance Filings", "Contract PDFs", "Meeting Minutes",
];

const logoNames = [
    "Enterprise AI", "GovTech", "MetroRail", "LegalTech",
    "SmartCity", "DataBridge", "CloudFirst", "SecureDoc",
];

const testimonials = [
    {
        quote: "PatraRekha transformed how we handle document workflows. What took hours now takes minutes.",
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
        quote: "Priority calendar with colour coding saved us from missing critical compliance deadlines.",
        author: "Ananya Sharma",
        role: "Project Manager",
        org: "DigitalBridge Solutions",
    },
];

/* ─── Scroll-reveal wrapper ─────────────────────────────────────────────── */

function Reveal({ children, className = "", delay = 0, direction = "up" }) {
    const ref = useRef(null);
    const inView = useInView(ref, { once: true, margin: "-60px" });

    const variants = {
        up: fadeUp,
        left: slideInLeft,
        right: slideInRight,
        plain: fadeIn,
    }[direction] ?? fadeUp;

    return (
        <motion.div
            ref={ref}
            variants={variants}
            initial="hidden"
            animate={inView ? "visible" : "hidden"}
            transition={{ delay: delay / 1000 }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

/* ─── Navbar ────────────────────────────────────────────────────────────── */

function Navbar() {
    const [scrolled, setScrolled] = useState(false);
    const [menuOpen, setMenuOpen] = useState(false);

    useEffect(() => {
        const handler = () => setScrolled(window.scrollY > 20);
        window.addEventListener("scroll", handler, { passive: true });
        return () => window.removeEventListener("scroll", handler);
    }, []);

    const navLinks = [
        { label: "Features", href: "#features" },
        { label: "How It Works", href: "#how-it-works" },
        { label: "Why PatraRekha", href: "#institutional" },
    ];

    return (
        <motion.header
            variants={navbarVariant}
            initial="hidden"
            animate="visible"
            className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
                scrolled
                    ? "bg-[#FFFBF0]/90 backdrop-blur-md border-b border-[#CABDB2]/30 shadow-sm shadow-[#413632]/5"
                    : "bg-transparent"
            }`}
        >
            <div className="max-w-7xl mx-auto px-6 md:px-8 h-16 flex items-center justify-between gap-6">
                {/* Logo */}
                <Link
                    href="/"
                    className="flex items-center gap-2.5 shrink-0 group"
                    aria-label="PatraRekha AI home"
                >
                    <div className="w-8 h-8 rounded-lg bg-[#CA8A78] flex items-center justify-center shadow-sm transition-transform duration-200 group-hover:scale-105">
                        <Image
                            src="/patrerekhaai-logo.png"
                            alt=""
                            width={18}
                            height={18}
                            className="h-[18px] w-[18px] object-contain"
                        />
                    </div>
                    <span className="font-bold text-[15px] tracking-tight text-[#413632]">
                        Patra<span className="text-[#CA8A78]">Rekha</span>
                        <span className="text-[#413632]/50 font-semibold text-xs ml-0.5">AI</span>
                    </span>
                </Link>

                {/* Desktop Nav Links */}
                <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
                    {navLinks.map((link) => (
                        <a
                            key={link.label}
                            href={link.href}
                            className="px-4 py-2 rounded-lg text-sm font-medium text-[#413632]/65 hover:text-[#413632] hover:bg-[#413632]/5 transition-all duration-150"
                        >
                            {link.label}
                        </a>
                    ))}
                </nav>

                {/* Desktop CTA */}
                <div className="hidden md:flex items-center gap-2 shrink-0">
                    <Link
                        href="/auth"
                        className="px-4 py-2 rounded-lg text-sm font-semibold text-[#413632] hover:bg-[#413632]/6 transition-all duration-150"
                    >
                        Sign in
                    </Link>
                    <Link
                        href="/auth"
                        className="group flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#413632] text-[#FFFBF0] text-sm font-semibold transition-all duration-200 hover:bg-[#413632]/85 hover:shadow-md hover:shadow-[#413632]/20 active:scale-95"
                    >
                        Get Started
                        <ArrowRight size={14} className="transition-transform duration-200 group-hover:translate-x-0.5" />
                    </Link>
                </div>

                {/* Mobile menu toggle */}
                <button
                    className="md:hidden p-2 rounded-lg text-[#413632] hover:bg-[#413632]/6 transition-colors"
                    onClick={() => setMenuOpen((o) => !o)}
                    aria-label={menuOpen ? "Close menu" : "Open menu"}
                >
                    {menuOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
            </div>

            {/* Mobile menu */}
            <AnimatePresence>
                {menuOpen && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.22, ease: "easeOut" }}
                        className="md:hidden overflow-hidden bg-[#FFFBF0]/95 backdrop-blur-md border-b border-[#CABDB2]/30"
                    >
                        <div className="px-6 py-4 flex flex-col gap-1">
                            {navLinks.map((link) => (
                                <a
                                    key={link.label}
                                    href={link.href}
                                    onClick={() => setMenuOpen(false)}
                                    className="px-3 py-2.5 rounded-lg text-sm font-medium text-[#413632]/70 hover:text-[#413632] hover:bg-[#413632]/5 transition-all"
                                >
                                    {link.label}
                                </a>
                            ))}
                            <div className="mt-3 pt-3 border-t border-[#CABDB2]/30 flex flex-col gap-2">
                                <Link href="/auth" onClick={() => setMenuOpen(false)} className="px-3 py-2.5 rounded-lg text-sm font-semibold text-[#413632] hover:bg-[#413632]/5 transition-all">
                                    Sign in
                                </Link>
                                <Link href="/auth" onClick={() => setMenuOpen(false)} className="flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[#413632] text-[#FFFBF0] text-sm font-semibold">
                                    Get Started <ArrowRight size={14} />
                                </Link>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.header>
    );
}

/* ─── Workflow Step ─────────────────────────────────────────────────────── */

function WorkflowStep({ step, index }) {
    const ref = useRef(null);
    const inView = useInView(ref, { once: true, margin: "-40px" });
    const isLast = index === workflowSteps.length - 1;

    return (
        <div ref={ref} className="relative flex gap-5 md:gap-6">
            {/* Step number + connector line */}
            <div className="flex flex-col items-center shrink-0">
                <motion.div
                    variants={scaleInVariant}
                    initial="hidden"
                    animate={inView ? "visible" : "hidden"}
                    transition={{ delay: index * 0.1 }}
                    className="w-10 h-10 rounded-full border-2 border-[#CA8A78]/40 bg-[#FFFBF0] flex items-center justify-center z-10 shadow-sm"
                >
                    <span className="text-xs font-black text-[#CA8A78]">{step.step}</span>
                </motion.div>
                {!isLast && (
                    <div className="w-px flex-1 mt-2 bg-gradient-to-b from-[#CABDB2]/50 to-transparent min-h-[2.5rem]" />
                )}
            </div>
            {/* Content */}
            <motion.div
                variants={fadeUp}
                initial="hidden"
                animate={inView ? "visible" : "hidden"}
                transition={{ delay: index * 0.1 + 0.05 }}
                className="pb-8"
            >
                <h3 className="text-base font-bold text-[#413632] mb-1">{step.title}</h3>
                <p className="text-sm text-[#413632]/60 leading-relaxed max-w-lg">{step.desc}</p>
            </motion.div>
        </div>
    );
}

const scaleInVariant = {
    hidden: { opacity: 0, scale: 0.7 },
    visible: { opacity: 1, scale: 1, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } },
};

/* ─── Landing Page ──────────────────────────────────────────────────────── */

export default function LandingPage() {
    return (
        <div className="min-h-screen bg-background text-foreground overflow-x-hidden">

            <Navbar />

            {/* ═══════════════ HERO ═══════════════ */}
            <section className="relative pt-40 md:pt-60 pb-20 px-6 md:px-8 overflow-hidden">
                {/* Subtle background texture */}
                <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute top-32 left-1/3 w-80 h-80 bg-[#CA8A78]/6 rounded-full blur-3xl" />
                    <div className="absolute bottom-0 right-1/4 w-64 h-64 bg-[#FFEAD5]/80 rounded-full blur-3xl" />
                </div>

                <div className="relative max-w-7xl mx-auto">
                    <div className="grid lg:grid-cols-[1fr_auto] gap-12 lg:gap-16 items-center">

                        {/* Left: Text */}
                        <div className="max-w-2xl">
                            {/* Eyebrow */}
                            {/* H1 */}
                            <Reveal delay={80}>
                                <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight leading-[1.08] text-[#413632] mb-5">
                                    Turn documents into{" "}
                                    <GradientText
                                        colors={["#CA8A78", "#8C4F3E", "#CA8A78", "#CABDB2"]}
                                        animationSpeed={6}
                                        className="font-extrabold"
                                    >
                                        knowledge
                                    </GradientText>{" "}
                                    you can actually use.
                                </h1>
                            </Reveal>

                            {/* Subtitle */}
                            <Reveal delay={160}>
                                <p className="text-base md:text-lg text-[#413632]/65 leading-relaxed mb-8 max-w-xl">
                                    PatraRekha AI helps organisations understand, search, summarise
                                    and interact with their institutional documents — notices, reports,
                                    circulars, and more.
                                </p>
                            </Reveal>

                            {/* CTAs */}
                            <Reveal delay={240}>
                                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                                    <Link
                                        href="/auth"
                                        className="group inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#413632] text-[#FFFBF0] font-semibold text-sm transition-all duration-200 hover:bg-[#413632]/85 hover:shadow-lg hover:shadow-[#413632]/20 hover:-translate-y-px active:scale-95"
                                    >
                                        Get Started
                                        <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-0.5" />
                                    </Link>
                                    <a
                                        href="#features"
                                        className="group inline-flex items-center gap-2 px-6 py-3 rounded-xl border border-[#CABDB2]/60 text-[#413632] font-semibold text-sm hover:border-[#CA8A78]/60 hover:bg-[#FFEAD5]/60 transition-all duration-200"
                                    >
                                        Explore PatraRekha
                                        <ChevronDown size={15} className="text-[#413632]/50 transition-transform duration-200 group-hover:translate-y-px" />
                                    </a>
                                </div>
                            </Reveal>

                            {/* Subtle social proof */}
                            <Reveal delay={320}>
                                <div className="mt-8 flex items-center gap-3">
                                    <div className="flex -space-x-2">
                                        {["#CA8A78", "#8C6B5E", "#CABDB2", "#6A4A3E"].map((c, i) => (
                                            <div
                                                key={i}
                                                className="w-7 h-7 rounded-full border-2 border-[#FFFBF0] flex items-center justify-center text-[9px] font-bold text-[#FFFBF0]"
                                                style={{ backgroundColor: c }}
                                            >
                                                {["P", "R", "M", "A"][i]}
                                            </div>
                                        ))}
                                    </div>
                                    <span className="text-xs text-[#413632]/50 font-medium">
                                        Used by institutional teams across sectors
                                    </span>
                                </div>
                            </Reveal>
                        </div>

                        {/* Right: Pipeline visual */}
                        <div className="lg:w-80 xl:w-88">
                            <PatraRekhaDemo />
                        </div>
                    </div>
                </div>
            </section>

            {/* ═══════════════ MARQUEE ═══════════════ */}
            <section className="py-10 border-y border-[#CABDB2]/20 bg-[#FFEAD5]/20">
                <p className="text-center text-[10px] font-bold uppercase tracking-[0.2em] text-[#413632]/40 mb-6">
                    Trusted by forward-thinking organisations
                </p>
                <ScrollVelocity
                    texts={[
                        <span key="orgs" className="inline-flex items-center gap-10">
                            {logoNames.map((name) => (
                                <span key={name} className="inline-flex items-center gap-2">
                                    <span className="w-1 h-1 rounded-full bg-[#CA8A78]/50" />
                                    {name}
                                </span>
                            ))}
                        </span>,
                    ]}
                    velocity={40}
                    numCopies={8}
                    className="pr-10 text-sm md:text-base font-semibold text-[#413632]/50 whitespace-nowrap tracking-wide"
                />
            </section>

            {/* ═══════════════ STATS ═══════════════ */}
            <section className="py-16 px-6 md:px-8">
                <Reveal>
                    <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
                        {stats.map((s, i) => (
                            <div key={s.label}>
                                <div className="text-3xl md:text-4xl font-black tracking-tight text-[#413632]">
                                    <AnimatedCounter target={s.value} duration={1800} />
                                    <span className="text-[#CA8A78]">{s.suffix}</span>
                                </div>
                                <p className="text-xs text-[#413632]/50 mt-1.5 font-medium uppercase tracking-wider">{s.label}</p>
                            </div>
                        ))}
                    </div>
                </Reveal>
            </section>

            {/* ═══════════════ FEATURES ═══════════════ */}
            <section id="features" className="py-20 px-6 md:px-8 bg-[#FFEAD5]/20 border-y border-[#CABDB2]/15">
                <div className="max-w-7xl mx-auto">
                    <Reveal>
                        <div className="mb-12 max-w-2xl">
                            <span className="text-xs font-bold uppercase tracking-widest text-[#CA8A78] mb-3 block">
                                Capabilities
                            </span>
                            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#413632] mb-3">
                                Everything your documents need to become useful.
                            </h2>
                            <p className="text-sm md:text-base text-[#413632]/60 leading-relaxed">
                                PatraRekha combines extraction, understanding, and conversation into one coherent workflow.
                            </p>
                        </div>
                    </Reveal>

                    <motion.div
                        variants={staggerContainer}
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, margin: "-40px" }}
                        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
                    >
                        {features.map((f) => {
                            const Icon = f.icon;
                            return (
                                <motion.div key={f.title} variants={fadeUp}>
                                    <SpotlightCard className="h-full">
                                        <div className="p-6">
                                            <div className="flex items-start justify-between mb-4">
                                                <div className="w-10 h-10 rounded-xl bg-[#CA8A78]/12 border border-[#CA8A78]/18 flex items-center justify-center">
                                                    <Icon size={18} className="text-[#CA8A78]" />
                                                </div>
                                                <span className="text-[9px] font-bold uppercase tracking-wider text-[#CA8A78] px-2 py-1 rounded-full bg-[#CA8A78]/8 border border-[#CA8A78]/18">
                                                    {f.tag}
                                                </span>
                                            </div>
                                            <h3 className="text-sm font-bold text-[#413632] mb-2">{f.title}</h3>
                                            <p className="text-xs text-[#413632]/58 leading-relaxed">{f.desc}</p>
                                        </div>
                                    </SpotlightCard>
                                </motion.div>
                            );
                        })}
                    </motion.div>
                </div>
            </section>

            {/* ═══════════════ HOW IT WORKS ═══════════════ */}
            <section id="how-it-works" className="py-20 px-6 md:px-8">
                <div className="max-w-4xl mx-auto">
                    <Reveal>
                        <div className="mb-12">
                            <span className="text-xs font-bold uppercase tracking-widest text-[#CA8A78] mb-3 block">
                                Pipeline
                            </span>
                            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#413632] mb-3">
                                How PatraRekha works.
                            </h2>
                            <p className="text-sm md:text-base text-[#413632]/60 leading-relaxed max-w-xl">
                                A document pipeline purpose-built for institutional knowledge. From raw upload to actionable insight.
                            </p>
                        </div>
                    </Reveal>

                    <div className="space-y-0">
                        {workflowSteps.map((step, i) => (
                            <WorkflowStep key={step.step} step={step} index={i} />
                        ))}
                    </div>
                </div>
            </section>

            {/* ═══════════════ INSTITUTIONAL KNOWLEDGE ═══════════════ */}
            <section id="institutional" className="py-20 px-6 md:px-8 bg-[#413632] text-[#FFFBF0] overflow-hidden relative">
                <div className="absolute top-0 right-0 w-72 h-72 bg-[#CA8A78]/12 rounded-full blur-3xl pointer-events-none" />
                <div className="absolute bottom-0 left-0 w-56 h-56 bg-[#FFEAD5]/5 rounded-full blur-3xl pointer-events-none" />

                <div className="relative max-w-7xl mx-auto">
                    <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
                        {/* Left: text */}
                        <Reveal direction="left">
                            <div>
                                <span className="text-xs font-bold uppercase tracking-widest text-[#CA8A78] mb-4 block">
                                    The Problem
                                </span>
                                <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-4 leading-tight">
                                    Institutional knowledge is scattered.
                                </h2>
                                <p className="text-[#CABDB2] text-base leading-relaxed mb-6">
                                    Organisations accumulate knowledge across dozens of document types —
                                    each stored in silos, rarely searchable, and almost never connected.
                                </p>
                                <p className="text-[#CABDB2]/80 text-sm leading-relaxed">
                                    PatraRekha transforms this fragmented information into a single,
                                    AI-accessible knowledge layer your team can actually query.
                                </p>
                            </div>
                        </Reveal>

                        {/* Right: source tags */}
                        <Reveal direction="right">
                            <div>
                                <p className="text-[#CABDB2]/60 text-xs font-semibold uppercase tracking-widest mb-5">
                                    Documents PatraRekha understands
                                </p>
                                <div className="flex flex-wrap gap-2.5">
                                    {knowledgeSources.map((src) => (
                                        <span
                                            key={src}
                                            className="px-3 py-1.5 rounded-full border border-white/12 bg-white/6 text-sm font-medium text-[#CABDB2] hover:border-[#CA8A78]/40 hover:text-[#FFFBF0] transition-all duration-200"
                                        >
                                            {src}
                                        </span>
                                    ))}
                                    <span className="px-3 py-1.5 rounded-full border border-[#CA8A78]/30 bg-[#CA8A78]/10 text-sm font-medium text-[#CA8A78]">
                                        + many more
                                    </span>
                                </div>

                                {/* Arrow callout */}
                                <div className="mt-8 flex items-start gap-3 p-4 rounded-xl border border-white/10 bg-white/4">
                                    <div className="w-8 h-8 rounded-lg bg-[#CA8A78]/20 flex items-center justify-center shrink-0 mt-0.5">
                                        <Layers size={14} className="text-[#CA8A78]" />
                                    </div>
                                    <div>
                                        <p className="text-sm font-semibold text-[#FFFBF0] mb-0.5">One knowledge layer</p>
                                        <p className="text-xs text-[#CABDB2]/70 leading-relaxed">
                                            All these document types become a unified, queryable knowledge base.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </Reveal>
                    </div>
                </div>
            </section>

            {/* ═══════════════ TESTIMONIALS ═══════════════ */}
            <section className="py-20 px-6 md:px-8">
                <div className="max-w-6xl mx-auto">
                    <Reveal>
                        <div className="mb-12 text-center">
                            <span className="text-xs font-bold uppercase tracking-widest text-[#CA8A78] mb-3 block">
                                Testimonials
                            </span>
                            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#413632]">
                                Loved by institutional teams.
                            </h2>
                        </div>
                    </Reveal>

                    <motion.div
                        variants={staggerContainer}
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, margin: "-40px" }}
                        className="grid grid-cols-1 md:grid-cols-3 gap-5"
                    >
                        {testimonials.map((t) => (
                            <motion.div key={t.author} variants={fadeUp}>
                                <SpotlightCard className="h-full">
                                    <div className="p-6 flex flex-col h-full min-h-[200px]">
                                        {/* Quote marks */}
                                        <span className="text-3xl font-serif text-[#CA8A78]/40 leading-none mb-2">&ldquo;</span>
                                        <p className="text-sm text-[#413632]/75 leading-relaxed flex-1 italic">
                                            {t.quote}
                                        </p>
                                        <div className="mt-5 pt-4 border-t border-[#CABDB2]/25">
                                            <p className="text-sm font-bold text-[#413632]">{t.author}</p>
                                            <p className="text-xs text-[#413632]/50 mt-0.5">{t.role}, {t.org}</p>
                                        </div>
                                    </div>
                                </SpotlightCard>
                            </motion.div>
                        ))}
                    </motion.div>
                </div>
            </section>

            {/* ═══════════════ FINAL CTA ═══════════════ */}
            <section className="py-20 px-6 md:px-8 bg-[#FFEAD5]/30 border-t border-[#CABDB2]/20">
                <div className="max-w-3xl mx-auto text-center">
                    <Reveal>
                        <div className="w-12 h-12 rounded-2xl bg-[#413632] flex items-center justify-center mx-auto mb-6 shadow-md">
                            <Image
                                src="/patrerekhaai-logo.png"
                                alt=""
                                width={22}
                                height={22}
                                className="h-[22px] w-[22px] object-contain"
                            />
                        </div>
                        <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-[#413632] mb-3">
                            Your documents already contain the answers.
                        </h2>
                        <p className="text-base text-[#413632]/60 mb-8 leading-relaxed max-w-xl mx-auto">
                            Make them accessible. Start using PatraRekha to unlock the institutional knowledge your organisation already holds.
                        </p>
                        <Link
                            href="/auth"
                            className="group inline-flex items-center gap-2 px-7 py-3.5 rounded-xl bg-[#413632] text-[#FFFBF0] font-semibold text-sm transition-all duration-200 hover:bg-[#413632]/85 hover:shadow-lg hover:shadow-[#413632]/20 hover:-translate-y-px active:scale-95"
                        >
                            Start with PatraRekha
                            <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-0.5" />
                        </Link>
                    </Reveal>
                </div>
            </section>

            {/* ═══════════════ FOOTER ═══════════════ */}
            <footer className="border-t border-[#CABDB2]/25 py-10 px-6 md:px-8">
                <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-5">
                    {/* Brand */}
                    <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-[#CA8A78] flex items-center justify-center">
                            <Image
                                src="/patrerekhaai-logo.png"
                                alt=""
                                width={14}
                                height={14}
                                className="h-[14px] w-[14px] object-contain"
                            />
                        </div>
                        <span className="font-bold text-sm text-[#413632]">
                            Patra<span className="text-[#CA8A78]">Rekha</span>
                            <span className="text-[#413632]/40 text-xs font-medium">AI</span>
                        </span>
                    </div>

                    {/* Nav links */}
                    <div className="flex items-center gap-5 text-xs text-[#413632]/45 font-medium">
                        <a href="#features" className="hover:text-[#413632] transition-colors">Features</a>
                        <a href="#how-it-works" className="hover:text-[#413632] transition-colors">How It Works</a>
                        <a href="#institutional" className="hover:text-[#413632] transition-colors">Why PatraRekha</a>
                        <Link href="/auth" className="hover:text-[#413632] transition-colors">Sign In</Link>
                    </div>

                    {/* Copyright */}
                    <p className="text-xs text-[#413632]/35">
                        © 2026 PatraRekha AI. All rights reserved.
                    </p>
                </div>
            </footer>

        </div>
    );
}
