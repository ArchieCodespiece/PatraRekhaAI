import React from "react";
import { motion } from "motion/react";

const tones = {
  neutral: "bg-muted text-muted-foreground border-border",
  success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
  danger: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30",
  info: "bg-primary/15 text-primary border-primary/30",
};

export default function StatusBadge({
  children,
  tone = "neutral",
  dot = true,
  className = "",
}) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${tones[tone] || tones.neutral} ${className}`}
    >
      {dot && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full rounded-full bg-current opacity-30" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      )}
      {children}
    </motion.span>
  );
}