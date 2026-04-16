"use client";

import { motion } from "framer-motion";
import { Check } from "lucide-react";

interface ChipProps {
  label: string;
  selected: boolean;
  onClick: () => void;
}

export function Chip({ label, selected, onClick }: ChipProps) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      whileTap={{ scale: 0.97 }}
      className={`
        inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-all focus-ring
        ${
          selected
            ? "border-indigo-400/60 bg-indigo-500/15 text-indigo-100 shadow-[0_0_12px_rgba(99,102,241,0.25)] hover:bg-indigo-500/20 active:bg-indigo-500/25"
            : "border-white/10 bg-white/[0.03] text-white/70 hover:border-white/20 hover:bg-white/[0.06] hover:text-white active:bg-white/[0.1]"
        }
      `}
    >
      {selected && <Check className="h-3.5 w-3.5" />}
      {label}
    </motion.button>
  );
}
