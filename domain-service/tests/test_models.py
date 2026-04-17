import pytest

from src.models import FinalStatus, final_status_to_legacy


@pytest.mark.parametrize(
    ("final_status", "premium_flag", "expected"),
    [
        (FinalStatus.AVAILABLE, False, "available"),
        (FinalStatus.STANDARD_PRICE, False, "available"),
        (FinalStatus.DISCOUNTED, False, "available"),
        (FinalStatus.PREMIUM, False, "premium"),
        (FinalStatus.UNAVAILABLE, False, "taken"),
        (FinalStatus.TRANSFER_ONLY, False, "taken"),
        (FinalStatus.UNSUPPORTED_TLD, False, "unknown"),
        (FinalStatus.BLOCKED, False, "unknown"),
        (FinalStatus.UNKNOWN, False, "unknown"),
        (FinalStatus.AVAILABLE, True, "premium"),
    ],
)
def test_final_status_to_legacy(final_status, premium_flag, expected):
    assert final_status_to_legacy(final_status, premium_flag) == expected
