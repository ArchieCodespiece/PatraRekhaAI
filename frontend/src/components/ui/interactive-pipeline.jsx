"use client";

import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { pipelineStep, staggerContainerSlow } from "@/components/motionVariants";
import StagePopover from "./stage-popover";

const STATUS_COPY = {
    completed: "Completed",
    processing: "In progress",
    pending: "Pending",
    failed: "Failed",
};

function StageNode({ stage, index, isLast, isPopoverOpen, onClick }) {
    const nodeRef = useRef(null);

    const handleClick = () => {
        if (!nodeRef.current) {
            return;
        }
        const rect = nodeRef.current.getBoundingClientRect();
        onClick(stage, rect);
    };

    const isCompleted = stage.status === "completed";
    const isProcessing = stage.status === "processing";
    const isFailed = stage.status === "failed";
    const isPending = stage.status === "pending";

    return (
        <motion.div
            variants={pipelineStep}
            className="flex items-center"
        >
            <button
                ref={nodeRef}
                type="button"
                onClick={handleClick}
                aria-label={`${stage.label}: ${STATUS_COPY[stage.status]}`}
                aria-expanded={isPopoverOpen}
                className={`flex flex-col items-center gap-1.5 rounded-xl px-2 py-2 transition-colors ${
                    isPending
                        ? "cursor-default"
                        : "cursor-pointer hover:bg-primary/10"
                }`}
            >
                <motion.span
                    whileHover={isPending ? {} : { scale: 1.05 }}
                    className={`flex h-8 w-8 items-center justify-center rounded-full border-2 shrink-0 ${
                        isCompleted
                            ? "border-primary bg-primary/15"
                            : isProcessing
                            ? "border-primary bg-primary/20"
                            : isFailed
                            ? "border-red-500 bg-red-500/15"
                            : "border-border bg-card"
                    }`}
                >
                    {isCompleted ? (
                        <motion.span
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{
                                type: "spring",
                                stiffness: 260,
                                damping: 20,
                            }}
                            className="text-primary"
                        >
                            ✓
                        </motion.span>
                    ) : isProcessing ? (
                        <motion.span
                            animate={{
                                scale: [1, 1.25, 1],
                                opacity: [0.5, 1, 0.5],
                            }}
                            transition={{
                                duration: 1.2,
                                repeat: Infinity,
                                ease: "easeInOut",
                            }}
                            className="block h-2.5 w-2.5 rounded-full bg-primary"
                        />
                    ) : isFailed ? (
                        <motion.span
                            animate={{
                                scale: [1, 1.15, 1],
                                opacity: [0.6, 1, 0.6],
                            }}
                            transition={{
                                duration: 1.4,
                                repeat: Infinity,
                                ease: "easeInOut",
                            }}
                            className="block h-2.5 w-2.5 rounded-full bg-red-500"
                        />
                    ) : (
                        <span className="block h-2 w-2 rounded-full bg-muted-foreground/60" />
                    )}
                </motion.span>

                <span
                    className={`text-[10px] font-semibold leading-none text-center whitespace-nowrap ${
                        isCompleted || isProcessing
                            ? "text-foreground"
                            : isFailed
                            ? "text-red-600 dark:text-red-400"
                            : "text-muted-foreground"
                    }`}
                >
                    {stage.label}
                </span>
            </button>

            {!isLast && (
                <Connector
                    fromStatus={stage.status}
                    toStatus={stage.status}
                />
            )}
        </motion.div>
    );
}

function Connector({ fromStatus }) {
    const isCompleted = fromStatus === "completed";
    const isProcessing = fromStatus === "processing";

    if (isCompleted) {
        return (
            <div className="mx-1 md:mx-2 h-px w-6 md:w-10 bg-primary/60 rounded-full" />
        );
    }

    if (isProcessing) {
        return (
            <motion.div
                animate={{ width: ["0%", "100%"] }}
                transition={{
                    duration: 0.6,
                    ease: [0.22, 1, 0.36, 1],
                    repeat: Infinity,
                    repeatType: "reverse",
                }}
                className="mx-1 md:mx-2 h-px w-6 md:w-10 bg-primary/50 rounded-full"
            />
        );
    }

    return (
        <div className="mx-1 md:mx-2 h-px w-6 md:w-10 bg-border rounded-full" />
    );
}

export default function InteractivePipeline({
    fileName,
    stages,
    className = "",
}) {
    const [activeStage, setActiveStage] = useState(null);
    const [anchorRect, setAnchorRect] = useState(null);

    const handleStageClick = useCallback((stage, rect) => {
        setActiveStage(stage);
        setAnchorRect(rect);
    }, []);

    const handleClosePopover = useCallback(() => {
        setActiveStage(null);
        setAnchorRect(null);
    }, []);

    return (
        <div className={`w-full max-w-sm mx-auto lg:mx-0 ${className}`}>
            <div className="rounded-2xl border border-border bg-card/80 backdrop-blur-sm shadow-xl shadow-foreground/5 overflow-hidden">
                <div className="flex items-center gap-1.5 px-4 py-3 border-b border-border bg-muted/60">
                    <div className="w-2.5 h-2.5 rounded-full bg-primary/70" />
                    <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/60" />
                    <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/40" />
                    <span className="ml-2 text-[10px] font-mono text-muted-foreground tracking-wide">
                        {fileName || "PatraRekha Pipeline"}
                    </span>
                </div>

                <div className="p-4">
                    <motion.div
                        variants={staggerContainerSlow}
                        initial="hidden"
                        animate="visible"
                        className="flex items-center overflow-x-auto pb-2 -mx-1 px-1"
                        style={{ scrollbarWidth: "none" }}
                    >
                        {stages.map((stage, index) => (
                            <StageNode
                                key={stage.key}
                                stage={stage}
                                index={index}
                                isLast={index === stages.length - 1}
                                isPopoverOpen={activeStage?.key === stage.key}
                                onClick={handleStageClick}
                            />
                        ))}
                    </motion.div>
                </div>
            </div>

            <AnimatePresence>
                {activeStage && anchorRect && (
                    <StagePopover
                        stage={activeStage}
                        anchorRect={anchorRect}
                        onClose={handleClosePopover}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}