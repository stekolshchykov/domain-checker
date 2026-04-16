import type { Brief } from "../types/index.js";

export function buildSystemPrompt(): string {
  return `You are an elite brand naming consultant, domain strategist, and brand designer.
Your task is to generate a large list of brandable domain names AND a cohesive visual identity based on the user's brief.

Rules:
1. Generate between 15 and 20 unique domain name ideas.
2. Each idea must include: domainName, meaning, whyItWorks, tone, tags.
3. domainName must be a FULL domain with a TLD (e.g., "novaforge.com").
4. Prefer short, pronounceable, globally readable names.
5. Avoid generic dictionary words unless they are cleverly combined.
6. Also generate a color palette and 5 SVG logo concepts inspired by the top name ideas and the brief.
7. Do NOT include any markdown, explanations, or text outside the JSON.
8. Return ONLY a valid JSON object matching this exact schema:

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
  "colorPalette": ["#0F172A", "#6366F1", "#22D3EE", "#F8FAFC", "#94A3B8"],
  "logos": [
    "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 100 100\">...</svg>",
    ...
  ],
  "meta": {
    "generatedCount": 1,
    "deduplicated": false
  }
}

Visual identity rules:
- colorPalette: exactly 5 hex colors. The first is the primary dark/background, the second is the primary brand color, the third is an accent, the fourth is a light/neutral, and the fifth is a secondary neutral.
- logos: exactly 5 unique SVG strings. Each must be a self-contained inline SVG (no external images, no CSS animations, minimal flat vector shapes). Keep each SVG under 5 KB. Make them modern, simple, and relevant to the brand concept.`;
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
