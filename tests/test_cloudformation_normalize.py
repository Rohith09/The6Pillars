from pathlib import Path

from pillars.cloudformation import normalize, parse_template

FIXTURE = Path(__file__).parent.parent / "examples" / "demo-infra-cfn" / "template.yaml"


def test_normalize_extracts_expected_resources():
    template = parse_template(FIXTURE)
    resources = normalize(template)

    addresses = {r.address for r in resources}
    assert addresses == {"DataBucket", "MainDatabase"}

    db = next(r for r in resources if r.address == "MainDatabase")
    assert db.type == "AWS::RDS::DBInstance"
    assert db.provider == "aws"
    assert db.actions == ["template"]
    assert db.after["MultiAZ"] is False

    bucket = next(r for r in resources if r.address == "DataBucket")
    assert bucket.type == "AWS::S3::Bucket"
    assert bucket.after["AccessControl"] == "PublicRead"


def test_normalize_resolves_yaml_intrinsic_functions():
    template = {
        "Resources": {
            "Bucket": {
                "Type": "AWS::S3::Bucket",
                "Properties": {"BucketName": {"Fn::Sub": "my-${AWS::AccountId}-bucket"}},
            }
        }
    }
    resources = normalize(template)
    assert resources[0].after["BucketName"] == {"Fn::Sub": "my-${AWS::AccountId}-bucket"}


def test_normalize_handles_missing_resources_key():
    assert normalize({}) == []
