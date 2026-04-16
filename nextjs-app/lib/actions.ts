"use server";

import type { Brief, DomainIdea, DomainResult } from "./types";

const ORCHESTRATOR_URL = process.env.KIMI_ORCHESTRATOR_URL || "http://localhost:4000";

interface GenerateApiResponse {
  domains: DomainIdea[];
  meta: { generatedCount: number; deduplicated: boolean };
}

interface CheckApiResponse {
  results: DomainResult[];
  checkedAt: string;
  totalChecks: number;
}

export async function generateDomainIdeas(brief: Brief): Promise<GenerateApiResponse> {
  const res = await fetch(`${ORCHESTRATOR_URL}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(brief),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`Generation failed: ${text}`);
  }

  return (await res.json()) as GenerateApiResponse;
}

export async function checkDomainAvailability(
  domains: string[],
  brief: Brief,
  ideas: DomainIdea[]
): Promise<CheckApiResponse> {
  const res = await fetch(`${ORCHESTRATOR_URL}/api/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domains,
      context: { brief, ideas },
    }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`Check failed: ${text}`);
  }

  return (await res.json()) as CheckApiResponse;
}
