import html
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Sequence
from urllib.parse import quote_plus

from src.models import FinalStatus


_PRICE_RE = re.compile(r"([€$£¥₹])\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_RENEWAL_RE = re.compile(
    r"renew(?:al)?[^€$£¥₹0-9]{0,30}([€$£¥₹]\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    flags=re.IGNORECASE,
)


@dataclass(slots=True)
class KeywordRules:
    available: Sequence[str] = field(default_factory=tuple)
    unavailable: Sequence[str] = field(default_factory=tuple)
    premium: Sequence[str] = field(default_factory=tuple)
    promo: Sequence[str] = field(default_factory=tuple)
    transfer_only: Sequence[str] = field(default_factory=tuple)
    unsupported_tld: Sequence[str] = field(default_factory=tuple)
    blocked: Sequence[str] = field(default_factory=tuple)
    rate_limited: Sequence[str] = field(default_factory=tuple)
    temporarily_unavailable: Sequence[str] = field(default_factory=tuple)


@dataclass(slots=True)
class ParserResult:
    final_status: FinalStatus
    registration_price: str | None = None
    renewal_price: str | None = None
    currency: str | None = None
    premium: bool = False
    promo: bool = False
    note: str | None = None
    confidence: float = 0.5


COMMON_RULES = KeywordRules(
    available=(
        "is available",
        "available to register",
        "domain available",
        "can be registered",
        "get this domain",
        "add to cart",
        "register now",
    ),
    unavailable=(
        "already registered",
        "already taken",
        "is taken",
        "is not available",
        "domain unavailable",
        "not available for registration",
    ),
    premium=(
        "premium",
        "aftermarket",
        "make offer",
        "broker",
        "buy this premium",
    ),
    promo=(
        "discount",
        "promo",
        "first year",
        "save",
        "special offer",
        "sale",
    ),
    transfer_only=(
        "transfer your domain",
        "transfer this domain",
        "transfer only",
        "already own this domain",
    ),
    unsupported_tld=(
        "unsupported tld",
        "tld not supported",
        "invalid tld",
        "extension is not supported",
    ),
    blocked=(
        "captcha",
        "access denied",
        "forbidden",
        "security check",
        "bot detection",
        "challenge required",
        "cloudflare ray id",
        "attention required",
        "enable javascript and cookies",
        "verify you are human",
        "request blocked",
        "access to this page has been denied",
        "incapsula incident id",
        "please verify you are human",
        "sign in to continue",
        "login required",
    ),
    rate_limited=(
        "too many requests",
        "rate limit",
        "slow down",
        "request limit exceeded",
    ),
    temporarily_unavailable=(
        "temporarily unavailable",
        "service unavailable",
        "try again later",
        "under maintenance",
    ),
)


def parse_with_keyword_rules(html_text: str, domain: str, custom_rules: KeywordRules | None = None) -> ParserResult:
    plain_text = _to_plain_text(html_text)
    plain_lower = plain_text.lower()
    domain_lower = domain.lower()
    context_lower, domain_found = _domain_context(plain_lower, domain_lower)

    rules = _merge_rules(COMMON_RULES, custom_rules)

    if _contains_any(rules.blocked, context_lower):
        return ParserResult(final_status=FinalStatus.BLOCKED, note="blocked or captcha", confidence=0.9)
    if _contains_any(rules.rate_limited, context_lower):
        return ParserResult(final_status=FinalStatus.RATE_LIMITED, note="rate-limited", confidence=0.9)
    if _contains_any(rules.temporarily_unavailable, context_lower):
        return ParserResult(final_status=FinalStatus.TEMPORARILY_UNAVAILABLE, note="temporary failure", confidence=0.85)
    if _contains_any(rules.unsupported_tld, context_lower):
        return ParserResult(final_status=FinalStatus.UNSUPPORTED_TLD, note="unsupported tld", confidence=0.9)

    available_flag = _contains_any(rules.available, context_lower)
    unavailable_flag = _contains_any(rules.unavailable, context_lower)
    premium_flag = _contains_any(rules.premium, context_lower)
    promo_flag = _contains_any(rules.promo, context_lower)
    transfer_flag = _contains_any(rules.transfer_only, context_lower)

    json_available = _extract_json_availability(html_text)
    if json_available is not None and not (domain_found or _domain_in_raw_html(html_text, domain_lower)):
        # Guard against unrelated global JSON snippets on generic landing/search pages.
        json_available = None
    if json_available is True:
        available_flag = True
    elif json_available is False:
        unavailable_flag = True

    registration_price, currency = _extract_primary_price(plain_text)
    renewal_price = _extract_renewal_price(plain_text)

    if not domain_found and json_available is None:
        # No domain-specific marker means status signals from noisy global text are unreliable.
        return ParserResult(
            final_status=FinalStatus.PARSING_FAILED,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=premium_flag,
            promo=promo_flag,
            note="domain marker missing in response",
            confidence=0.15,
        )

    if transfer_flag and unavailable_flag:
        return ParserResult(
            final_status=FinalStatus.TRANSFER_ONLY,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=premium_flag,
            promo=promo_flag,
            note="transfer flow",
            confidence=0.85,
        )

    if transfer_flag and not available_flag:
        return ParserResult(
            final_status=FinalStatus.TRANSFER_ONLY,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=premium_flag,
            promo=promo_flag,
            note="transfer-only signal",
            confidence=0.75,
        )

    if available_flag and unavailable_flag:
        return ParserResult(
            final_status=FinalStatus.UNKNOWN,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=premium_flag,
            promo=promo_flag,
            note="conflicting available/unavailable signals",
            confidence=0.35,
        )

    if available_flag:
        final_status = FinalStatus.AVAILABLE
        if premium_flag:
            final_status = FinalStatus.PREMIUM
        elif promo_flag and registration_price:
            final_status = FinalStatus.DISCOUNTED
        elif registration_price:
            final_status = FinalStatus.STANDARD_PRICE
        return ParserResult(
            final_status=final_status,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=premium_flag,
            promo=promo_flag,
            note="available signal",
            confidence=0.82 if json_available is None else 0.92,
        )

    if unavailable_flag:
        return ParserResult(
            final_status=FinalStatus.UNAVAILABLE,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=premium_flag,
            promo=promo_flag,
            note="unavailable signal",
            confidence=0.82 if json_available is None else 0.92,
        )

    if premium_flag and registration_price:
        return ParserResult(
            final_status=FinalStatus.PREMIUM,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=True,
            promo=promo_flag,
            note="premium signal",
            confidence=0.65,
        )

    if registration_price and "register" in context_lower:
        return ParserResult(
            final_status=FinalStatus.STANDARD_PRICE,
            registration_price=registration_price,
            renewal_price=renewal_price,
            currency=currency,
            premium=False,
            promo=promo_flag,
            note="price-only signal",
            confidence=0.45,
        )

    return ParserResult(
        final_status=FinalStatus.PARSING_FAILED,
        registration_price=registration_price,
        renewal_price=renewal_price,
        currency=currency,
        premium=premium_flag,
        promo=promo_flag,
        note="could not determine status",
        confidence=0.2,
    )


def _to_plain_text(html_text: str) -> str:
    no_script = re.sub(r"<script[\\s\\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    no_style = re.sub(r"<style[\\s\\S]*?</style>", " ", no_script, flags=re.IGNORECASE)
    tags_removed = re.sub(r"<[^>]+>", " ", no_style)
    unescaped = html.unescape(tags_removed)
    compact = re.sub(r"\s+", " ", unescaped)
    return compact.strip()


def _domain_context(text: str, domain: str) -> tuple[str, bool]:
    if not domain:
        return text, False

    pattern = _compile_domain_pattern(domain)
    matches = list(pattern.finditer(text))
    if not matches:
        return text, False

    chunks: list[str] = []
    for match in matches[:3]:
        start = max(0, match.start() - 600)
        end = min(len(text), match.end() + 600)
        chunks.append(text[start:end])
    return " ".join(chunks), True


def _contains_any(markers: Iterable[str], text: str) -> bool:
    for marker in markers:
        if not marker:
            continue
        if _compile_marker_pattern(marker).search(text):
            return True
    return False


def _extract_json_availability(raw_html: str) -> bool | None:
    lower = raw_html.lower()
    true_patterns = (
        r'"isavailable"\s*:\s*true',
        r'"available"\s*:\s*true',
        r"'isavailable'\s*:\s*true",
    )
    false_patterns = (
        r'"isavailable"\s*:\s*false',
        r'"available"\s*:\s*false',
        r"'isavailable'\s*:\s*false",
    )

    if any(re.search(pattern, lower) for pattern in true_patterns):
        return True
    if any(re.search(pattern, lower) for pattern in false_patterns):
        return False
    return None


def _domain_in_raw_html(raw_html: str, domain_lower: str) -> bool:
    lower = raw_html.lower()
    if domain_lower in lower:
        return True
    encoded = quote_plus(domain_lower)
    if encoded and encoded in lower:
        return True
    url_escaped = domain_lower.replace(".", r"\u002e")
    if url_escaped in lower:
        return True
    return False


@lru_cache(maxsize=1024)
def _compile_marker_pattern(marker: str) -> re.Pattern:
    parts = [re.escape(part) for part in marker.strip().lower().split()]
    if not parts:
        return re.compile(r"$^")
    body = r"\s+".join(parts)
    return re.compile(rf"(?<![\w]){body}(?![\w])")


@lru_cache(maxsize=512)
def _compile_domain_pattern(domain: str) -> re.Pattern:
    escaped = re.escape(domain.strip().lower())
    escaped = escaped.replace(r"\.", r"\s*[.\u3002]\s*")
    escaped = escaped.replace(r"\-", r"\s*-\s*")
    return re.compile(escaped)


def _extract_primary_price(text: str) -> tuple[str | None, str | None]:
    match = _PRICE_RE.search(text)
    if not match:
        return None, None
    symbol = match.group(1)
    value = match.group(2).rstrip(".,")
    price = f"{symbol}{value}"
    return price, _symbol_to_currency(symbol)


def _extract_renewal_price(text: str) -> str | None:
    match = _RENEWAL_RE.search(text)
    if not match:
        return None
    return match.group(1).replace(" ", "")


def _symbol_to_currency(symbol: str) -> str | None:
    mapping = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "¥": "JPY",
        "₹": "INR",
    }
    return mapping.get(symbol)


def _merge_rules(base: KeywordRules, custom: KeywordRules | None) -> KeywordRules:
    if custom is None:
        return base

    return KeywordRules(
        available=tuple({*base.available, *custom.available}),
        unavailable=tuple({*base.unavailable, *custom.unavailable}),
        premium=tuple({*base.premium, *custom.premium}),
        promo=tuple({*base.promo, *custom.promo}),
        transfer_only=tuple({*base.transfer_only, *custom.transfer_only}),
        unsupported_tld=tuple({*base.unsupported_tld, *custom.unsupported_tld}),
        blocked=tuple({*base.blocked, *custom.blocked}),
        rate_limited=tuple({*base.rate_limited, *custom.rate_limited}),
        temporarily_unavailable=tuple({*base.temporarily_unavailable, *custom.temporarily_unavailable}),
    )
