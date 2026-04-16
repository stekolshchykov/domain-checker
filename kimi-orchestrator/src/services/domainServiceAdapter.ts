import { z } from "zod";
import type { CheckRequest, CheckResponse, DomainStatus } from "../types/index.js";

const DOMAIN_SERVICE_URL = process.env.DOMAIN_SERVICE_URL || "http://domain-service:8000";
const REQUEST_TIMEOUT_MS = Number(process.env.DOMAIN_SERVICE_TIMEOUT_MS || "30000");

export class DomainServiceError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message);
    this.name = "DomainServiceError";
  }
}

export async function checkDomains(payload: CheckRequest): Promise<CheckResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${DOMAIN_SERVICE_URL}/check`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ domains: payload.domains }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "Unknown error");
      throw new DomainServiceError(`Domain service HTTP ${response.status}: ${text}`);
    }

    const data = await response.json();
    return validateCheckResponse(data);
  } catch (err) {
    if (err instanceof DomainServiceError) throw err;
    throw new DomainServiceError("Failed to reach domain service", err);
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function healthCheck(): Promise<{ status: string; browser_ready: boolean; timestamp: string }> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(`${DOMAIN_SERVICE_URL}/health`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new DomainServiceError(`Domain service health HTTP ${response.status}`);
    }
    const data = (await response.json()) as { status: string; browser_ready: boolean; timestamp: string };
    return data;
  } catch (err) {
    throw new DomainServiceError("Domain service health check failed", err);
  } finally {
    clearTimeout(timeoutId);
  }
}

function validateCheckResponse(data: unknown): CheckResponse {
  const DomainStatusSchema = z.object({
    domain: z.string(),
    status: z.enum(["available", "taken", "premium", "unknown"]),
    price: z.string().nullable().optional(),
    currency: z.string().nullable().optional(),
    source: z.string().optional(),
    detail: z.string().nullable().optional(),
  });

  const schema = z.object({
    results: z.array(DomainStatusSchema),
    checked_at: z.string().datetime(),
    total_checks: z.number().int(),
  });

  const result = schema.safeParse(data);
  if (!result.success) {
    throw new DomainServiceError(`Invalid response from domain service: ${result.error.message}`);
  }

  return {
    results: result.data.results as DomainStatus[],
    checkedAt: result.data.checked_at,
    totalChecks: result.data.total_checks,
  };
}
