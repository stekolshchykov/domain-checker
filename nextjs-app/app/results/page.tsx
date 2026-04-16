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
  ExternalLink,
  Palette,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useSession } from "@/components/SessionProvider";
import { Pill } from "@/components/ui/Pill";
import { Stepper } from "@/components/Stepper";
import type { DomainResult, PriceOption } from "@/lib/types";

type SortMode = "available" | "price" | "brand" | "short";

const REGISTRAR_META: Record<string, { label: string; color: string }> = {
  namecheap: { label: "Namecheap", color: "text-indigo-300" },
  godaddy: { label: "GoDaddy", color: "text-emerald-300" },
  letshost: { label: "LetsHost", color: "text-amber-300" },
  cloudflare: { label: "Cloudflare", color: "text-orange-300" },
};

function sanitizeSvg(svg: string): string {
  const s = svg.trim();
  if (!s.startsWith("<svg")) return "";
  // strip scripts and event handlers
  return s
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/javascript:/gi, "")
    .replace(/on\w+\s*=/gi, "");
}

function formatRegistrar(po: PriceOption) {
  const meta = REGISTRAR_META[po.source] || {
    label: po.source.charAt(0).toUpperCase() + po.source.slice(1),
    color: "text-white/70",
  };
  return {
    ...po,
    displayName: meta.label,
    displayColor: meta.color,
  };
}

export default function ResultsPage() {
  const router = useRouter();
  const { results, checkedAt, colorPalette, logos, clearSession, hydrated } = useSession();
  const [sort, setSort] = useState<SortMode>("available");

  useEffect(() => {
    if (!hydrated) return;
    if (!results || results.length === 0) {
      router.replace("/");
    }
  }, [results, router, hydrated]);

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

  if (!hydrated) return null;
  if (!results) return null;

  return (
    <main className="flex flex-1 flex-col px-6 py-10">
      <div className="mx-auto w-full max-w-5xl">
        <div className="mb-6 rounded-2xl border border-white/5 bg-white/[0.02] p-4">
          <Stepper />
        </div>

        <div className="mb-2 text-sm text-white/60">
          Step 4 of 4 · Availability checked across multiple registrars
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

        {/* Brand Identity */}
        {(colorPalette || logos) && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-5"
          >
            <div className="mb-4 flex items-center gap-2 text-white">
              <Palette className="h-5 w-5 text-indigo-300" />
              <span className="font-semibold">Brand Identity</span>
            </div>

            {colorPalette && (
              <div className="mb-5 flex flex-wrap items-center gap-3">
                {colorPalette.map((color, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div
                      className="h-10 w-10 rounded-full border border-white/10 shadow"
                      style={{ backgroundColor: color }}
                      title={color}
                    />
                    <span className="text-xs text-white/60 font-mospace">{color}</span>
                  </div>
                ))}
              </div>
            )}

            {logos && (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
                {logos.map((rawSvg, i) => {
                  const svg = sanitizeSvg(rawSvg);
                  return (
                    <div
                      key={i}
                      className="flex aspect-square items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] p-4"
                    >
                      {svg ? (
                        <div
                          className="h-full w-full"
                          dangerouslySetInnerHTML={{ __html: svg }}
                        />
                      ) : (
                        <span className="text-xs text-white/30">Logo {i + 1}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </motion.div>
        )}

        {/* Sort tabs */}
        <div className="mb-6 flex flex-wrap gap-2">
          {[
            { key: "available", label: "Available first", icon: CheckCircle2 },
            { key: "price", label: "Cheapest first", icon: TrendingUp },
            { key: "brand", label: "Best brand", icon: Crown },
            { key: "short", label: "Shortest first", icon: Minimize2 },
          ].map((opt) => (
            <Pill
              key={opt.key}
              selected={sort === opt.key}
              onClick={() => setSort(opt.key as SortMode)}
              icon={<opt.icon className="h-4 w-4" />}
            >
              {opt.label}
            </Pill>
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
              We found {availableCount} available domain{availableCount > 1 ? "s" : ""} that match your brief. Compare prices across registrars and grab the best deal.
            </p>
          </motion.div>
        )}

        {/* Results list */}
        <div className="space-y-4">
          {sorted.map((result, idx) => {
            const isAvailable = result.status === "available";
            const isPremium = result.status === "premium";
            const isTaken = result.status === "taken";
            const prices = (result.prices || [])
              .filter((p) => p.link || p.price)
              .map(formatRegistrar);

            return (
              <motion.div
                key={result.domain}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                className={`
                  rounded-2xl border px-5 py-4 transition-colors
                  ${
                    isAvailable
                      ? "border-emerald-500/20 bg-emerald-500/[0.06]"
                      : isPremium
                      ? "border-amber-500/20 bg-amber-500/[0.05]"
                      : "border-white/10 bg-white/[0.03]"
                  }
                `}
              >
                <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
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

                  {/* Legacy single price fallback */}
                  {!prices.length && result.price && (
                    <div className="text-right">
                      <div className="text-lg font-semibold text-white">
                        {result.price}
                      </div>
                      <div className="text-xs text-white/40">
                        {result.currency || ""}
                      </div>
                    </div>
                  )}
                </div>

                {/* Registrar price grid */}
                {prices.length > 0 && (
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    {prices.map((po) => (
                      <a
                        key={po.source}
                        href={po.link || "#"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 transition-colors hover:bg-white/[0.06] focus:outline-none focus:ring-2 focus:ring-indigo-500/30 active:bg-white/[0.08]"
                      >
                        <div>
                          <div className={`text-xs font-medium ${po.displayColor}`}>
                            {po.displayName}
                          </div>
                          <div className="text-sm font-semibold text-white">
                            {po.price || (
                              <span className="text-white/40">Check price</span>
                            )}
                          </div>
                        </div>
                        {po.link && (
                          <ExternalLink className="h-4 w-4 text-white/30" />
                        )}
                      </a>
                    ))}
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
