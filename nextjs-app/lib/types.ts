export type Tone = "luxurious" | "playful" | "tech" | "minimal" | "bold" | "friendly" | "premium";

export interface Brief {
  projectDescription: string;
  audience?: string;
  tone: Tone[];
  lengthPreference: "short" | "medium" | "long" | "any";
  keywords: string[];
  exclusions: string[];
  tlds: string[];
}

export interface DomainIdea {
  domainName: string;
  meaning: string;
  whyItWorks: string;
  tone: string;
  tags: string[];
}

export interface PriceOption {
  source: string;
  price?: string | null;
  currency?: string | null;
  link?: string | null;
}

export interface DomainResult extends DomainIdea {
  domain: string;
  status: "available" | "taken" | "premium" | "unknown";
  price?: string | null;
  currency?: string | null;
  prices?: PriceOption[];
  selected?: boolean;
}

export const TONE_OPTIONS: { value: Tone; label: string }[] = [
  { value: "tech", label: "Tech" },
  { value: "premium", label: "Premium" },
  { value: "minimal", label: "Minimal" },
  { value: "bold", label: "Bold" },
  { value: "playful", label: "Playful" },
  { value: "friendly", label: "Friendly" },
  { value: "luxurious", label: "Luxurious" },
];

export const TLD_OPTIONS = [".com", ".io", ".ai", ".app", ".co", ".dev", ".net", ".org"];
