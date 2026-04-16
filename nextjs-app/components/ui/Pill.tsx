"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { type ReactNode } from "react";

interface PillProps extends HTMLMotionProps<"button"> {
  children: ReactNode;
  selected?: boolean;
  icon?: ReactNode;
}

export function Pill({
  children,
  selected,
  icon,
  className = "",
  disabled,
  ...props
}: PillProps) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      disabled={disabled}
      className={`
        inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium
        transition-all focus-ring
        active:scale-[0.97]
        disabled:cursor-not-allowed disabled:opacity-50
        ${
          selected
            ? "bg-white text-gray-950 shadow-[0_0_16px_rgba(255,255,255,0.15)] hover:bg-gray-100 active:bg-gray-200"
            : "bg-white/5 text-white/70 hover:bg-white/10 hover:text-white active:bg-white/[0.14]"
        }
        ${className}
      `}
      {...props}
    >
      {icon}
      {children}
    </motion.button>
  );
}
