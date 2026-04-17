import pytest

from src.availability_parser import KeywordRules, parse_with_keyword_rules
from src.models import FinalStatus


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("example.com is available to register for $9.99", FinalStatus.STANDARD_PRICE),
        ("example.com is already registered", FinalStatus.UNAVAILABLE),
        ("premium domain example.com for $2,999", FinalStatus.PREMIUM),
        ("example.com is available first year discount $5.99", FinalStatus.DISCOUNTED),
        ("example.com transfer only", FinalStatus.TRANSFER_ONLY),
        ("unsupported tld for this search", FinalStatus.UNSUPPORTED_TLD),
        ("access denied captcha", FinalStatus.BLOCKED),
        ("Attention Required! Please enable JavaScript and cookies to continue", FinalStatus.BLOCKED),
        ("too many requests, rate limit", FinalStatus.RATE_LIMITED),
        ("service unavailable try again later", FinalStatus.TEMPORARILY_UNAVAILABLE),
        ("welcome to registrar", FinalStatus.PARSING_FAILED),
    ],
)
def test_parser_status_matrix(html, expected):
    result = parse_with_keyword_rules(html, "example.com")
    assert result.final_status == expected


def test_parser_json_true_signal_wins():
    html = '<script>{"domain":"example.com","isAvailable":true}</script>'
    result = parse_with_keyword_rules(html, "example.com")
    assert result.final_status in {FinalStatus.AVAILABLE, FinalStatus.STANDARD_PRICE}


def test_parser_conflicting_signals_unknown():
    html = "example.com is available but also says already registered"
    result = parse_with_keyword_rules(html, "example.com")
    assert result.final_status == FinalStatus.UNKNOWN


def test_parser_custom_rules_extend_default():
    rules = KeywordRules(available=("is free",), unavailable=("not free",))
    result = parse_with_keyword_rules("example.com is free", "example.com", rules)
    assert result.final_status in {FinalStatus.AVAILABLE, FinalStatus.STANDARD_PRICE}


def test_parser_extracts_renewal_price():
    html = "example.com is available for $8.99 now, renewal $14.99 yearly"
    result = parse_with_keyword_rules(html, "example.com")
    assert result.registration_price == "$8.99"
    assert result.renewal_price == "$14.99"


def test_parser_domain_missing_returns_parsing_failed():
    html = "Get your domain now! Premium domains from $0.99"
    result = parse_with_keyword_rules(html, "example.com")
    assert result.final_status == FinalStatus.PARSING_FAILED
    assert result.note == "domain marker missing in response"


def test_parser_domain_match_tolerates_spaced_dot_markup():
    html = "<h1>example </h1><span>.</span><h2> com is available to register for $9.99</h2>"
    result = parse_with_keyword_rules(html, "example.com")
    assert result.final_status == FinalStatus.STANDARD_PRICE


def test_parser_marker_boundary_avoids_available_inside_unavailable():
    rules = KeywordRules(available=("available",), unavailable=("unavailable",))
    result = parse_with_keyword_rules("example.com is unavailable", "example.com", rules)
    assert result.final_status == FinalStatus.UNAVAILABLE


def test_parser_ignores_json_availability_without_domain_context():
    html = '<script>{"isAvailable":true}</script><div>Find your perfect domain today</div>'
    result = parse_with_keyword_rules(html, "example.com")
    assert result.final_status == FinalStatus.PARSING_FAILED
