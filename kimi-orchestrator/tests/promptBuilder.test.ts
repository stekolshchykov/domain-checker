import { describe, it, expect } from "vitest";
import { buildSystemPrompt, buildUserPrompt } from "../src/prompts/promptBuilder.js";
import type { Brief } from "../src/types/index.js";

describe("buildSystemPrompt", () => {
  it("contains JSON schema instructions", () => {
    const prompt = buildSystemPrompt();
    expect(prompt).toContain("domainName");
    expect(prompt).toContain("meaning");
    expect(prompt).toContain("whyItWorks");
    expect(prompt).toContain("Return ONLY a valid JSON");
  });
});

describe("buildUserPrompt", () => {
  it("includes all brief fields", () => {
    const brief: Brief = {
      projectDescription: "AI logo generator",
      audience: "startups",
      tone: ["tech", "modern"],
      lengthPreference: "short",
      keywords: ["logo", "brand"],
      exclusions: ["pix"],
      tlds: [".com", ".io"],
    };
    const prompt = buildUserPrompt(brief);
    expect(prompt).toContain("AI logo generator");
    expect(prompt).toContain("startups");
    expect(prompt).toContain("tech");
    expect(prompt).toContain("logo");
    expect(prompt).toContain("pix");
    expect(prompt).toContain(".com");
  });

  it("falls back to default TLDs when none provided", () => {
    const brief: Brief = {
      projectDescription: "Test",
      tone: [],
      lengthPreference: "any",
      keywords: [],
      exclusions: [],
      tlds: [],
    };
    const prompt = buildUserPrompt(brief);
    expect(prompt).toContain(".com, .io, .ai, .app, .co");
  });
});
