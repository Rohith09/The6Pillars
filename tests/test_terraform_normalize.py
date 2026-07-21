import json
from pathlib import Path

from pillars.terraform import extract_references, normalize

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
