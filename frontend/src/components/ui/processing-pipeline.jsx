import React from "react";
import { motion } from "motion/react";

export const PIPELINE_STAGES = [
  { key: "upload", label: "Upload" },
  { key: "extract", label: "Extract" },
  { key: "ner", label: "NER" },
  { key: "summarize", label: "Summarize" },
  { key: "embed", label: "Embed" },
  { key: "index", label: "Indexed" },
];

export default function ProcessingPipeline({
  active = "upload",
  steps = PIPELINE_STAGES,
  className = "",
  compact = true,
}) {
  const activeIndex = Math.max(0, steps.findIndex((step) => step.key === active));

  if (compact) {
    return (
      <div
        className={`flex items-center gap-1 sm:gap-1.5 py-1 px-2.5 rounded-lg border border-border bg-muted text-[11px] font-medium select-none ${className}`}
        title={`Processing: currently ${steps[activeIndex]?.label || active}`}
      >
        {steps.map((step, index) => {
          const isDone = index < activeIndex;
          const isCurrent = index === activeIndex;

          return (
            <React.Fragment key={step.key}>
              <div
                className={`flex items-center gap-1 transition-colors ${
                  isDone
                    ? "text-primary font-semibold"
                    : isCurrent
                    ? "text-foreground font-bold"
                    : "text-muted-foreground opacity-60"
                }`}
              >
                {isDone ? (
                  <span className="text-[10px] text-primary font-bold">✓</span>
                ) : isCurrent ? (
                  <motion.span
                    animate={{ scale: [1, 1.3, 1], opacity: [0.6, 1, 0.6] }}
                    transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
                    className="inline-block h-1.5 w-1.5 rounded-full bg-primary"
                  />
                ) : (
                  <span className="inline-block h-1 w-1 rounded-full bg-muted-foreground" />
                )}
                <span className="hidden md:inline text-[10.5px] leading-none">
                  {step.label}
                </span>
              </div>

              {index < steps.length - 1 && (
                <span
                  className={`text-[9px] ${
                    index < activeIndex ? "text-primary/70" : "text-muted-foreground"
                  }`}
                >
                  →
                </span>
              )}
            </React.Fragment>
          );
        })}
      </div>
    );
  }

  // Full-size vertical version
  return (
    <div className={`rounded-2xl border border-border bg-card p-4 ${className}`}>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold text-card-foreground">Processing document</p>
          <p className="text-[11px] text-muted-foreground">Preparing it for PatraRekha search</p>
        </div>
        <motion.span
          key={active}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground"
        >
          {Math.round(((activeIndex + 1) / steps.length) * 100)}%
        </motion.span>
      </div>

      <div className="space-y-1.5">
        {steps.map((step, index) => {
          const done = index < activeIndex;
          const current = index === activeIndex;

          return (
            <div
              key={step.key}
              className={`flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-xs ${
                current ? "bg-muted font-medium text-foreground" : done ? "text-primary" : "text-muted-foreground"
              }`}
            >
              <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full border border-border text-[10px]">
                {done ? "✓" : current ? (
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
                    className="block leading-none"
                  >
                    ◌
                  </motion.span>
                ) : (
                  index + 1
                )}
              </span>
              <span>{step.label}</span>
              {current && (
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="ml-auto text-[10px] text-primary"
                >
                  processing...
                </motion.span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}