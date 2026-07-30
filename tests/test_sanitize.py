from copy import deepcopy

import pytest

from pillars.sanitize import REDACTED_VALUE, is_sensitive_key, sanitize_after, sanitize_value


def test_sensitive_scalar_is_redacted():
    assert sanitize_value("super-secret-test-password", True) == REDACTED_VALUE
    assert sanitize_value("db.t3.medium", False) == "db.t3.medium"


def test_true_sensitivity_preserves_dict_and_list_structure():
    value = {
        "username": "appadmin",
        "credentials": {
            "password": "super-secret-test-password",
            "token": "test-api-token-value",
        },
        "items": ["safe-item", {"private_key": "fake-private-key-material"}],
        "empty_dict": {},
        "empty_list": [],
        "nothing": None,
    }

    assert sanitize_value(value, True) == {
        "username": REDACTED_VALUE,
        "credentials": {
            "password": REDACTED_VALUE,
            "token": REDACTED_VALUE,
        },
        "items": [REDACTED_VALUE, {"private_key": REDACTED_VALUE}],
        "empty_dict": {},
        "empty_list": [],
        "nothing": REDACTED_VALUE,
    }


def test_partial_sensitivity_preserves_safe_fields():
    value = {
        "username": "appadmin",
        "password": "super-secret-test-password",
        "settings": {
            "host": "db.internal",
            "token": "test-api-token-value",
        },
        "rules": [
            {"name": "safe-rule", "secret": "fake-private-key-material"},
            {"name": "another-safe-rule"},
        ],
    }
    sensitivity = {
        "password": True,
        "settings": {"token": True},
        "rules": [{"secret": True}],
    }

    assert sanitize_value(value, sensitivity) == {
        "username": "appadmin",
        "password": REDACTED_VALUE,
        "settings": {
            "host": "db.internal",
            "token": REDACTED_VALUE,
        },
        "rules": [
            {"name": "safe-rule", "secret": REDACTED_VALUE},
            {"name": "another-safe-rule"},
        ],
    }


def test_missing_malformed_and_incomplete_metadata_still_uses_key_fallback():
    value = {
        "password": "super-secret-test-password",
        "config": {
            "apiKey": "test-api-token-value",
            "name": "safe-name",
        },
        "items": [
            {"privatekey": "fake-private-key-material"},
            {"engine": "postgres"},
        ],
    }
    sensitivity = {
        "config": "not-a-sensitivity-tree",
        "items": [{"unknown": True}],
    }

    assert sanitize_value(value, sensitivity) == {
        "password": REDACTED_VALUE,
        "config": {
            "apiKey": REDACTED_VALUE,
            "name": "safe-name",
        },
        "items": [
            {"privatekey": REDACTED_VALUE},
            {"engine": "postgres"},
        ],
    }


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "api-key",
        "apiKey",
        "ApiKey",
        "apikey",
        "dbpassword",
        "accesstoken",
        "privatekey",
        "password",
        "passwd",
        "token",
        "clientSecret",
        "connectionString",
        "authorization",
        "user_data",
    ],
)
def test_sensitive_key_variants_are_detected(key):
    assert is_sensitive_key(key) is True
    assert sanitize_value({key: "super-secret-test-password"}) == {key: REDACTED_VALUE}


@pytest.mark.parametrize(
    "key",
    [
        "public_key",
        "public-key",
        "publicKey",
        "PublicKey",
        "key_name",
        "keyName",
        "secret_name",
        "secretName",
        "secret_id",
        "secretId",
        "secret_arn",
        "secretArn",
        "secret_version",
        "secretVersion",
    ],
)
def test_safe_identifier_keys_are_not_redacted(key):
    assert is_sensitive_key(key) is False
    assert sanitize_value({key: "safe-identifier"}) == {key: "safe-identifier"}


def test_sanitize_after_preserves_dict_or_none_shape():
    assert sanitize_after(None, True) is None
    assert sanitize_after({"username": "appadmin", "password": "super-secret-test-password"}, True) == {
        "username": REDACTED_VALUE,
        "password": REDACTED_VALUE,
    }
    assert sanitize_after("unexpected-top-level-scalar", True) is None


def test_sanitization_does_not_mutate_source_input():
    value = {
        "password": "super-secret-test-password",
        "nested": [{"token": "test-api-token-value", "safe": "ok"}],
    }
    original = deepcopy(value)

    result = sanitize_value(value)

    assert value == original
    assert value["password"] == "super-secret-test-password"
    assert value["nested"][0]["token"] == "test-api-token-value"
    assert result is not value
    assert result["nested"] is not value["nested"]
    assert result["nested"][0] is not value["nested"][0]
