"""Pure logic for turning a flat resource+reference list into a containment tree (VPC/Subnet)
and a curated set of edges (structural relationships suppressed, real ones kept and labeled).
No Graphviz/diagrams import here -- fully unit testable without rendering anything."""

from pillars.models import ResourceChange

_VPC_TYPES = {"aws_vpc", "AWS::EC2::VPC"}
_SUBNET_TYPES = {"aws_subnet", "AWS::EC2::Subnet"}
_SECURITY_GROUP_TYPES = {"aws_security_group", "AWS::EC2::SecurityGroup"}
# Resource types whose own presence definitionally implies a specific VPC -- safe to hop through
# when resolving a *third* resource's VPC (e.g. a Listener's VPC is its Load Balancer's VPC).
# Deliberately narrow: does NOT include compute/data types like RDS or Lambda, since referencing
# e.g. an RDS instance's ARN in an env var doesn't mean the referencing resource is network-
# located inside that RDS instance's VPC -- only real "networking carrier" types belong here.
_VPC_CARRIER_TYPES = _SECURITY_GROUP_TYPES | _SUBNET_TYPES | {
    "aws_route_table",
    "AWS::EC2::RouteTable",
    "aws_lb",
    "aws_alb",
    "aws_elb",
    "AWS::ElasticLoadBalancingV2::LoadBalancer",
    "AWS::ElasticLoadBalancing::LoadBalancer",
    "aws_lb_target_group",
    "AWS::ElasticLoadBalancingV2::TargetGroup",
}
_IAM_TYPES = {
    "aws_iam_role",
    "aws_iam_user",
    "aws_iam_policy",
    "aws_iam_instance_profile",
    "AWS::IAM::Role",
    "AWS::IAM::User",
    "AWS::IAM::Policy",
    "AWS::IAM::InstanceProfile",
}
_LOGGING_TYPES = {
    "aws_cloudwatch_log_group",
    "aws_cloudwatch_metric_alarm",
    "AWS::Logs::LogGroup",
    "AWS::CloudWatch::Alarm",
}
_SUBNET_GROUP_TYPES = {
    "aws_db_subnet_group",
    "aws_elasticache_subnet_group",
    "AWS::RDS::DBSubnetGroup",
    "AWS::ElastiCache::SubnetGroup",
}
# Reference targets that represent structural/configuration wiring rather than a real data-flow
# connection -- suppressed as arrows (VPC/Subnet become containment instead; the rest are simply
# dropped, per the "what NOT to show" list: IAM attachments, log/alarm wiring, subnet-group
# plumbing).
_STRUCTURAL_TARGET_TYPES = _VPC_TYPES | _SUBNET_TYPES | _IAM_TYPES | _LOGGING_TYPES | _SUBNET_GROUP_TYPES


def _type_index(resources: list[ResourceChange]) -> dict[str, str]:
    return {r.address: r.type for r in resources}


def resolve_vpc(resources: list[ResourceChange]) -> dict[str, str | None]:
    """Map each resource address to the VPC address it belongs to, resolved directly or by
    hopping through referenced "network carrier" resources (Security Group, Subnet, Route Table,
    Load Balancer, Target Group -- see _VPC_CARRIER_TYPES) until a VPC is found. None if no VPC
    is resolvable (a "global" resource -- S3, CloudFront, IAM, SNS/SQS, etc.)."""
    type_index = _type_index(resources)
    by_address = {r.address: r for r in resources}

    def find_vpc(resource: ResourceChange, seen: frozenset[str]) -> str | None:
        if resource.address in seen:
            return None
        seen = seen | {resource.address}
        for ref in resource.references:
            if type_index.get(ref) in _VPC_TYPES:
                return ref
        for ref in resource.references:
            ref_type = type_index.get(ref)
            if ref_type in _VPC_CARRIER_TYPES:
                ref_resource = by_address.get(ref)
                if ref_resource is not None:
                    found = find_vpc(ref_resource, seen)
                    if found is not None:
                        return found
        return None

    return {r.address: find_vpc(r, frozenset()) for r in resources}


def resolve_subnet(resources: list[ResourceChange]) -> dict[str, str | None]:
    """Map each resource address to the single Subnet address it belongs to, only when exactly
    one is referenced. Resources spanning multiple subnets (e.g. an ASG across 2 AZs) or none
    map to None and render at the VPC level instead -- a node can't cleanly sit inside two
    Graphviz cluster boxes at once."""
    type_index = _type_index(resources)
    result: dict[str, str | None] = {}
    for r in resources:
        subnet_refs = [ref for ref in r.references if type_index.get(ref) in _SUBNET_TYPES]
        result[r.address] = subnet_refs[0] if len(subnet_refs) == 1 else None
    return result


def is_structural_reference(source_type: str, target_type: str) -> bool:
    """True if a reference from source_type to target_type is configuration wiring that should
    be suppressed rather than drawn as an arrow. Security-Group-to-Security-Group is the
    explicit carve-out -- an ingress rule referencing another SG is a real allowed-traffic
    relationship, not membership."""
    if source_type in _SECURITY_GROUP_TYPES and target_type in _SECURITY_GROUP_TYPES:
        return False
    return target_type in _STRUCTURAL_TARGET_TYPES


def _value_references(value: object, address: str) -> bool:
    if isinstance(value, dict):
        if value.get("Ref") == address:
            return True
        get_att = value.get("Fn::GetAtt")
        if isinstance(get_att, list) and get_att and get_att[0] == address:
            return True
        return any(_value_references(v, address) for v in value.values())
    if isinstance(value, list):
        return any(_value_references(v, address) for v in value)
    return value == address


def _format_port_label(protocol: object, from_port: object, to_port: object) -> str | None:
    if protocol is None:
        return None
    proto = str(protocol).upper()
    if proto in ("-1", "ALL"):
        return "ALL"
    if from_port is None:
        return proto
    if to_port is not None and to_port != from_port:
        return f"{proto}:{from_port}-{to_port}"
    return f"{proto}:{from_port}"


def security_group_ingress_label(sg_resource: ResourceChange, target_address: str) -> str | None:
    """Best-effort port/protocol label for an SG-to-SG edge, scanning the security group's own
    ingress rules (CFN SecurityGroupIngress list / Terraform ingress blocks) for one whose
    source references target_address. Returns None -- edge still drawn, just unlabeled -- when
    nothing matches (common for Terraform, where cross-resource references in a plan's `after`
    are often blanked out as "known after apply")."""
    after = sg_resource.after or {}
    rules = after.get("SecurityGroupIngress")
    if not isinstance(rules, list):
        rules = after.get("ingress")
    if not isinstance(rules, list):
        return None

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        source = rule.get("SourceSecurityGroupId")
        if source is None:
            source = rule.get("security_groups")
        if source is not None and _value_references(source, target_address):
            protocol = rule.get("IpProtocol", rule.get("protocol"))
            from_port = rule.get("FromPort", rule.get("from_port"))
            to_port = rule.get("ToPort", rule.get("to_port"))
            return _format_port_label(protocol, from_port, to_port)
    return None
