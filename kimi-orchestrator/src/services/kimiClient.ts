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

const MOCK_DOMAINS: GenerateResponse = {
  domains: Array.from({ length: 12 }).map((_, i) => ({
    domainName: `novaforge${i === 0 ? "" : i}.com`,
    meaning: "Combines newness and creation energy",
    whyItWorks: "Strong, memorable, tech-forward, brandable",
    tone: "modern premium",
    tags: ["tech", "brandable", "strong", "global"],
  })),
  meta: { generatedCount: 12, deduplicated: true },
};

export async function generateDomains(brief: Brief): Promise<GenerateResponse> {
  if (process.env.KIMI_MOCK_RESPONSE === "true") {
    await sleep(1500);
    return {
      domains: MOCK_DOMAINS.domains.map((d, i) => ({
        ...d,
        domainName: `${brief.projectDescription.slice(0, 6).replace(/\s+/g, "").toLowerCase() || "brand"}${i}.com`,
      })),
      meta: { generatedCount: 12, deduplicated: true },
    };
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
