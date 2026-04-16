"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Sparkles, Wand2, Lightbulb, Search } from "lucide-react";
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
  const { brief, setIdeas } = useSession();
  const [progress, setProgress] = useState(10);
  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!brief) {
      router.replace("/");
      return;
    }

    let mounted = true;

    async function run() {
      if (!brief) return;
      try {
        const timers: NodeJS.Timeout[] = [];
        timers.push(setTimeout(() => mounted && setProgress(25), 400));
        timers.push(setTimeout(() => mounted && setStepIndex(1), 1200));
        timers.push(setTimeout(() => mounted && setProgress(50), 1600));
        timers.push(setTimeout(() => mounted && setStepIndex(2), 3000));
        timers.push(setTimeout(() => mounted && setProgress(75), 3600));
        timers.push(setTimeout(() => mounted && setStepIndex(3), 5000));

        const result = await generateDomainIdeas(brief);

        if (!mounted) return;
        setProgress(100);
        setIdeas(result.domains);

        timers.push(
          setTimeout(() => {
            if (mounted) router.push("/ideas");
          }, 800)
        );
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Something went wrong");
      }
    }

    run();

    return () => {
      mounted = false;
    };
  }, [brief, router, setIdeas]);

  if (error) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center px-6">
        <div className="glass-card max-w-md rounded-3xl p-8 text-center">
          <h2 className="mb-2 text-xl font-semibold text-white">
            Generation failed
          </h2>
          <p className="mb-6 text-white/60">{error}</p>
          <button
            onClick={() => router.push("/brief")}
            className="rounded-xl bg-white px-6 py-2.5 font-medium text-gray-950 hover:bg-gray-100"
          >
            Try again
          </button>
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
