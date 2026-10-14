"""Unit tests for the TokenBlacklist service."""

from __future__ import annotations

import time

from app.services.token_blacklist import TokenBlacklist


def test_blacklist_revocation_and_query():
    blacklist = TokenBlacklist()
    blacklist.reset_for_tests()

    jti = "test-token-id-12345"
    assert blacklist.is_revoked(jti) is False

    blacklist.revoke(jti, expires_in_seconds=60)
    assert blacklist.is_revoked(jti) is True


def test_blacklist_expires_old_entries():
    blacklist = TokenBlacklist()
    blacklist.reset_for_tests()

    jti = "short-lived-token"
    # Revoke with 1 second TTL
    blacklist.revoke(jti, expires_in_seconds=1)
    assert blacklist.is_revoked(jti) is True

    # Sleep past the TTL
    time.sleep(1.1)
    assert blacklist.is_revoked(jti) is False


def test_blacklist_ignores_non_positive_ttl():
    blacklist = TokenBlacklist()
    blacklist.reset_for_tests()

    jti = "zero-ttl-token"
    blacklist.revoke(jti, expires_in_seconds=0)
    assert blacklist.is_revoked(jti) is False

    blacklist.revoke(jti, expires_in_seconds=-5)
    assert blacklist.is_revoked(jti) is False
