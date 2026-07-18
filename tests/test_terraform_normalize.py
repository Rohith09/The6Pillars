import json
from pathlib import Path

from pillars.terraform import normalize

FIXTURE = Path(__file__).parent.parent / "examples" / "demo-infra" / "plan.json"


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
