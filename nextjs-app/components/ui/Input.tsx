"use client";

import { type InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = "", ...props }, ref) => {
    return (
      <div className={`flex flex-col gap-1.5 ${className}`}>
        {label && (
          <label className="text-sm font-medium text-white/80">{label}</label>
        )}
        <input
          ref={ref}
          className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-white placeholder:text-white/30 transition-colors hover:border-white/20 focus:border-white/30 focus:bg-white/[0.05] focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
          {...props}
        />
        {error && <span className="text-sm text-rose-400">{error}</span>}
      </div>
    );
  }
);
Input.displayName = "Input";
