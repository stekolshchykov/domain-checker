import type { Brief, GenerateResponse } from "../types/index.js";
import { buildSystemPrompt, buildUserPrompt } from "../prompts/promptBuilder.js";
import { parseKimiContent } from "./responseParser.js";

const KIMI_API_KEY = process.env.KIMI_API_KEY || "";
const KIMI_API_BASE_URL = process.env.KIMI_API_BASE_URL || "https://api.kimi.com/coding/v1";
const KIMI_MODEL = process.env.KIMI_MODEL || "kimi-for-coding";
const REQUEST_TIMEOUT_MS = Number(process.env.KIMI_REQUEST_TIMEOUT_MS || "180000");
const MAX_RETRIES = Number(process.env.KIMI_MAX_RETRIES || "2");

export class KimiClientError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message);
    this.name = "KimiClientError";
  }
}

export interface KimiMessage {
  role: "system" | "user" | "assistant";
  content: string;
  reasoning_content?: string;
}

export interface KimiChoice {
  message: KimiMessage;
  finish_reason: string;
  index: number;
}

export interface KimiResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: KimiChoice[];
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function callKimi(messages: KimiMessage[], attempt: number): Promise<KimiResponse> {
  if (!KIMI_API_KEY) {
    throw new KimiClientError("KIMI_API_KEY is not configured");
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${KIMI_API_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${KIMI_API_KEY}`,
        "User-Agent": "claude-code/1.0",
      },
      body: JSON.stringify({
        model: KIMI_MODEL,
        messages,
        temperature: 0.85,
        max_tokens: 8192,
        response_format: { type: "json_object" },
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "Unknown error");
      throw new KimiClientError(`Kimi API HTTP ${response.status}: ${text}`);
    }

    const data = (await response.json()) as KimiResponse;
    return data;
  } catch (err) {
    if (err instanceof KimiClientError) throw err;
    throw new KimiClientError(`Kimi API request failed (attempt ${attempt + 1})`, err);
  } finally {
    clearTimeout(timeoutId);
  }
}

const MOCK_PALETTES = [
  ["#0F172A", "#6366F1", "#22D3EE", "#F8FAFC", "#94A3B8"],
  ["#1A0B2E", "#FF4ECD", "#7B61FF", "#F3F0FF", "#B8B2D1"],
  ["#0D1F2D", "#2EC4B6", "#E71D36", "#FDFFFC", "#A8B2C1"],
  ["#1C1C1E", "#F5A623", "#4A90E2", "#F8F8F8", "#9B9B9B"],
  ["#121212", "#00D9FF", "#FF0055", "#EAEAEA", "#8E8E93"],
];

function makeMockSvg(index: number, color: string): string {
  const shapes = [
    `<circle cx="50" cy="50" r="40" fill="${color}"/>`,
    `<rect x="15" y="15" width="70" height="70" rx="18" fill="${color}"/>`,
    `<polygon points="50,10 90,90 10,90" fill="${color}"/>`,
    `<path d="M10,50 Q30,10 50,50 T90,50" stroke="${color}" stroke-width="12" fill="none"/>`,
    `<circle cx="50" cy="50" r="35" fill="none" stroke="${color}" stroke-width="10"/><circle cx="50" cy="50" r="15" fill="${color}"/>`,
  ];
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">${shapes[index % shapes.length]}</svg>`;
}

const PREFIXES = [
  "nova", "flux", "zen", "bolt", "nexus", "loom", "orbit", "spark", "cipher",
  "drift", "pulse", "aura", "echo", "glyph", "prism", "verge", "fable", "quark",
  "neon", "vox", "synth", "haven", "rift", "cinder", "myth", "ember",
];

const SUFFIXES = [
  "forge", "lab", "io", "hub", "ly", "ify", "scape", "works", "node", "path",
  "base", "flow", "cast", "loom", "bits", "deck", "verse", "trail", "spark",
  "field", "kit", "tap", "nest", "grid", "lane",
];

const TONES = [
  "modern premium", "playful tech", "minimal elegant", "bold corporate",
  "friendly creative", "futuristic clean", "warm artisan", "sharp professional",
];

const TAG_POOLS = [
  ["tech", "brandable", "short", "global"],
  ["creative", "modern", "memorable", "clean"],
  ["premium", "sleek", "professional", "trustworthy"],
  ["playful", "friendly", "approachable", "fresh"],
  ["innovative", "futuristic", "dynamic", "smart"],
];

function hashString(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h += (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24);
  }
  return Math.abs(h);
}

function seededRand(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function pick<T>(arr: T[], seed: number): T {
  return arr[Math.floor(seededRand(seed) * arr.length)];
}

function buildMockName(seed: number, tlds: string[]): string {
  const prefix = pick(PREFIXES, seed);
  const suffix = pick(SUFFIXES, seed + 1);
  const tld = tlds.length ? pick(tlds, seed + 2) : ".com";
  const combo = `${prefix}${suffix}`;
  return `${combo}${tld}`;
}

function capitalize(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

function buildMockDomains(brief: Brief): GenerateResponse {
  const rawSeed = hashString(brief.projectDescription + (brief.keywords?.join("") ?? ""));
  const tlds = brief.tlds?.length ? brief.tlds : [".com"];
  const palette = pick(MOCK_PALETTES, rawSeed);
  const brandColor = palette[1];

  const used = new Set<string>();
  const domains: DomainIdea[] = [];

  for (let i = 0; i < 12; i++) {
    const seed = rawSeed + i * 31;
    let name = buildMockName(seed, tlds);
    let attempts = 0;
    while (used.has(name) && attempts < 10) {
      name = buildMockName(seed + attempts + 100, tlds);
      attempts++;
    }
    used.add(name);

    const base = name.split(".")[0];
    const tone = pick(TONES, seed + 3);
    const tags = pick(TAG_POOLS, seed + 4);
    const prefix = pick(PREFIXES, seed);
    const suffix = pick(SUFFIXES, seed + 1);

    domains.push({
      domainName: name,
      meaning: `Blends "${prefix}" and "${suffix}" to evoke ${tone} energy around ${brief.keywords?.[0] || brief.projectDescription.split(" ")[0] || "your idea"}.`,
      whyItWorks: `${capitalize(base)} is ${pick(["short", "crisp", "snappy", "smooth"], seed + 5)}, easy to pronounce globally, and feels ${tone}.`,
      tone,
      tags: [...tags],
    });
  }

  const logos = Array.from({ length: 5 }).map((_, i) => makeMockSvg(i + rawSeed, brandColor));

  return {
    domains,
    colorPalette: palette,
    logos,
    meta: { generatedCount: domains.length, deduplicated: true },
  };
}

export async function generateDomains(brief: Brief): Promise<GenerateResponse> {
  if (process.env.KIMI_MOCK_RESPONSE === "true") {
    await sleep(1500);
    return buildMockDomains(brief);
  }

  const messages: KimiMessage[] = [
    { role: "system", content: buildSystemPrompt() },
    { role: "user", content: buildUserPrompt(brief) },
  ];

  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      if (attempt > 0) {
        await sleep(1000 * attempt);
      }
      const response = await callKimi(messages, attempt);
      const choice = response.choices[0];
      if (!choice) {
        throw new KimiClientError("No choices returned from Kimi API");
      }
      const content = choice.message.content ?? "";
      const reasoning = choice.message.reasoning_content ?? "";
      console.log("[KimiClient] content length:", content.length, "reasoning length:", reasoning.length);
      const rawContent = content.trim() || reasoning.trim() || "";
      if (!rawContent.trim()) {
        throw new KimiClientError("Kimi API returned empty content and reasoning content");
      }
      try {
        return parseKimiContent(rawContent);
      } catch (parseErr) {
        console.error("[KimiClient] Failed to parse rawContent (first 800 chars):", rawContent.slice(0, 800));
        console.error("[KimiClient] Failed to parse rawContent (last 200 chars):", rawContent.slice(-200));
        throw parseErr;
      }
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
    }
  }

  throw new KimiClientError(
    `All ${MAX_RETRIES + 1} attempts failed. Last error: ${lastError?.message}`,
    lastError
  );
}
