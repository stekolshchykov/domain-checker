"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Sparkles, ArrowRight, CheckCircle2, Lightbulb, Search, Tag } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { TextArea } from "@/components/ui/TextArea";
import { useSession } from "@/components/SessionProvider";
import { Stepper } from "@/components/Stepper";

const PREVIEW_STEPS = [
  {
    icon: Lightbulb,
    title: "Smart names",
    desc: "AI crafts brandable domain ideas tailored to your project.",
  },
  {
    icon: Tag,
    title: "Why it works",
    desc: "Every suggestion includes meaning, tone, and tags.",
  },
  {
    icon: Search,
    title: "Live availability",
    desc: "We check Namecheap in real-time so you know what’s buyable.",
  },
];

export default function Home() {
  const router = useRouter();
  const { setBrief } = useSession();
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  const handleStart = () => {
    if (!description.trim()) {
      setError("Tell us a little about what you're building.");
      return;
    }
    setBrief({
      projectDescription: description.trim(),
      tone: [],
      lengthPreference: "any",
      keywords: [],
      exclusions: [],
      tlds: [".com", ".io"],
    });
    router.push("/brief");
  };

  return (
    <main className="relative flex flex-1 flex-col items-center px-6 py-10">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="mx-auto w-full max-w-5xl"
      >
        <div className="mx-auto max-w-3xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-400/20 bg-indigo-500/10 px-4 py-1.5 text-sm font-medium text-indigo-200">
            <Sparkles className="h-4 w-4" />
            <span>AI-Powered Naming Studio</span>
          </div>

          <h1 className="mb-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl lg:text-6xl">
            Find a domain name
            <br />
            <span className="bg-gradient-to-r from-indigo-400 via-violet-300 to-indigo-300 bg-clip-text text-transparent">
              that actually fits
            </span>
          </h1>

          <p className="mx-auto mb-8 max-w-xl text-lg text-white/60">
            Describe your idea. Our AI will craft brandable domain names,
            explain why they work, and check availability in seconds.
          </p>
        </div>

        {/* Global stepper */}
        <div className="mx-auto mb-10 max-w-2xl rounded-2xl border border-white/5 bg-white/[0.02] p-4">
          <Stepper />
        </div>

        <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-2 lg:items-start">
          {/* Input card */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="glass-card rounded-3xl p-6 sm:p-8"
          >
            <h2 className="mb-2 text-xl font-semibold text-white">
              What are you building?
            </h2>
            <p className="mb-4 text-sm text-white/50">
              A short description is enough to get started.
            </p>

            <TextArea
              placeholder="e.g., An AI tool that helps startups create brand identities and logos in minutes..."
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
                if (error) setError("");
              }}
              error={error}
              className="mb-4"
            />

            <Button onClick={handleStart} size="lg" className="w-full">
              Start naming
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>

            <div className="mt-4 flex items-center justify-center gap-4 text-xs text-white/40">
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" />
                No sign-up
              </span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Free to explore
              </span>
            </div>
          </motion.div>

          {/* Preview / what you get */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.35, duration: 0.5 }}
            className="space-y-4"
          >
            <div className="mb-2 text-sm font-medium uppercase tracking-wider text-white/40">
              What you&apos;ll get
            </div>

            {PREVIEW_STEPS.map((item, idx) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.45 + idx * 0.1 }}
                className="flex items-start gap-4 rounded-2xl border border-white/5 bg-white/[0.02] p-4 transition-colors hover:bg-white/[0.04]"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-300">
                  <item.icon className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-medium text-white">{item.title}</h3>
                  <p className="text-sm text-white/50">{item.desc}</p>
                </div>
              </motion.div>
            ))}

            {/* Sample result card */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.75 }}
              className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-indigo-500/10 to-violet-500/10 p-5"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-lg font-semibold text-white">novaforge.com</span>
                <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-300">
                  Available
                </span>
              </div>
              <p className="mb-2 text-sm text-white/70">
                Combines newness and creation energy
              </p>
              <p className="mb-3 text-xs text-white/50">
                Strong, memorable, tech-forward, brandable
              </p>
              <div className="flex flex-wrap gap-2">
                {["tech", "brandable", "premium"].map((t) => (
                  <span
                    key={t}
                    className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs text-white/70"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </motion.div>
          </motion.div>
        </div>
      </motion.div>
    </main>
  );
}
