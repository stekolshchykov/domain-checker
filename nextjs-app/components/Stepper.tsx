"use client";

import { motion } from "framer-motion";
import { Edit3, Sliders, Wand2, SearchCheck } from "lucide-react";
import { usePathname } from "next/navigation";

const STEPS = [
  { id: "describe", label: "Describe", path: "/", icon: Edit3 },
  { id: "refine", label: "Refine", path: "/brief", icon: Sliders },
  { id: "generate", label: "Generate", path: "/generating", icon: Wand2 },
  { id: "check", label: "Check", path: "/results", icon: SearchCheck },
];

export function Stepper() {
  const pathname = usePathname();

  let activeIndex = STEPS.findIndex((s) => s.path === pathname);
  // generating and ideas are both part of "Generate"
  if (pathname === "/ideas") activeIndex = 2;
  if (activeIndex === -1) activeIndex = 0;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between">
        {STEPS.map((step, idx) => {
          const isActive = idx === activeIndex;
          const isCompleted = idx < activeIndex;
          const Icon = step.icon;

          return (
            <div key={step.id} className="relative flex flex-1 flex-col items-center">
              {/* Connector line */}
              {idx !== 0 && (
                <div
                  className={`absolute left-0 top-5 hidden h-0.5 w-1/2 -translate-x-1/2 sm:block ${
                    isCompleted ? "bg-indigo-500" : "bg-white/10"
                  }`}
                />
              )}
              {idx !== STEPS.length - 1 && (
                <div
                  className={`absolute left-full top-5 hidden h-0.5 w-1/2 -translate-x-1/2 sm:block ${
                    isCompleted ? "bg-indigo-500" : "bg-white/10"
                  }`}
                />
              )}

              <motion.div
                animate={{
                  scale: isActive ? 1.05 : 1,
                  backgroundColor: isActive
                    ? "rgba(99,102,241,1)"
                    : isCompleted
                    ? "rgba(99,102,241,0.9)"
                    : "rgba(255,255,255,0.05)",
                }}
                className={`z-10 flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold transition-colors ${
                  isActive
                    ? "text-white shadow-[0_0_16px_rgba(99,102,241,0.45)]"
                    : isCompleted
                    ? "text-white"
                    : "text-white/40"
                }`}
              >
                <Icon className="h-4 w-4" />
              </motion.div>

              <span
                className={`mt-2 hidden text-xs font-medium sm:block ${
                  isActive ? "text-white" : isCompleted ? "text-indigo-200" : "text-white/40"
                }`}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
