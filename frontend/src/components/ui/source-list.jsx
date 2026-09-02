import React from "react";
import { motion } from "motion/react";
import ExpandableSource from "./expandable-source";

export default function SourceList({ sources = [], className = "" }) {
  if (!sources.length) return null;

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center gap-2 px-1">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Sources
        </span>
        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          {sources.length}
        </span>
      </div>

      <div className="space-y-2">
        {sources.map((source, index) => (
          <motion.div
            key={source.id || `${source.title}-${index}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.04 }}
          >
            <ExpandableSource
              title={source.title || source.name || "Document source"}
              meta={source.meta || source.page || ""}
              excerpt={source.excerpt || source.content || "Relevant passage available in the source document."}
              icon={<span className="text-xs">↗</span>}
            />
          </motion.div>
        ))}
      </div>
    </div>
  );
}