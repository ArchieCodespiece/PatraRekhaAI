import React from "react";
import { motion } from "motion/react";

export default function AnimatedButton({
  children,
  className = "",
  disabled,
  type = "button",
  ...props
}) {
  return (
    <motion.button
      type={type}
      disabled={disabled}
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      transition={{ duration: 0.12 }}
      className={className}
      {...props}
    >
      {children}
    </motion.button>
  );
}
