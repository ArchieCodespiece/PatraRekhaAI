"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { FileText, Check, Loader2, Send, Brain } from "lucide-react";

/* ─── Scene timings (ms) ─────────────────────────────────────────────────── */

const SCENE_TIMINGS = [
    2000,  // Upload
    4200,  // Processing
    1200,  // Ready
    2800,  // Question
    2000,  // Thinking
    3800,  // Answer
];

/* ─── Upload Scene ────────────────────────────────────────────────────────── */

function UploadScene() {
    const [progress, setProgress] = useState(0);
    const [showCheck, setShowCheck] = useState(false);

    useEffect(() => {
        const start = Date.now();
        const duration = 1600;

        const tick = () => {
            const elapsed = Date.now() - start;
            const p = Math.min(100, (elapsed / duration) * 100);
            setProgress(p);

            if (p < 100) {
                requestAnimationFrame(tick);
            } else {
                setTimeout(() => setShowCheck(true), 150);
            }
        };

        const timer = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(timer);
    }, []);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col items-center gap-4"
        >
            {/* Document card */}
            <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15, duration: 0.4 }}
                className="w-full max-w-[220px] bg-[#FFFBF0] border border-[#CABDB2]/50 rounded-xl p-4 shadow-sm shadow-[#413632]/5"
            >
                <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-lg bg-[#CA8A78]/10 border border-[#CA8A78]/20 flex items-center justify-center">
                        <FileText size={18} className="text-[#CA8A78]" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-[#413632] truncate">circular.pdf</p>
                        <p className="text-[10px] text-[#413632]/50">2.4 MB</p>
                    </div>
                </div>

                {/* Progress bar */}
                <div className="h-1.5 bg-[#CABDB2]/30 rounded-full overflow-hidden">
                    <motion.div
                        className="h-full bg-[#CA8A78] rounded-full"
                        initial={{ width: "0%" }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.05, ease: "linear" }}
                    />
                </div>

                <div className="flex items-center justify-between mt-2">
                    <span className="text-[10px] text-[#413632]/50">
                        {showCheck ? "Complete" : "Uploading..."}
                    </span>
                    <span className="text-[10px] font-medium text-[#413632]/60">
                        {Math.round(progress)}%
                    </span>
                </div>
            </motion.div>

            {/* Checkmark */}
            <AnimatePresence>
                {showCheck && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ type: "spring", stiffness: 260, damping: 18 }}
                        className="w-8 h-8 rounded-full bg-[#CA8A78]/15 border border-[#CA8A78]/30 flex items-center justify-center"
                    >
                        <Check size={14} className="text-[#CA8A78]" />
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

/* ─── Processing Scene ────────────────────────────────────────────────────── */

const PROCESSING_STAGES = [
    { label: "Uploaded", done: true },
    { label: "Extracted", done: true },
    { label: "Summarising", done: true },
    { label: "Deadlines", done: true },
    { label: "Embedded", done: true },
    { label: "Indexed", done: true },
];

function ProcessingScene() {
    const [completedCount, setCompletedCount] = useState(0);

    useEffect(() => {
        let count = 0;
        const interval = setInterval(() => {
            count += 1;
            setCompletedCount(count);
            if (count >= PROCESSING_STAGES.length) {
                clearInterval(interval);
            }
        }, 550);

        return () => clearInterval(interval);
    }, []);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="w-full"
        >
            {/* Document name header */}
            <div className="flex items-center gap-2 mb-4">
                <div className="w-7 h-7 rounded-md bg-[#CA8A78]/10 border border-[#CA8A78]/20 flex items-center justify-center">
                    <FileText size={12} className="text-[#CA8A78]" />
                </div>
                <span className="text-xs font-semibold text-[#413632]">circular.pdf</span>
            </div>

            {/* Pipeline stages */}
            <div className="space-y-2">
                {PROCESSING_STAGES.map((stage, i) => {
                    const isCompleted = i < completedCount;
                    const isCurrent = i === completedCount;

                    return (
                        <motion.div
                            key={stage.label}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.08, duration: 0.3 }}
                            className="flex items-center gap-2.5"
                        >
                            {/* Status indicator */}
                            <motion.div
                                initial={false}
                                animate={{
                                    scale: isCurrent ? [1, 1.2, 1] : 1,
                                    opacity: isCompleted || isCurrent ? 1 : 0.4,
                                }}
                                transition={{
                                    scale: { duration: 0.8, repeat: isCurrent ? Infinity : 0 },
                                }}
                                className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                                    isCompleted
                                        ? "bg-[#CA8A78]/15 border border-[#CA8A78]/40"
                                        : isCurrent
                                        ? "bg-[#FFEAD5] border border-[#CA8A78]/60"
                                        : "bg-[#CABDB2]/20 border border-[#CABDB2]/30"
                                }`}
                            >
                                {isCompleted ? (
                                    <motion.span
                                        initial={{ scale: 0 }}
                                        animate={{ scale: 1 }}
                                        transition={{ type: "spring", stiffness: 260, damping: 18 }}
                                    >
                                        <Check size={10} className="text-[#CA8A78]" />
                                    </motion.span>
                                ) : isCurrent ? (
                                    <motion.div
                                        animate={{ opacity: [0.4, 1, 0.4] }}
                                        transition={{ duration: 1, repeat: Infinity }}
                                        className="w-1.5 h-1.5 rounded-full bg-[#CA8A78]"
                                    />
                                ) : (
                                    <div className="w-1.5 h-1.5 rounded-full bg-[#CABDB2]/50" />
                                )}
                            </motion.div>

                            {/* Label */}
                            <span className={`text-[11px] font-medium ${
                                isCompleted
                                    ? "text-[#413632]"
                                    : isCurrent
                                    ? "text-[#413632]/80"
                                    : "text-[#413632]/35"
                            }`}>
                                {stage.label}
                            </span>
                        </motion.div>
                    );
                })}
            </div>
        </motion.div>
    );
}

/* ─── Ready Scene ─────────────────────────────────────────────────────────── */

function ReadyScene() {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col items-center gap-3 text-center"
        >
            {/* Success checkmark */}
            <motion.div
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ type: "spring", stiffness: 200, damping: 15, delay: 0.1 }}
                className="w-12 h-12 rounded-full bg-[#CA8A78]/15 border-2 border-[#CA8A78]/40 flex items-center justify-center"
            >
                <Check size={20} className="text-[#CA8A78]" />
            </motion.div>

            <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25, duration: 0.35 }}
            >
                <p className="text-sm font-semibold text-[#413632]">Document processed</p>
                <p className="text-[10px] text-[#413632]/50 mt-1">circular.pdf</p>
                <p className="text-[11px] text-[#CA8A78] font-medium mt-2">Ready to ask questions</p>
            </motion.div>
        </motion.div>
    );
}

/* ─── Question Scene ──────────────────────────────────────────────────────── */

function QuestionScene() {
    const fullText = "What is the deadline for submission?";
    const [displayText, setDisplayText] = useState("");
    const [showCursor, setShowCursor] = useState(true);

    useEffect(() => {
        let i = 0;
        const interval = setInterval(() => {
            if (i <= fullText.length) {
                setDisplayText(fullText.slice(0, i));
                i += 1;
            } else {
                clearInterval(interval);
                setTimeout(() => setShowCursor(false), 600);
            }
        }, 65);

        return () => clearInterval(interval);
    }, []);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="w-full"
        >
            {/* User chat bubble */}
            <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ delay: 0.1, duration: 0.35 }}
                className="ml-auto max-w-[85%]"
            >
                <div className="bg-[#413632] text-[#FFFBF0] rounded-2xl rounded-tr-sm px-4 py-3 shadow-md shadow-[#413632]/15">
                    <p className="text-xs leading-relaxed">
                        {displayText}
                        {showCursor && (
                            <motion.span
                                animate={{ opacity: [1, 0] }}
                                transition={{ duration: 0.5, repeat: Infinity }}
                                className="inline-block w-px h-3 bg-[#FFFBF0]/70 ml-0.5 align-middle"
                            />
                        )}
                    </p>
                </div>
                <p className="text-[9px] text-[#413632]/40 mt-1.5 mr-1">You</p>
            </motion.div>
        </motion.div>
    );
}

/* ─── Thinking Scene ──────────────────────────────────────────────────────── */

function ThinkingScene() {
    const [steps, setSteps] = useState([]);

    useEffect(() => {
        const delays = [0, 700, 1300];
        const labels = [
            "Searching document...",
            "Relevant section found",
            "Deadline identified",
        ];

        const timers = delays.map((delay, i) =>
            setTimeout(() => {
                setSteps((prev) => [...prev, labels[i]]);
            }, delay)
        );

        return () => timers.forEach(clearTimeout);
    }, []);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="w-full"
        >
            {/* AI header */}
            <div className="flex items-center gap-2 mb-3">
                <div className="w-6 h-6 rounded-md bg-[#413632] flex items-center justify-center">
                    <Brain size={12} className="text-[#FFFBF0]" />
                </div>
                <span className="text-[11px] font-semibold text-[#413632]">PatraRekha AI</span>
            </div>

            {/* Thinking bubble */}
            <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.3 }}
                className="bg-white/70 border border-[#CABDB2]/40 rounded-2xl rounded-tl-sm px-4 py-3 backdrop-blur-sm shadow-sm shadow-[#413632]/5"
            >
                <div className="space-y-2">
                    {steps.map((step, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ duration: 0.25 }}
                            className="flex items-center gap-2"
                        >
                            <div className="w-4 h-4 rounded-full bg-[#CA8A78]/15 flex items-center justify-center">
                                <Check size={9} className="text-[#CA8A78]" />
                            </div>
                            <span className="text-[11px] text-[#413632]/70">{step}</span>
                        </motion.div>
                    ))}

                    {/* Loading indicator */}
                    {steps.length < 3 && (
                        <motion.div
                            animate={{ opacity: [0.4, 1, 0.4] }}
                            transition={{ duration: 1, repeat: Infinity }}
                            className="flex items-center gap-2"
                        >
                            <Loader2 size={12} className="text-[#CA8A78] animate-spin" />
                            <span className="text-[11px] text-[#413632]/50">Analysing...</span>
                        </motion.div>
                    )}
                </div>
            </motion.div>
        </motion.div>
    );
}

/* ─── Answer Scene ────────────────────────────────────────────────────────── */

function AnswerScene() {
    const fullText = "The submission deadline is";
    const dateText = "15 September 2026";
    const [displayPart1, setDisplayPart1] = useState("");
    const [showDate, setShowDate] = useState(false);

    useEffect(() => {
        let i = 0;
        const interval = setInterval(() => {
            if (i <= fullText.length) {
                setDisplayPart1(fullText.slice(0, i));
                i += 1;
            } else {
                clearInterval(interval);
                setTimeout(() => setShowDate(true), 200);
            }
        }, 50);

        return () => clearInterval(interval);
    }, []);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="w-full"
        >
            {/* AI header */}
            <div className="flex items-center gap-2 mb-3">
                <div className="w-6 h-6 rounded-md bg-[#413632] flex items-center justify-center">
                    <Brain size={12} className="text-[#FFFBF0]" />
                </div>
                <span className="text-[11px] font-semibold text-[#413632]">PatraRekha AI</span>
            </div>

            {/* Answer bubble */}
            <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1, duration: 0.3 }}
                className="bg-white/70 border border-[#CABDB2]/40 rounded-2xl rounded-tl-sm px-4 py-3 backdrop-blur-sm shadow-sm shadow-[#413632]/5"
            >
                <p className="text-xs leading-relaxed text-[#413632]">
                    {displayPart1}
                    <AnimatePresence>
                        {showDate && (
                            <motion.span
                                initial={{ opacity: 0, y: 4 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.3, ease: "easeOut" }}
                                className="inline font-bold text-[#CA8A78]"
                            >
                                {" "}{dateText}
                            </motion.span>
                        )}
                    </AnimatePresence>
                </p>
            </motion.div>
        </motion.div>
    );
}

/* ─── Scene Indicator ─────────────────────────────────────────────────────── */

function SceneIndicator({ total, current }) {
    return (
        <div className="flex items-center justify-center gap-1.5 mt-5">
            {Array.from({ length: total }).map((_, i) => (
                <motion.div
                    key={i}
                    animate={{
                        width: i === current ? 16 : 6,
                        backgroundColor: i === current ? "#CA8A78" : "#CABDB2",
                        opacity: i === current ? 1 : 0.5,
                    }}
                    transition={{ duration: 0.3, ease: "easeOut" }}
                    className="h-1.5 rounded-full"
                />
            ))}
        </div>
    );
}

/* ─── Main Demo Component ─────────────────────────────────────────────────── */

export default function PatraRekhaDemo() {
    const [scene, setScene] = useState(0);
    const isPausedRef = useRef(false);
    const timerRef = useRef(null);

    const scenes = [
        UploadScene,
        ProcessingScene,
        ReadyScene,
        QuestionScene,
        ThinkingScene,
        AnswerScene,
    ];

    const CurrentScene = scenes[scene];

    const startTimer = useCallback(() => {
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
            if (!isPausedRef.current) {
                setScene((prev) => (prev + 1) % scenes.length);
            }
        }, SCENE_TIMINGS[scene]);
    }, [scene, scenes.length]);

    useEffect(() => {
        if (!isPausedRef.current) {
            startTimer();
        }
        return () => clearTimeout(timerRef.current);
    }, [scene, startTimer]);

    const handleMouseEnter = () => {
        isPausedRef.current = true;
        clearTimeout(timerRef.current);
    };

    const handleMouseLeave = () => {
        isPausedRef.current = false;
        startTimer();
    };

    return (
        <div
            className="w-full max-w-sm mx-auto lg:mx-0"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <div className="rounded-2xl border border-[#CABDB2]/50 bg-white/70 backdrop-blur-sm shadow-xl shadow-[#413632]/8 overflow-hidden">
                {/* Title bar */}
                <div className="flex items-center gap-1.5 px-4 py-3 border-b border-[#CABDB2]/30 bg-[#FFEAD5]/40">
                    <div className="w-2.5 h-2.5 rounded-full bg-[#CA8A78]/70" />
                    <div className="w-2.5 h-2.5 rounded-full bg-[#CABDB2]/60" />
                    <div className="w-2.5 h-2.5 rounded-full bg-[#CABDB2]/40" />
                    <span className="ml-2 text-[10px] font-mono text-[#413632]/40 tracking-wide">
                        PatraRekha Demo
                    </span>
                </div>

                {/* Scene content */}
                <div className="p-5 min-h-[240px] flex items-center justify-center">
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={scene}
                            className="w-full"
                        >
                            <CurrentScene />
                        </motion.div>
                    </AnimatePresence>
                </div>

                {/* Scene indicator */}
                <div className="px-4 pb-4">
                    <SceneIndicator total={scenes.length} current={scene} />
                </div>
            </div>
        </div>
    );
}
