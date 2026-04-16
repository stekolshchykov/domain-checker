import type { Brief } from "../types/index.js";

export function buildSystemPrompt(): string {
  return `You are an elite brand naming consultant and domain strategist.
Your task is to generate a large list of brandable, memorable, and meaningful domain names based on the user's brief.

Rules:
1. Generate between 15 and 20 unique domain name ideas.
2. Each idea must include: domainName, meaning, whyItWorks, tone, tags.
3. domainName must be a FULL domain with a TLD (e.g., "novaforge.com").
4. Prefer short, pronounceable, globally readable names.
5. Avoid generic dictionary words unless they are cleverly combined.
6. Do NOT include any markdown, explanations, or text outside the JSON.
7. Return ONLY a valid JSON object matching this exact schema:

{
  "domains": [
    {
      "domainName": "novaforge.com",
      "meaning": "Combines newness and creation energy",
      "whyItWorks": "Short, memorable, and brandable",
      "tone": "modern premium",
      "tags": ["tech", "brandable", "strong"]
    }
  ],
  "meta": {
    "generatedCount": 1,
    "deduplicated": false
  }
}`;
}

export function buildUserPrompt(brief: Brief): string {
  const parts: string[] = [];

  parts.push(`Project description: ${brief.projectDescription}`);

  if (brief.audience) {
    parts.push(`Target audience: ${brief.audience}`);
  }

  if (brief.tone && brief.tone.length > 0) {
    parts.push(`Desired tone(s): ${brief.tone.join(", ")}`);
  }

  parts.push(`Length preference: ${brief.lengthPreference}`);

  if (brief.keywords && brief.keywords.length > 0) {
    parts.push(`Keywords to consider: ${brief.keywords.join(", ")}`);
  }

  if (brief.exclusions && brief.exclusions.length > 0) {
    parts.push(`Words/patterns to exclude: ${brief.exclusions.join(", ")}`);
  }

  if (brief.tlds && brief.tlds.length > 0) {
    parts.push(`Preferred TLDs (use them actively): ${brief.tlds.join(", ")}`);
  } else {
    parts.push(`Preferred TLDs: .com, .io, .ai, .app, .co`);
  }

  parts.push(`\nNow generate the JSON response.`);

  return parts.join("\n");
}
