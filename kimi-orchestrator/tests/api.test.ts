import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import request from "supertest";
import { createApp } from "../src/app.js";

// Mock Kimi client and domain service adapter before importing routes
vi.mock("../src/services/kimiClient.js", () => ({
  generateDomains: vi.fn(),
}));

vi.mock("../src/services/domainServiceAdapter.js", () => ({
  checkDomains: vi.fn(),
  healthCheck: vi.fn(),
}));

import { generateDomains } from "../src/services/kimiClient.js";
import { checkDomains, healthCheck } from "../src/services/domainServiceAdapter.js";

const app = createApp();

describe("API routes", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    process.env.KIMI_API_KEY = "test-key";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GET /api/health returns ok when domain service is healthy", async () => {
    vi.mocked(healthCheck).mockResolvedValue({
      status: "ok",
      browser_ready: true,
      timestamp: new Date().toISOString(),
    });

    const res = await request(app).get("/api/health");
    expect(res.status).toBe(200);
    expect(res.body.status).toBe("ok");
    expect(res.body.domainService).toBe("healthy");
  });

  it("POST /api/generate returns domains", async () => {
    vi.mocked(generateDomains).mockResolvedValue({
      domains: [
        {
          domainName: "testbrand.com",
          meaning: "A test brand",
          whyItWorks: "It's short",
          tone: "modern",
          tags: ["tech"],
        },
      ],
      meta: { generatedCount: 1, deduplicated: false },
    });

    const res = await request(app).post("/api/generate").send({
      projectDescription: "A test project",
      tone: ["tech"],
      lengthPreference: "short",
      keywords: [],
      exclusions: [],
      tlds: [".com"],
    });

    expect(res.status).toBe(200);
    expect(res.body.domains).toHaveLength(1);
    expect(res.body.domains[0].domainName).toBe("testbrand.com");
  });

  it("POST /api/generate returns 422 for invalid brief", async () => {
    const res = await request(app).post("/api/generate").send({
      projectDescription: "",
    });
    expect(res.status).toBe(422);
    expect(res.body.error.code).toBe("VALIDATION_ERROR");
  });

  it("POST /api/check returns merged results", async () => {
    vi.mocked(checkDomains).mockResolvedValue({
      results: [
        { domain: "testbrand.com", status: "available", source: "namecheap" },
      ],
      checkedAt: new Date().toISOString(),
      totalChecks: 1,
    });

    const res = await request(app).post("/api/check").send({
      domains: ["testbrand.com"],
    });

    expect(res.status).toBe(200);
    expect(res.body.results[0].status).toBe("available");
  });
});
