"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowLeft,
  RotateCw,
  Crown,
  TrendingUp,
  Minimize2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useSession } from "@/components/SessionProvider";
import { Stepper } from "@/components/Stepper";
import type { DomainResult } from "@/lib/types";

type SortMode = "available" | "price" | "brand" | "short";

export default function ResultsPage() {
  const router = useRouter();
  const { results, checkedAt, clearSession } = useSession();
  const [sort, setSort] = useState<SortMode>("available");

  useEffect(() => {
    if (!results || results.length === 0) {
      router.replace("/");
    }
  }, [results, router]);

  const sorted = useMemo(() => {
    if (!results) return [];
    const copy = [...results];
    switch (sort) {
      case "available":
        copy.sort((a, b) => {
          const order = { available: 0, premium: 1, unknown: 2, taken: 3 };
          return order[a.status] - order[b.status];
        });
        break;
      case "price":
        copy.sort((a, b) => {
          const price = (x: DomainResult) => {
            if (!x.price) return x.status === "available" ? 0 : Infinity;
            const n = parseFloat(x.price.replace(/[^0-9.]/g, ""));
            return isNaN(n) ? Infinity : n;
          };
          return price(a) - price(b);
        });
        break;
      case "short":
        copy.sort(
          (a, b) => a.domain.split(".")[0].length - b.domain.split(".")[0].length
        );
        break;
      case "brand":
        copy.sort((a, b) => {
          const score = (x: DomainResult) =>
            (x.tags?.includes("brandable") ? 2 : 0) +
            (x.tags?.includes("premium") ? 1 : 0) +
            (x.status === "available" ? 1 : 0);
          return score(b) - score(a);
        });
        break;
    }
    return copy;
  }, [results, sort]);

  const availableCount = useMemo(
    () => sorted.filter((r) => r.status === "available").length,
    [sorted]
  );

  if (!results) return null;

  return (
    <main className="flex flex-1 flex-col px-6 py-10">
      <div className="mx-auto w-full max-w-5xl">
        <div className="mb-6 rounded-2xl border border-white/5 bg-white/[0.02] p-4">
          <Stepper />
        </div>

        <div className="mb-2 text-sm text-white/60">
          Step 4 of 4 · Availability checked live via Namecheap
        </div>

        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white sm:text-3xl">
              Availability results
            </h1>
            <p className="text-white/50">
              {availableCount} available · Checked{" "}
              {checkedAt ? new Date(checkedAt).toLocaleTimeString() : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => router.push("/ideas")}>
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              Back to ideas
            </Button>
            <Button variant="secondary" size="sm" onClick={() => router.push("/")}>
              <RotateCw className="mr-1.5 h-4 w-4" />
              New search
            </Button>
          </div>
        </div>

        {/* Sort tabs */}
        <div className="mb-6 flex flex-wrap gap-2">
          {[
            { key: "available", label: "Available first", icon: CheckCircle2 },
            { key: "price", label: "Cheapest first", icon: TrendingUp },
            { key: "brand", label: "Best brand", icon: Crown },
            { key: "short", label: "Shortest first", icon: Minimize2 },
          ].map((opt) => (
            <button
              key={opt.key}
              onClick={() => setSort(opt.key as SortMode)}
              className={`
                inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all
                ${
                  sort === opt.key
                    ? "bg-white text-gray-950"
                    : "bg-white/5 text-white/70 hover:bg-white/10"
                }
              `}
            >
              <opt.icon className="h-4 w-4" />
              {opt.label}
            </button>
          ))}
        </div>

        {/* Top picks banner */}
        {availableCount > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-5 py-4"
          >
            <div className="flex items-center gap-2 text-emerald-300">
              <Crown className="h-5 w-5" />
              <span className="font-semibold">Great news</span>
            </div>
            <p className="mt-1 text-emerald-100/80">
              We found {availableCount} available domain{availableCount > 1 ? "s" : ""} that match your brief. Snap it up before someone else does.
            </p>
          </motion.div>
        )}

        {/* Results list */}
        <div className="space-y-3">
          {sorted.map((result, idx) => {
            const isAvailable = result.status === "available";
            const isPremium = result.status === "premium";
            const isTaken = result.status === "taken";

            return (
              <motion.div
                key={result.domain}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                className={`
                  flex flex-col gap-3 rounded-2xl border px-5 py-4 transition-colors sm:flex-row sm:items-center sm:justify-between
                  ${
                    isAvailable
                      ? "border-emerald-500/20 bg-emerald-500/[0.06]"
                      : isPremium
                      ? "border-amber-500/20 bg-amber-500/[0.05]"
                      : "border-white/10 bg-white/[0.03]"
                  }
                `}
              >
                <div className="flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-white">
                      {result.domain}
                    </h3>
                    {isAvailable && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-medium text-emerald-300">
                        <CheckCircle2 className="h-3 w-3" />
                        Available
                      </span>
                    )}
                    {isPremium && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-300">
                        <Crown className="h-3 w-3" />
                        Premium
                      </span>
                    )}
                    {isTaken && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/20 px-2 py-0.5 text-xs font-medium text-rose-300">
                        <XCircle className="h-3 w-3" />
                        Taken
                      </span>
                    )}
                    {!isAvailable && !isPremium && !isTaken && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2 py-0.5 text-xs font-medium text-white/60">
                        <AlertCircle className="h-3 w-3" />
                        Unknown
                      </span>
                    )}
                  </div>
                  {result.meaning && (
                    <p className="text-sm text-white/60">{result.meaning}</p>
                  )}
                  {result.tags && result.tags.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {result.tags.slice(0, 5).map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-white/50"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-4 sm:text-right">
                  {result.price ? (
                    <div>
                      <div className="text-lg font-semibold text-white">
                        {result.price}
                      </div>
                      <div className="text-xs text-white/40">
                        {result.currency || ""}
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-white/40">
                      {isAvailable ? "Standard price" : "—"}
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
