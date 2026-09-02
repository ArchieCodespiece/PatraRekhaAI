import React, { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

export default function ExpandableSource({
  title,
  meta,
  excerpt,
  icon,
  className = "",
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`overflow-hidden rounded-xl border border-border bg-card ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/70"
        aria-expanded={open}
      >
        {icon && <span className="shrink-0">{icon}</span>}
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-card-foreground">
            {title}
          </span>
          {meta && (
            <span className="mt-0.5 block truncate text-xs text-muted-foreground">
              {meta}
            </span>
          )}
        </span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.18 }}
          className="text-muted-foreground/70"
          aria-hidden="true"
        >
          ↓
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <div className="border-t border-border bg-muted/60 px-4 py-3 text-sm leading-6 text-card-foreground/80">
              {excerpt}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}