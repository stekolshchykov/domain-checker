"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Sparkles, Wand2, Lightbulb, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { useSession } from "@/components/SessionProvider";
import { generateDomainIdeas } from "@/lib/actions";
import { Stepper } from "@/components/Stepper";

const STEPS = [
  { icon: Sparkles, text: "Understanding your brand..." },
  { icon: Wand2, text: "Crafting name ideas..." },
  { icon: Lightbulb, text: "Evaluating brandability..." },
  { icon: Search, text: "Preparing suggestions..." },
];

export default function GeneratingPage() {
  const router = useRouter();
  const { brief, setIdeas, setGenerationExtras, hydrated } = useSession();
  const [progress, setProgress] = useState(10);
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hydrated) return;
    if (!brief) {
      router.replace("/");
      return;
    }

    let isActive = true;

    async function run() {
      if (!brief) return;
      try {
        const timers: NodeJS.Timeout[] = [];
        timers.push(setTimeout(() => isActive && setProgress(25), 200));
        timers.push(setTimeout(() => isActive && setStepIndex(1), 600));
        timers.push(setTimeout(() => isActive && setProgress(50), 800));
        timers.push(setTimeout(() => isActive && setStepIndex(2), 1500));
        timers.push(setTimeout(() => isActive && setProgress(75), 1800));
        timers.push(setTimeout(() => isActive && setStepIndex(3), 2500));

        const result = await generateDomainIdeas(brief);

        if (!isActive) return;
        // Clear pending animation timers so we transition immediately
        timers.forEach(clearTimeout);
        setProgress(100);
        setStepIndex(3);
        setIdeas(result.domains);
        setGenerationExtras(result.colorPalette, result.logos);

        timers.push(
          setTimeout(() => {
            if (isActive) router.push("/ideas");
          }, 400)
        );
      } catch (err) {
        if (!isActive) return;
        setError(err instanceof Error ? err.message : "Something went wrong");
      }
    }

    run();

    return () => {
      isActive = false;
    };
  }, [brief, router, setIdeas, setGenerationExtras, hydrated]);

  if (!hydrated) return null;

  if (error) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center px-6">
        <div className="glass-card max-w-md rounded-3xl p-8 text-center">
          <h2 className="mb-2 text-xl font-semibold text-white">
            Generation failed
          </h2>
          <p className="mb-6 text-white/60">{error}</p>
          <Button onClick={() => router.push("/brief")}>
            Try again
          </Button>
        </div>
      </main>
    );
  }

  const CurrentIcon = STEPS[stepIndex].icon;

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-10">
      <div className="w-full max-w-2xl">
        <div className="mb-6 rounded-2xl border border-white/5 bg-white/[0.02] p-4">
          <Stepper />
        </div>

        <div className="mb-4 text-center text-sm text-white/60">
          Step 3 of 4 · AI is crafting your names
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md text-center"
      >
        <div className="mb-8 flex justify-center">
          <div className="relative flex h-20 w-20 items-center justify-center rounded-3xl bg-indigo-500/15 text-indigo-300 shadow-[0_0_40px_rgba(99,102,241,0.25)]">
            <CurrentIcon className="h-8 w-8" />
            <span className="absolute inset-0 animate-pulse rounded-3xl bg-indigo-400/10" />
          </div>
        </div>

        <motion.h2
          key={stepIndex}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-2 text-2xl font-semibold text-white"
        >
          {STEPS[stepIndex].text}
        </motion.h2>

        <p className="mb-8 text-white/50">
          This usually takes 30–90 seconds. You&apos;ll get names with meaning, tone, and tags.
        </p>

        <ProgressBar progress={progress} className="mb-2" />
        <p className="text-right text-xs text-white/30">{progress}%</p>
      </motion.div>
    </main>
  );
}
