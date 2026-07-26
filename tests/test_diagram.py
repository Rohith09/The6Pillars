import shutil

import pytest
from diagrams.aws.database import RDS
from diagrams.aws.general import General
from diagrams.aws.network import PrivateSubnet, PublicSubnet, RouteTable
from diagrams.aws.storage import S3

from pillars.diagram import _icon_for, build_architecture_diagram
from pillars.models import ResourceChange

_GRAPHVIZ_AVAILABLE = shutil.which("dot") is not None


def test_icon_for_known_terraform_type():
    assert _icon_for("aws_s3_bucket") is S3


def test_icon_for_known_cloudformation_type():
    assert _icon_for("AWS::RDS::DBInstance") is RDS


def test_icon_for_ec2_service_override():
    # AWS::EC2::* covers several unrelated resource kinds; SecurityGroup has no dedicated icon
    assert _icon_for("AWS::EC2::SecurityGroup") is General


def test_icon_for_unknown_type_falls_back_to_general():
    assert _icon_for("aws_some_brand_new_resource_type") is General
    assert _icon_for("AWS::SomeNewService::SomeResource") is General


def test_icon_for_route_table():
    assert _icon_for("aws_route_table") is RouteTable
    assert _icon_for("AWS::EC2::RouteTable") is RouteTable


def test_icon_for_subnet_uses_name_heuristic():
    assert _icon_for("aws_subnet", "PrivateSubnet1") is PrivateSubnet
    assert _icon_for("AWS::EC2::Subnet", "PrivateAppSubnet") is PrivateSubnet
    assert _icon_for("aws_subnet", "PublicSubnet1") is PublicSubnet
    # no naming hint at all -- defaults to public rather than failing to render
    assert _icon_for("aws_subnet", "Subnet1") is PublicSubnet


def test_build_architecture_diagram_empty_returns_none():
    assert build_architecture_diagram([]) is None


@pytest.mark.skipif(not _GRAPHVIZ_AVAILABLE, reason="Graphviz not installed")
def test_build_architecture_diagram_renders_png_with_references():
    resources = [
        ResourceChange(
            address="DataBucket",
            type="AWS::S3::Bucket",
            name="DataBucket",
            provider="aws",
            actions=["template"],
            references=[],
        ),
        ResourceChange(
            address="CDN",
            type="AWS::CloudFront::Distribution",
            name="CDN",
            provider="aws",
            actions=["template"],
            references=["DataBucket"],
        ),
    ]
    png = build_architecture_diagram(resources)
    assert png is not None
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
