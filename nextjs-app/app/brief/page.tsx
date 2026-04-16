"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, ArrowLeft, Users, Palette, Sliders, FileText } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { TextArea } from "@/components/ui/TextArea";
import { Chip } from "@/components/ui/Chip";
import { ToggleButton } from "@/components/ui/ToggleButton";
import { useSession } from "@/components/SessionProvider";
import { TONE_OPTIONS, TLD_OPTIONS, type Tone } from "@/lib/types";
import { Stepper } from "@/components/Stepper";

const STEP_ICONS = [Users, Palette, Sliders];
const STEP_TITLES = ["Project & Audience", "Tone & Style", "Keywords & TLDs"];

export default function BriefPage() {
  const router = useRouter();
  const { brief, setBrief, hydrated } = useSession();
  const [step, setStep] = useState(0);

  const [projectDescription, setProjectDescription] = useState(brief?.projectDescription || "");
  const [audience, setAudience] = useState(brief?.audience || "");
  const [tone, setTone] = useState<Tone[]>(brief?.tone || []);
  const [lengthPreference, setLengthPreference] = useState(brief?.lengthPreference || "any");
  const [keywords, setKeywords] = useState(brief?.keywords?.join(", ") || "");
  const [exclusions, setExclusions] = useState(brief?.exclusions?.join(", ") || "");
  const [tlds, setTlds] = useState<string[]>(brief?.tlds || [".com", ".io"]);

  useEffect(() => {
    if (hydrated && !brief) {
      router.replace("/");
    }
  }, [brief, router, hydrated]);

  const toggleTone = (t: Tone) => {
    setTone((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  const toggleTld = (t: string) => {
    setTlds((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  const handleNext = () => {
    if (step < 2) {
      setStep(step + 1);
      return;
    }
    const finalBrief = {
      projectDescription: projectDescription.trim(),
      audience: audience.trim() || undefined,
      tone,
      lengthPreference: lengthPreference as any,
      keywords: keywords
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      exclusions: exclusions
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      tlds: tlds.length > 0 ? tlds : [".com"],
    };
    setBrief(finalBrief as any);
    router.push("/generating");
  };

  const canProceed = () => {
    if (step === 0) return projectDescription.trim().length > 0;
    if (step === 1) return tone.length > 0;
    return true;
  };

  const StepIcon = STEP_ICONS[step];

  if (!hydrated) return null;

  return (
    <main className="flex flex-1 flex-col items-center px-6 py-10">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-2xl"
      >
        {/* Global flow stepper */}
        <div className="mb-6 rounded-2xl border border-white/5 bg-white/[0.02] p-4">
          <Stepper />
        </div>

        <div className="mb-4 flex items-center gap-3 text-white/60">
          <FileText className="h-4 w-4" />
          <span className="text-sm">Step 2 of 4 · Refine your brief</span>
        </div>

        {/* Internal brief stepper */}
        <div className="mb-6">
          <div className="mb-3 flex items-center justify-between">
            {STEP_TITLES.map((title, idx) => (
              <div key={title} className="flex flex-1 flex-col items-center">
                <div
                  className={`mb-2 flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                    idx <= step
                      ? "bg-indigo-500 text-white shadow-[0_0_16px_rgba(99,102,241,0.35)]"
                      : "bg-white/5 text-white/40"
                  }`}
                >
                  {idx + 1}
                </div>
                <span
                  className={`hidden text-xs font-medium sm:block ${
                    idx <= step ? "text-white/80" : "text-white/30"
                  }`}
                >
                  {title}
                </span>
              </div>
            ))}
          </div>
          <div className="h-1 w-full rounded-full bg-white/10">
            <motion.div
              className="h-full rounded-full bg-indigo-500"
              initial={{ width: 0 }}
              animate={{ width: `${((step + 1) / 3) * 100}%` }}
              transition={{ type: "spring", stiffness: 80, damping: 15 }}
            />
          </div>
        </div>

        {/* Card */}
        <div className="glass-card rounded-3xl p-6 sm:p-10">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-300">
              <StepIcon className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">
                {STEP_TITLES[step]}
              </h2>
              <p className="text-sm text-white/50">
                Step {step + 1} of 3
              </p>
            </div>
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
              className="space-y-5"
            >
              {step === 0 && (
                <>
                  <TextArea
                    label="Project description"
                    value={projectDescription}
                    onChange={(e) => setProjectDescription(e.target.value)}
                    placeholder="Describe your product, service, or idea..."
                  />
                  <Input
                    label="Target audience"
                    value={audience}
                    onChange={(e) => setAudience(e.target.value)}
                    placeholder="e.g., SaaS founders, Gen Z creators, luxury travelers..."
                  />
                </>
              )}

              {step === 1 && (
                <>
                  <div>
                    <label className="mb-3 block text-sm font-medium text-white/80">
                      What tone should the name convey?
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {TONE_OPTIONS.map((opt) => (
                        <Chip
                          key={opt.value}
                          label={opt.label}
                          selected={tone.includes(opt.value)}
                          onClick={() => toggleTone(opt.value)}
                        />
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="mb-3 block text-sm font-medium text-white/80">
                      Preferred name length
                    </label>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {(["short", "medium", "long", "any"] as const).map(
                        (len) => (
                          <ToggleButton
                            key={len}
                            selected={lengthPreference === len}
                            onClick={() => setLengthPreference(len)}
                          >
                            {len}
                          </ToggleButton>
                        )
                      )}
                    </div>
                  </div>
                </>
              )}

              {step === 2 && (
                <>
                  <Input
                    label="Keywords to include"
                    value={keywords}
                    onChange={(e) => setKeywords(e.target.value)}
                    placeholder="e.g., nova, forge, brand, pixel"
                  />
                  <Input
                    label="Words or patterns to exclude"
                    value={exclusions}
                    onChange={(e) => setExclusions(e.target.value)}
                    placeholder="e.g., ly, io, tech"
                  />
                  <div>
                    <label className="mb-3 block text-sm font-medium text-white/80">
                      Preferred domain extensions
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {TLD_OPTIONS.map((tld) => (
                        <Chip
                          key={tld}
                          label={tld}
                          selected={tlds.includes(tld)}
                          onClick={() => toggleTld(tld)}
                        />
                      ))}
                    </div>
                  </div>
                </>
              )}
            </motion.div>
          </AnimatePresence>

          <div className="mt-8 flex items-center justify-between gap-4">
            <Button
              variant="ghost"
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              disabled={step === 0}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button
              onClick={handleNext}
              disabled={!canProceed()}
            >
              {step === 2 ? "Generate names" : "Next"}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </motion.div>
    </main>
  );
}
