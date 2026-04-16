"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { type ReactNode } from "react";

interface ToggleButtonProps extends HTMLMotionProps<"button"> {
  children: ReactNode;
  selected?: boolean;
}

export function ToggleButton({
  children,
  selected,
  className = "",
  disabled,
  ...props
}: ToggleButtonProps) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      disabled={disabled}
      className={`
        rounded-xl border px-4 py-3 text-sm font-medium capitalize
        transition-all focus-ring
        disabled:cursor-not-allowed disabled:opacity-50
        ${
          selected
            ? "border-indigo-400/60 bg-indigo-500/15 text-indigo-100 shadow-[0_0_16px_rgba(99,102,241,0.2)] hover:bg-indigo-500/20 active:bg-indigo-500/25"
            : "border-white/10 bg-white/[0.03] text-white/70 hover:border-white/20 hover:bg-white/[0.06] hover:text-white active:bg-white/[0.1]"
        }
        ${className}
      `}
      {...props}
    >
      {children}
    </motion.button>
  );
}
