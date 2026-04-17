from pathlib import Path

import pytest

from src.availability_parser import parse_with_keyword_rules
from src.models import FinalStatus


FIXTURES = Path(__file__).parent / "fixtures" / "registrars"


@pytest.mark.parametrize(
    ("fixture_name", "expected_status"),
    [
        ("namecheap_available.html", FinalStatus.STANDARD_PRICE),
        ("namecheap_taken.html", FinalStatus.UNAVAILABLE),
        ("generic_discounted.html", FinalStatus.DISCOUNTED),
        ("generic_transfer_only.html", FinalStatus.TRANSFER_ONLY),
        ("generic_blocked.html", FinalStatus.BLOCKED),
        ("generic_unsupported_tld.html", FinalStatus.UNSUPPORTED_TLD),
        ("generic_ambiguous.html", FinalStatus.UNKNOWN),
    ],
)
def test_parser_on_html_fixtures(fixture_name, expected_status):
    html = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    parsed = parse_with_keyword_rules(html, "example.com")
    assert parsed.final_status == expected_status
