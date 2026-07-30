from pillars.agents.runner import _resources_payload
from pillars.terraform import normalize

REDACTED_VALUE = "[REDACTED]"


def test_resources_payload_uses_redacted_normalized_terraform_values():
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
                        "engine": "postgres",
                        "password": "super-secret-test-password",
                        "apiKey": "test-api-token-value",
                        "public_key": "safe-public-key-reference",
                        "connection": {
                            "privatekey": "fake-private-key-material",
                            "host": "db.internal",
                        },
                    },
                    "after_sensitive": {
                        "connection": {"privatekey": True},
                    },
                },
            },
            {
                "address": "aws_security_group.db",
                "type": "aws_security_group",
                "name": "db",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {"actions": ["create"], "after": {"name": "db-sg"}},
            },
        ],
        "configuration": {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_db_instance.main",
                        "expressions": {
                            "vpc_security_group_ids": {
                                "references": ["aws_security_group.db.id"]
                            }
                        },
                    },
                    {
                        "address": "aws_security_group.db",
                        "expressions": {},
                    },
                ]
            }
        },
    }

    payload = _resources_payload(normalize(plan))

    assert REDACTED_VALUE in payload
    assert "super-secret-test-password" not in payload
    assert "test-api-token-value" not in payload
    assert "fake-private-key-material" not in payload
    assert "postgres" in payload
    assert "safe-public-key-reference" in payload
    assert "aws_security_group.db" in payload
