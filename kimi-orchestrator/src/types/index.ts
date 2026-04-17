import { z } from "zod";

export const BriefSchema = z.object({
  projectDescription: z.string().min(1).max(2000),
  audience: z.string().min(1).max(500).optional(),
  tone: z.array(z.string()).max(10).optional(),
  lengthPreference: z.enum(["short", "medium", "long", "any"]).default("any"),
  keywords: z.array(z.string().max(50)).max(20).optional(),
  exclusions: z.array(z.string().max(50)).max(20).optional(),
  tlds: z.array(z.string().regex(/^\.[a-z]{2,}$/)).max(10).optional(),
});

export type Brief = z.infer<typeof BriefSchema>;

export const DomainIdeaSchema = z.object({
  domainName: z.string().min(3).max(100),
  meaning: z.string().min(5).max(500),
  whyItWorks: z.string().min(5).max(500),
  tone: z.string().min(2).max(100),
  tags: z.array(z.string().max(50)).max(10),
});

export type DomainIdea = z.infer<typeof DomainIdeaSchema>;

export const GenerateResponseSchema = z.object({
  domains: z.array(DomainIdeaSchema).min(1).max(100),
  colorPalette: z.array(z.string().regex(/^#[0-9A-Fa-f]{6}$/)).length(5),
  logos: z.array(z.string().min(50).max(50000)).length(5),
  meta: z.object({
    generatedCount: z.number().int().min(0),
    deduplicated: z.boolean(),
  }),
});

export type GenerateResponse = z.infer<typeof GenerateResponseSchema>;

export const CheckRequestSchema = z.object({
  domains: z.array(z.string().min(3).max(100)).min(1).max(50),
  context: z.record(z.any()).optional(),
});

export type CheckRequest = z.infer<typeof CheckRequestSchema>;

export const PriceOptionSchema = z.object({
  source: z.string(),
  price: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
  link: z.string().nullable().optional(),
}).passthrough();

export type PriceOption = z.infer<typeof PriceOptionSchema>;

export const DomainStatusSchema = z.object({
  domain: z.string(),
  status: z.enum(["available", "taken", "premium", "unknown"]),
  price: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
  source: z.string().optional(),
  detail: z.string().nullable().optional(),
  prices: z.array(PriceOptionSchema).optional(),
}).passthrough();

export type DomainStatus = z.infer<typeof DomainStatusSchema>;

export const CheckResponseSchema = z.object({
  results: z.array(DomainStatusSchema),
  checkedAt: z.string().datetime(),
  totalChecks: z.number().int(),
});

export type CheckResponse = z.infer<typeof CheckResponseSchema>;

export const FinalResultSchema = DomainStatusSchema.extend({
  meaning: z.string().optional(),
  whyItWorks: z.string().optional(),
  tone: z.string().optional(),
  tags: z.array(z.string()).optional(),
});

export type FinalResult = z.infer<typeof FinalResultSchema>;

export const FinalCheckResponseSchema = z.object({
  results: z.array(FinalResultSchema),
  checkedAt: z.string().datetime(),
  totalChecks: z.number().int(),
  colorPalette: z.array(z.string()).optional(),
  logos: z.array(z.string()).optional(),
});

export type FinalCheckResponse = z.infer<typeof FinalCheckResponseSchema>;
