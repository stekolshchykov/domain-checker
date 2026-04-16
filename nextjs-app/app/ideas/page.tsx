"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Check,
  X,
  RefreshCw,
  ArrowRight,
  Zap,
  Sparkles,
  Filter,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useSession } from "@/components/SessionProvider";
import { checkDomainAvailability } from "@/lib/actions";
import { Pill } from "@/components/ui/Pill";
import { Stepper } from "@/components/Stepper";
import type { DomainIdea } from "@/lib/types";

export default function IdeasPage() {
  const router = useRouter();
  const { brief, ideas, setResults, setGenerationExtras, hydrated } = useSession();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<"all" | "short" | "premium" | "tech" | "playful">("all");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hydrated) return;
    if (!ideas || ideas.length === 0) {
      router.replace("/");
      return;
    }
    setSelected(new Set(ideas.map((i) => i.domainName)));
  }, [ideas, router, hydrated]);

  const filteredIdeas = useMemo(() => {
    if (!ideas) return [];
    if (filter === "all") return ideas;
    if (filter === "short") return ideas.filter((i) => i.domainName.split(".")[0].length <= 6);
    return ideas.filter((i) =>
      i.tags.some((t) => t.toLowerCase().includes(filter))
    );
  }, [ideas, filter]);

  const toggleOne = (domain: string) => {
    const next = new Set(selected);
    if (next.has(domain)) next.delete(domain);
    else next.add(domain);
    setSelected(next);
  };

  const selectAllVisible = () => {
    setSelected(new Set(filteredIdeas.map((i) => i.domainName)));
  };

  const clearAll = () => {
    setSelected(new Set());
  };

  const handleCheck = async () => {
    if (!brief || !ideas) return;
    const domains = Array.from(selected);
    if (domains.length === 0) return;
    setChecking(true);
    try {
      const res = await checkDomainAvailability(domains, brief, ideas);
      setResults(res.results, res.checkedAt);
      if (res.colorPalette && res.logos) {
        setGenerationExtras(res.colorPalette, res.logos);
      }
      router.push("/results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Check failed");
      setChecking(false);
    }
  };

  if (!hydrated) return null;
  if (!ideas) return null;

  const visibleSelectedCount = filteredIdeas.filter((i) => selected.has(i.domainName)).length;

  return (
    <main className="flex flex-1 flex-col px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-6 rounded-2xl border border-white/5 bg-white/[0.02] p-4">
          <Stepper />
        </div>

        <div className="mb-2 text-sm text-white/60">
          Step 3 of 4 · Pick your favorites and check availability
        </div>

        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white sm:text-3xl">
              AI-generated names
            </h1>
            <p className="text-white/50">
              {selected.size} selected · {ideas.length} total ideas
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={selectAllVisible}>
              <Check className="mr-1.5 h-4 w-4" />
              Select all
            </Button>
            <Button variant="ghost" size="sm" onClick={clearAll}>
              <X className="mr-1.5 h-4 w-4" />
              Clear
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <div className="mr-2 flex items-center gap-1.5 text-sm text-white/60">
            <Filter className="h-4 w-4" />
            Filter:
          </div>
          {[
            { key: "all", label: "All" },
            { key: "short", label: "Short" },
            { key: "premium", label: "Premium" },
            { key: "tech", label: "Tech" },
            { key: "playful", label: "Playful" },
          ].map((f) => (
            <Pill
              key={f.key}
              selected={filter === f.key}
              onClick={() => setFilter(f.key as any)}
              className="px-3 py-1.5 text-xs"
            >
              {f.label}
            </Pill>
          ))}
        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-rose-200">
            {error}
          </div>
        )}

        {/* Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredIdeas.map((idea, idx) => {
            const isSelected = selected.has(idea.domainName);
            return (
              <motion.div
                key={idea.domainName}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.02 }}
                onClick={() => toggleOne(idea.domainName)}
                className={`
                  glass-card group cursor-pointer rounded-2xl p-5 transition-all
                  ${
                    isSelected
                      ? "border-indigo-400/40 bg-indigo-500/[0.08] shadow-[0_0_24px_rgba(99,102,241,0.15)]"
                      : "hover:border-white/15 hover:bg-white/[0.06]"
                  }
                `}
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <h3 className="break-all text-lg font-semibold text-white">
                    {idea.domainName}
                  </h3>
                  <div
                    className={`
                      flex h-6 w-6 shrink-0 items-center justify-center rounded-md border transition-colors
                      ${
                        isSelected
                          ? "border-indigo-400 bg-indigo-500 text-white"
                          : "border-white/20 bg-transparent"
                      }
                    `}
                  >
                    {isSelected && <Check className="h-4 w-4" />}
                  </div>
                </div>

                <p className="mb-3 text-sm leading-relaxed text-white/70">
                  {idea.meaning}
                </p>

                <div className="mb-3 flex flex-wrap gap-1.5">
                  {idea.tags.slice(0, 4).map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-white/60"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                <div className="flex items-center gap-1 text-xs text-white/40">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span className="capitalize">{idea.tone}</span>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Bottom bar */}
        <div className="fixed bottom-0 left-0 right-0 z-10 border-t border-white/10 bg-[#030712]/90 px-6 py-4 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl items-center justify-between">
            <div className="text-sm text-white/70">
              <span className="font-semibold text-white">{visibleSelectedCount}</span>{" "}
              domains selected for checking
            </div>
            <Button
              onClick={handleCheck}
              isLoading={checking}
              disabled={visibleSelectedCount === 0 || checking}
            >
              <Zap className="mr-2 h-4 w-4" />
              Check availability
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
