import { describe, it, expect } from "vitest";
import { parseKimiContent, validateGenerateResponse, ResponseParseError } from "../src/services/responseParser.js";

describe("parseKimiContent", () => {
  it("parses clean JSON", () => {
    const input = JSON.stringify({
      domains: [
        {
          domainName: "novaforge.com",
          meaning: "New creation",
          whyItWorks: "Short and brandable",
          tone: "modern",
          tags: ["tech"],
        },
      ],
      meta: { generatedCount: 1, deduplicated: false },
    });
    const result = parseKimiContent(input);
    expect(result.domains[0].domainName).toBe("novaforge.com");
    expect(result.meta.generatedCount).toBe(1);
  });

  it("strips markdown code fences", () => {
    const raw =
      '```json\n' +
      JSON.stringify({
        domains: [
          {
            domainName: "test.io",
            meaning: "Testing",
            whyItWorks: "Works",
            tone: "tech",
            tags: ["short"],
          },
        ],
        meta: { generatedCount: 1, deduplicated: false },
      }) +
      '\n```';
    const result = parseKimiContent(raw);
    expect(result.domains[0].domainName).toBe("test.io");
  });

  it("extracts JSON from surrounding text", () => {
    const json = JSON.stringify({
      domains: [
        {
          domainName: "extracted.ai",
          meaning: "Extracted meaning here",
          whyItWorks: "It works perfectly",
          tone: "bold",
          tags: ["ai"],
        },
      ],
      meta: { generatedCount: 1, deduplicated: false },
    });
    const raw = `Here is the result:\n${json}\nHope that helps!`;
    const result = parseKimiContent(raw);
    expect(result.domains[0].domainName).toBe("extracted.ai");
  });

  it("throws on invalid JSON", () => {
    expect(() => parseKimiContent("not json at all")).toThrow(ResponseParseError);
  });
});

describe("validateGenerateResponse", () => {
  it("deduplicates domains case-insensitively", () => {
    const input = {
      domains: [
        {
          domainName: "Dup.com",
          meaning: "First duplicate entry",
          whyItWorks: "Works great",
          tone: "tech",
          tags: [],
        },
        {
          domainName: "dup.com",
          meaning: "Second duplicate entry",
          whyItWorks: "Works great",
          tone: "tech",
          tags: [],
        },
      ],
      meta: { generatedCount: 2, deduplicated: false },
    };
    const result = validateGenerateResponse(input);
    expect(result.domains.length).toBe(1);
    expect(result.meta.deduplicated).toBe(true);
  });

  it("throws on missing required fields", () => {
    const input = {
      domains: [{ domainName: "bad" }],
      meta: { generatedCount: 1, deduplicated: false },
    };
    expect(() => validateGenerateResponse(input)).toThrow(ResponseParseError);
  });
});
