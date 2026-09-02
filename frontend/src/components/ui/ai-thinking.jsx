import React from "react";
import { motion } from "motion/react";

export default function AIThinking({ stage = "Searching your documents..." }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3 rounded-2xl border border-border bg-card px-4 py-3 shadow-sm"
    >
      <span className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map((item) => (
          <motion.span
            key={item}
            className="h-1.5 w-1.5 rounded-full bg-muted-foreground"
            animate={{ y: [0, -3, 0], opacity: [0.35, 1, 0.35] }}
            transition={{
              duration: 0.9,
              repeat: Infinity,
              delay: item * 0.12,
              ease: "easeInOut",
            }}
          />
        ))}
      </span>
      <motion.span
        key={stage}
        initial={{ opacity: 0, y: 3 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-sm text-muted-foreground"
      >
        {stage}
      </motion.span>
    </motion.div>
  );
}