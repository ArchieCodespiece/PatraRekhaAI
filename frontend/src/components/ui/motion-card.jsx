import React from "react";
import { motion } from "motion/react";

export default function MotionCard({
  children,
  className = "",
  delay = 0,
  hover = true,
  ...props
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay, ease: [0.22, 1, 0.36, 1] }}
      whileHover={
        hover
          ? { y: -2, transition: { duration: 0.18, ease: "easeOut" } }
          : undefined
      }
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
}
