from pathlib import Path

from pillars.cloudformation import normalize, parse_template

FIXTURE = Path(__file__).parent.parent / "examples" / "demo-infra-cfn" / "template.yaml"


def test_normalize_extracts_expected_resources():
    template = parse_template(FIXTURE)
    resources = normalize(template)

    addresses = {r.address for r in resources}
    assert addresses == {"DataBucket", "MainDatabase", "CDN"}

    db = next(r for r in resources if r.address == "MainDatabase")
    assert db.type == "AWS::RDS::DBInstance"
    assert db.provider == "aws"
    assert db.actions == ["template"]
    assert db.after["MultiAZ"] is False

    bucket = next(r for r in resources if r.address == "DataBucket")
    assert bucket.type == "AWS::S3::Bucket"
    assert bucket.after["AccessControl"] == "PublicRead"

    cdn = next(r for r in resources if r.address == "CDN")
    assert cdn.type == "AWS::CloudFront::Distribution"
    assert cdn.references == ["DataBucket"]


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


def test_normalize_extracts_references_from_ref_getatt_and_sub():
    template = {
        "Resources": {
            "Bucket": {"Type": "AWS::S3::Bucket", "Properties": {}},
            "Distribution": {
                "Type": "AWS::CloudFront::Distribution",
                "Properties": {
                    "Origin": {"Ref": "Bucket"},
                    "Comment": {"Fn::Sub": "CDN for ${Bucket.Arn}, region ${AWS::Region}"},
                    "OriginAccessIdentity": {"Fn::GetAtt": ["Bucket", "Arn"]},
                },
            },
        }
    }
    resources = normalize(template)
    distribution = next(r for r in resources if r.address == "Distribution")
    assert distribution.references == ["Bucket"]

    bucket = next(r for r in resources if r.address == "Bucket")
    assert bucket.references == []
