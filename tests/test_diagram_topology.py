from pillars.diagram_topology import (
    is_structural_reference,
    resolve_subnet,
    resolve_vpc,
    security_group_ingress_label,
)
from pillars.models import ResourceChange


def _rc(address, type_, references=None, after=None):
    return ResourceChange(
        address=address,
        type=type_,
        name=address,
        provider="aws",
        actions=["template"],
        references=references or [],
        after=after or {},
    )


def test_resolve_vpc_direct_reference():
    resources = [
        _rc("VPC", "AWS::EC2::VPC"),
        _rc("Instance", "AWS::EC2::Instance", references=["VPC"]),
    ]
    assert resolve_vpc(resources) == {"VPC": None, "Instance": "VPC"}


def test_resolve_vpc_one_hop_via_security_group():
    resources = [
        _rc("VPC", "AWS::EC2::VPC"),
        _rc("SG", "AWS::EC2::SecurityGroup", references=["VPC"]),
        _rc("Instance", "AWS::EC2::Instance", references=["SG"]),
    ]
    vpc = resolve_vpc(resources)
    assert vpc["Instance"] == "VPC"


def test_resolve_vpc_one_hop_via_subnet():
    resources = [
        _rc("VPC", "AWS::EC2::VPC"),
        _rc("Subnet1", "AWS::EC2::Subnet", references=["VPC"]),
        _rc("Instance", "AWS::EC2::Instance", references=["Subnet1"]),
    ]
    vpc = resolve_vpc(resources)
    assert vpc["Instance"] == "VPC"


def test_resolve_vpc_none_when_unresolvable():
    resources = [_rc("Bucket", "AWS::S3::Bucket")]
    assert resolve_vpc(resources) == {"Bucket": None}


def test_resolve_vpc_hops_through_load_balancer_and_route_table():
    resources = [
        _rc("VPC", "AWS::EC2::VPC"),
        _rc("ALBSecurityGroup", "AWS::EC2::SecurityGroup", references=["VPC"]),
        _rc(
            "ALB",
            "AWS::ElasticLoadBalancingV2::LoadBalancer",
            references=["ALBSecurityGroup"],
        ),
        _rc("Listener", "AWS::ElasticLoadBalancingV2::Listener", references=["ALB"]),
        _rc("RouteTable", "AWS::EC2::RouteTable", references=["VPC"]),
        _rc(
            "PublicRoute",
            "AWS::EC2::Route",
            references=["RouteTable", "InternetGateway"],
        ),
    ]
    vpc = resolve_vpc(resources)
    assert vpc["Listener"] == "VPC"
    assert vpc["PublicRoute"] == "VPC"


def test_resolve_vpc_does_not_false_positive_through_data_references():
    # A Lambda referencing an RDS instance's identifier (e.g. in an env var) is not network-
    # located inside that RDS instance's VPC -- only "network carrier" types should count.
    resources = [
        _rc("VPC", "AWS::EC2::VPC"),
        _rc("DatabaseSecurityGroup", "AWS::EC2::SecurityGroup", references=["VPC"]),
        _rc("RDSDatabase", "AWS::RDS::DBInstance", references=["DatabaseSecurityGroup"]),
        _rc("SomeFunction", "AWS::Lambda::Function", references=["RDSDatabase"]),
    ]
    vpc = resolve_vpc(resources)
    assert vpc["RDSDatabase"] == "VPC"
    assert vpc["SomeFunction"] is None


def test_resolve_subnet_single_reference():
    resources = [
        _rc("Subnet1", "AWS::EC2::Subnet"),
        _rc("Instance", "AWS::EC2::Instance", references=["Subnet1"]),
    ]
    assert resolve_subnet(resources)["Instance"] == "Subnet1"


def test_resolve_subnet_multiple_references_is_none():
    resources = [
        _rc("Subnet1", "AWS::EC2::Subnet"),
        _rc("Subnet2", "AWS::EC2::Subnet"),
        _rc("ASG", "AWS::AutoScaling::AutoScalingGroup", references=["Subnet1", "Subnet2"]),
    ]
    assert resolve_subnet(resources)["ASG"] is None


def test_resolve_subnet_no_reference_is_none():
    resources = [_rc("Bucket", "AWS::S3::Bucket")]
    assert resolve_subnet(resources)["Bucket"] is None


def test_is_structural_reference_suppresses_vpc_subnet_iam_logs():
    assert is_structural_reference("AWS::EC2::Instance", "AWS::EC2::VPC") is True
    assert is_structural_reference("AWS::EC2::Instance", "AWS::EC2::Subnet") is True
    assert is_structural_reference("AWS::Lambda::Function", "AWS::IAM::Role") is True
    assert is_structural_reference("AWS::EC2::Instance", "AWS::Logs::LogGroup") is True
    assert is_structural_reference("AWS::RDS::DBInstance", "AWS::RDS::DBSubnetGroup") is True


def test_is_structural_reference_keeps_plain_resource_references():
    assert is_structural_reference("AWS::Lambda::Function", "AWS::SQS::Queue") is False


def test_is_structural_reference_security_group_to_security_group_is_kept():
    assert (
        is_structural_reference("AWS::EC2::SecurityGroup", "AWS::EC2::SecurityGroup") is False
    )


def test_security_group_ingress_label_cloudformation():
    sg = _rc(
        "AppSecurityGroup",
        "AWS::EC2::SecurityGroup",
        after={
            "SecurityGroupIngress": [
                {
                    "IpProtocol": "tcp",
                    "FromPort": 8080,
                    "ToPort": 8080,
                    "SourceSecurityGroupId": {"Ref": "ALBSecurityGroup"},
                }
            ]
        },
    )
    assert security_group_ingress_label(sg, "ALBSecurityGroup") == "TCP:8080"


def test_security_group_ingress_label_terraform():
    sg = _rc(
        "app_sg",
        "aws_security_group",
        after={
            "ingress": [
                {
                    "protocol": "tcp",
                    "from_port": 5432,
                    "to_port": 5432,
                    "security_groups": ["app_sg_id"],
                }
            ]
        },
    )
    assert security_group_ingress_label(sg, "app_sg_id") == "TCP:5432"


def test_security_group_ingress_label_returns_none_when_no_match():
    sg = _rc("AppSecurityGroup", "AWS::EC2::SecurityGroup", after={"SecurityGroupIngress": []})
    assert security_group_ingress_label(sg, "SomeOtherSG") is None
