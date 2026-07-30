import json
from copy import deepcopy
from pathlib import Path

from pillars.terraform import extract_references, normalize

FIXTURE = Path(__file__).parent.parent / "examples" / "demo-infra" / "plan.json"
REDACTED_VALUE = "[REDACTED]"


def test_normalize_extracts_expected_resources():
    plan = json.loads(FIXTURE.read_text())
    resources = normalize(plan)

    addresses = {r.address for r in resources}
    assert addresses == {
        "aws_s3_bucket.data",
        "aws_s3_bucket_acl.data_acl",
        "aws_db_instance.main",
    }

    db = next(r for r in resources if r.address == "aws_db_instance.main")
    assert db.type == "aws_db_instance"
    assert db.provider == "aws"
    assert db.actions == ["create"]
    assert db.after["multi_az"] is False


def test_normalize_skips_no_op_and_read_actions():
    plan = {
        "resource_changes": [
            {
                "address": "aws_s3_bucket.untouched",
                "type": "aws_s3_bucket",
                "name": "untouched",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {"actions": ["no-op"], "after": {}},
            },
            {
                "address": "data.aws_ami.latest",
                "type": "aws_ami",
                "name": "latest",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {"actions": ["read"], "after": {}},
            },
            {
                "address": "aws_s3_bucket.new",
                "type": "aws_s3_bucket",
                "name": "new",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {"actions": ["create"], "after": {}},
            },
        ]
    }

    resources = normalize(plan)
    assert [r.address for r in resources] == ["aws_s3_bucket.new"]


_REFERENCE_PLAN = {
    "resource_changes": [
        {
            "address": "aws_s3_bucket.data",
            "type": "aws_s3_bucket",
            "name": "data",
            "provider_name": "registry.terraform.io/hashicorp/aws",
            "change": {"actions": ["create"], "after": {}},
        },
        {
            "address": "aws_cloudfront_distribution.cdn",
            "type": "aws_cloudfront_distribution",
            "name": "cdn",
            "provider_name": "registry.terraform.io/hashicorp/aws",
            "change": {"actions": ["create"], "after": {}},
        },
    ],
    "configuration": {
        "root_module": {
            "resources": [
                {"address": "aws_s3_bucket.data", "expressions": {}},
                {
                    "address": "aws_cloudfront_distribution.cdn",
                    "expressions": {
                        "origin": {
                            "domain_name": {
                                "references": [
                                    "aws_s3_bucket.data.bucket_regional_domain_name",
                                    "aws_s3_bucket.data",
                                ]
                            }
                        }
                    },
                },
            ]
        }
    },
}


def test_extract_references_maps_cross_resource_dependencies():
    refs = extract_references(_REFERENCE_PLAN)
    assert refs["aws_cloudfront_distribution.cdn"] == ["aws_s3_bucket.data"]
    assert refs["aws_s3_bucket.data"] == []


def test_normalize_attaches_references():
    resources = normalize(_REFERENCE_PLAN)
    cdn = next(r for r in resources if r.address == "aws_cloudfront_distribution.cdn")
    assert cdn.references == ["aws_s3_bucket.data"]


def test_normalize_redacts_top_level_sensitive_after_object_without_changing_shape():
    plan = {
        "resource_changes": [
            {
                "address": "aws_db_instance.main",
                "type": "aws_db_instance",
                "name": "main",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "identifier": "my-app-db",
                        "settings": {
                            "host": "db.internal",
                            "password": "super-secret-test-password",
                        },
                        "bootstrap": [
                            "test-api-token-value",
                            {"private_key": "fake-private-key-material"},
                        ],
                        "enabled": True,
                    },
                    "after_sensitive": True,
                },
            }
        ]
    }

    resources = normalize(plan)
    db = resources[0]

    assert isinstance(db.after, dict)
    assert db.after == {
        "identifier": REDACTED_VALUE,
        "settings": {
            "host": REDACTED_VALUE,
            "password": REDACTED_VALUE,
        },
        "bootstrap": [
            REDACTED_VALUE,
            {"private_key": REDACTED_VALUE},
        ],
        "enabled": REDACTED_VALUE,
    }


def test_normalize_applies_partial_after_sensitive_and_preserves_references():
    plan = {
        "resource_changes": [
            {
                "address": "aws_secretsmanager_secret_version.db",
                "type": "aws_secretsmanager_secret_version",
                "name": "db",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "secret_id": "aws_secretsmanager_secret.db.id",
                        "credentials": {
                            "username": "appadmin",
                            "password": "super-secret-test-password",
                        },
                        "replicas": [
                            {"region": "us-east-1", "token": "test-api-token-value"},
                            {"region": "us-west-2"},
                        ],
                    },
                    "after_sensitive": {
                        "credentials": {"password": True},
                        "replicas": [{"token": True}],
                    },
                },
            },
            {
                "address": "aws_secretsmanager_secret.db",
                "type": "aws_secretsmanager_secret",
                "name": "db",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {"actions": ["create"], "after": {"name": "db-secret"}},
            },
        ],
        "configuration": {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_secretsmanager_secret_version.db",
                        "expressions": {
                            "secret_id": {
                                "references": ["aws_secretsmanager_secret.db.id"]
                            }
                        },
                    },
                    {
                        "address": "aws_secretsmanager_secret.db",
                        "expressions": {},
                    },
                ]
            }
        },
    }

    resources = normalize(plan)
    version = next(
        r for r in resources if r.address == "aws_secretsmanager_secret_version.db"
    )

    assert version.references == ["aws_secretsmanager_secret.db"]
    assert version.after == {
        "secret_id": "aws_secretsmanager_secret.db.id",
        "credentials": {
            "username": "appadmin",
            "password": REDACTED_VALUE,
        },
        "replicas": [
            {"region": "us-east-1", "token": REDACTED_VALUE},
            {"region": "us-west-2"},
        ],
    }


def test_normalize_fallback_redacts_without_after_sensitive_and_does_not_mutate_input():
    plan = {
        "resource_changes": [
            {
                "address": "aws_db_instance.main",
                "type": "aws_db_instance",
                "name": "main",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "identifier": "my-app-db",
                        "password": "super-secret-test-password",
                        "apiKey": "test-api-token-value",
                        "public_key": "safe-public-key-reference",
                        "secret_name": "safe-secret-name",
                        "engine": "postgres",
                    },
                },
            }
        ]
    }
    original = deepcopy(plan)

    resources = normalize(plan)
    db = resources[0]
    payload = json.dumps([r.model_dump() for r in resources])

    assert plan == original
    assert db.after == {
        "identifier": "my-app-db",
        "password": REDACTED_VALUE,
        "apiKey": REDACTED_VALUE,
        "public_key": "safe-public-key-reference",
        "secret_name": "safe-secret-name",
        "engine": "postgres",
    }
    assert "super-secret-test-password" not in payload
    assert "test-api-token-value" not in payload
    assert "safe-public-key-reference" in payload
