import { Router, type Request, type Response, type NextFunction } from "express";
import { z } from "zod";
import {
  BriefSchema,
  CheckRequestSchema,
  type Brief,
  type FinalCheckResponse,
  type GenerateResponse,
} from "../types/index.js";
import { generateDomains } from "../services/kimiClient.js";
import { checkDomains, healthCheck as domainHealthCheck } from "../services/domainServiceAdapter.js";

const router = Router();

// In-memory cache for demo/testing (optional, simple)
const generationCache = new Map<string, GenerateResponse>();

router.get("/health", async (_req, res, next) => {
  try {
    const domainHealth = await domainHealthCheck();
    res.json({
      status: "ok",
      domainService: domainHealth.status === "ok" ? "healthy" : "unhealthy",
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    next(err);
  }
});

router.post("/generate", async (req, res, next) => {
  try {
    const parsed = BriefSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(422).json({
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid brief format",
          details: parsed.error.issues,
        },
      });
      return;
    }

    const brief: Brief = parsed.data;
    const result = await generateDomains(brief);

    // Store in cache keyed by a simple hash for later merge during check
    const cacheKey = JSON.stringify(brief);
    generationCache.set(cacheKey, result);

    res.json(result);
  } catch (err) {
    next(err);
  }
});

router.post("/check", async (req, res, next) => {
  try {
    const parsed = CheckRequestSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(422).json({
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid check request",
          details: parsed.error.issues,
        },
      });
      return;
    }

    const availability = await checkDomains(parsed.data);

    // Merge with generation context if provided
    const context = (req.body.context || {}) as { brief?: Brief };
    let merged: FinalCheckResponse;

    if (context.brief) {
      const cacheKey = JSON.stringify(context.brief);
      const cached = generationCache.get(cacheKey);
      if (cached) {
        const ideaMap = new Map(cached.domains.map((d) => [d.domainName.toLowerCase(), d]));
        merged = {
          results: availability.results.map((r) => {
            const idea = ideaMap.get(r.domain.toLowerCase());
            return {
              ...r,
              meaning: idea?.meaning,
              whyItWorks: idea?.whyItWorks,
              tone: idea?.tone,
              tags: idea?.tags,
            };
          }),
          checkedAt: availability.checkedAt,
          totalChecks: availability.totalChecks,
        };
        res.json(merged);
        return;
      }
    }

    merged = {
      results: availability.results,
      checkedAt: availability.checkedAt,
      totalChecks: availability.totalChecks,
    };

    res.json(merged);
  } catch (err) {
    next(err);
  }
});

export default router;
