import React from "react";
import { motion } from "motion/react";
import StatusBadge from "./StatusBadge";
import ProcessingPipeline from "./processing-pipeline";

const statusTone = {
  indexed: "success",
  processed: "success",
  processing: "warning",
  uploading: "info",
  failed: "danger",
};

const statusLabel = {
  indexed: "Processed",
  processed: "Processed",
  processing: "Processing",
  uploading: "Uploading",
  failed: "Failed",
};

export default function DocumentCard({
  name = "Untitled document",
  type = "PDF",
  meta = "",
  status = "indexed",
  processingStage = "upload",
  icon,
  onClick,
  onAction,
  className = "",
}) {
  const isProcessing = status === "processing" || status === "uploading";
  const tone = statusTone[status] || "neutral";
  const label = statusLabel[status] || status;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
      className={`group relative overflow-hidden rounded-2xl border border-border bg-card p-4 shadow-sm transition-all hover:border-primary/60 hover:shadow-md ${className}`}
    >
      <button
        type="button"
        onClick={onClick}
        className="block w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 rounded-xl"
      >
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-border bg-muted text-primary">
            {icon || <span className="text-xs font-bold">{type}</span>}
          </div>

          <div className="min-w-0 flex-1 pr-8">
            <h3 className="truncate text-sm font-semibold text-card-foreground">{name}</h3>
            {meta && <p className="mt-1 truncate text-xs text-muted-foreground">{meta}</p>}
          </div>
        </div>

        <div className="mt-3.5 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-3">
          {isProcessing ? (
            <ProcessingPipeline active={processingStage} compact={true} />
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                ✓
              </span>
              <span>Processed</span>
            </div>
          )}

          <span className="text-xs text-muted-foreground transition-transform group-hover:translate-x-0.5">
            Open →
          </span>
        </div>
      </button>

      {onAction && (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onAction(event);
          }}
          aria-label={`Actions for ${name}`}
          className="absolute right-3 top-3 grid h-7 w-7 place-items-center rounded-lg text-muted-foreground opacity-0 transition hover:bg-muted hover:text-foreground group-hover:opacity-100 focus:opacity-100"
        >
          ···
        </button>
      )}
    </motion.div>
  );
}