import { z } from "zod";
import type { GenerateResponse } from "../types/index.js";

export class ResponseParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ResponseParseError";
  }
}

const DomainIdeaSchema = z.object({
  domainName: z.string().min(3).max(100),
  meaning: z.string().min(5).max(500),
  whyItWorks: z.string().min(5).max(500),
  tone: z.string().min(2).max(100),
  tags: z.array(z.string().max(50)).max(10),
});

const GenerateResponseSchema = z.object({
  domains: z.array(DomainIdeaSchema).min(1).max(100),
  meta: z.object({
    generatedCount: z.number().int().min(0),
    deduplicated: z.boolean(),
  }),
});

export function parseKimiContent(content: string): GenerateResponse {
  let raw = content.trim();

  if (raw.startsWith("```json")) {
    raw = raw.replace(/^```json\s*/, "").replace(/\s*```$/, "");
  } else if (raw.startsWith("```")) {
    raw = raw.replace(/^```\s*/, "").replace(/\s*```$/, "");
  }

  try {
    const parsed = JSON.parse(raw);
    return validateGenerateResponse(parsed);
  } catch {
    const match = raw.match(/\{[\s\S]*\}/);
    if (match) {
      try {
        const parsed = JSON.parse(match[0]);
        return validateGenerateResponse(parsed);
      } catch {
        // fall through
      }
    }
    throw new ResponseParseError("Kimi response is not valid JSON");
  }
}

export function validateGenerateResponse(parsed: unknown): GenerateResponse {
  const result = GenerateResponseSchema.safeParse(parsed);
  if (!result.success) {
    throw new ResponseParseError(`Validation failed: ${result.error.message}`);
  }

  const seen = new Set<string>();
  const uniqueDomains = result.data.domains.filter((d) => {
    const key = d.domainName.trim().toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return {
    domains: uniqueDomains,
    meta: {
      generatedCount: uniqueDomains.length,
      deduplicated: uniqueDomains.length !== result.data.domains.length,
    },
  };
}
