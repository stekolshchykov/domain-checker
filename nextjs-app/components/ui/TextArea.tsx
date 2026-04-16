"use client";

import { type TextareaHTMLAttributes, forwardRef } from "react";

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ label, error, className = "", ...props }, ref) => {
    return (
      <div className={`flex flex-col gap-1.5 ${className}`}>
        {label && (
          <label className="text-sm font-medium text-white/80">{label}</label>
        )}
        <textarea
          ref={ref}
          className="w-full min-h-[120px] resize-y rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-white placeholder:text-white/30 transition-colors hover:border-white/20 focus:border-white/30 focus:bg-white/[0.05] focus:outline-none focus:ring-2 focus:ring-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-white/[0.02] disabled:border-white/5"
          {...props}
        />
        {error && <span className="text-sm text-rose-400">{error}</span>}
      </div>
    );
  }
);
TextArea.displayName = "TextArea";
