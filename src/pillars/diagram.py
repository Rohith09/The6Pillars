import tempfile
from pathlib import Path

from diagrams import Diagram
from diagrams.aws.compute import EC2, ECS, EKS, AutoScaling, Fargate, Lambda
from diagrams.aws.database import RDS, Aurora, Dynamodb, ElastiCache, Redshift
from diagrams.aws.general import General
from diagrams.aws.integration import SNS, SQS
from diagrams.aws.management import CloudwatchAlarm, CloudwatchLogs
from diagrams.aws.network import (
    ALB,
    ELB,
    VPC,
    APIGateway,
    CloudFront,
    InternetGateway,
    NATGateway,
    PublicSubnet,
    PrivateSubnet,
    Route53,
    RouteTable,
)
from diagrams.aws.security import KMS, IAM, Cognito, SecretsManager, WAF
from diagrams.aws.storage import S3
from graphviz.backend.execute import ExecutableNotFound

from pillars.models import ResourceChange

# Exact resource-type-string -> icon class. Both Terraform and CloudFormation forms are exact
# strings, so they coexist in one dict without collisions. Anything not listed here falls back
# to General rather than failing to render.
_ICON_MAP: dict[str, type] = {
    # Terraform
    "aws_s3_bucket": S3,
    "aws_db_instance": RDS,
    "aws_rds_cluster": Aurora,
    "aws_dynamodb_table": Dynamodb,
    "aws_elasticache_cluster": ElastiCache,
    "aws_redshift_cluster": Redshift,
    "aws_instance": EC2,
    "aws_lambda_function": Lambda,
    "aws_ecs_service": ECS,
    "aws_ecs_cluster": ECS,
    "aws_eks_cluster": EKS,
    "aws_autoscaling_group": AutoScaling,
    "aws_fargate_service": Fargate,
    "aws_cloudfront_distribution": CloudFront,
    "aws_lb": ALB,
    "aws_alb": ALB,
    "aws_elb": ELB,
    "aws_vpc": VPC,
    "aws_api_gateway_rest_api": APIGateway,
    "aws_apigatewayv2_api": APIGateway,
    "aws_route53_zone": Route53,
    "aws_route53_record": Route53,
    "aws_internet_gateway": InternetGateway,
    "aws_nat_gateway": NATGateway,
    "aws_iam_role": IAM,
    "aws_iam_user": IAM,
    "aws_iam_policy": IAM,
    "aws_kms_key": KMS,
    "aws_secretsmanager_secret": SecretsManager,
    "aws_cognito_user_pool": Cognito,
    "aws_wafv2_web_acl": WAF,
    "aws_sqs_queue": SQS,
    "aws_sns_topic": SNS,
    "aws_route_table": RouteTable,
    "aws_launch_template": EC2,
    "aws_lb_target_group": ALB,
    "aws_lb_listener": ALB,
    "aws_iam_instance_profile": IAM,
    "aws_db_subnet_group": RDS,
    "aws_elasticache_subnet_group": ElastiCache,
    "aws_cloudwatch_log_group": CloudwatchLogs,
    "aws_cloudwatch_metric_alarm": CloudwatchAlarm,
    "aws_autoscaling_policy": AutoScaling,
    "aws_sqs_queue_policy": SQS,
    "aws_sns_topic_subscription": SNS,
    "aws_lambda_event_source_mapping": Lambda,
    # CloudFormation
    "AWS::S3::Bucket": S3,
    "AWS::RDS::DBInstance": RDS,
    "AWS::RDS::DBCluster": Aurora,
    "AWS::DynamoDB::Table": Dynamodb,
    "AWS::ElastiCache::CacheCluster": ElastiCache,
    "AWS::Redshift::Cluster": Redshift,
    "AWS::EC2::Instance": EC2,
    "AWS::Lambda::Function": Lambda,
    "AWS::ECS::Service": ECS,
    "AWS::ECS::Cluster": ECS,
    "AWS::EKS::Cluster": EKS,
    "AWS::AutoScaling::AutoScalingGroup": AutoScaling,
    "AWS::CloudFront::Distribution": CloudFront,
    "AWS::ElasticLoadBalancingV2::LoadBalancer": ALB,
    "AWS::ElasticLoadBalancing::LoadBalancer": ELB,
    "AWS::EC2::VPC": VPC,
    "AWS::EC2::SecurityGroup": General,
    "AWS::EC2::InternetGateway": InternetGateway,
    "AWS::EC2::NatGateway": NATGateway,
    "AWS::ApiGateway::RestApi": APIGateway,
    "AWS::ApiGatewayV2::Api": APIGateway,
    "AWS::Route53::HostedZone": Route53,
    "AWS::Route53::RecordSet": Route53,
    "AWS::IAM::Role": IAM,
    "AWS::IAM::User": IAM,
    "AWS::IAM::Policy": IAM,
    "AWS::KMS::Key": KMS,
    "AWS::SecretsManager::Secret": SecretsManager,
    "AWS::Cognito::UserPool": Cognito,
    "AWS::WAFv2::WebACL": WAF,
    "AWS::SQS::Queue": SQS,
    "AWS::SNS::Topic": SNS,
    "AWS::EC2::RouteTable": RouteTable,
    "AWS::EC2::LaunchTemplate": EC2,
    "AWS::ElasticLoadBalancingV2::TargetGroup": ALB,
    "AWS::ElasticLoadBalancingV2::Listener": ALB,
    "AWS::IAM::InstanceProfile": IAM,
    "AWS::RDS::DBSubnetGroup": RDS,
    "AWS::ElastiCache::SubnetGroup": ElastiCache,
    "AWS::Logs::LogGroup": CloudwatchLogs,
    "AWS::CloudWatch::Alarm": CloudwatchAlarm,
    "AWS::AutoScaling::ScalingPolicy": AutoScaling,
    "AWS::SQS::QueuePolicy": SQS,
    "AWS::SNS::Subscription": SNS,
    "AWS::Lambda::EventSourceMapping": Lambda,
}

# Subnets don't distinguish public/private at the type level -- fall back to a naming heuristic
# on the resource's own name/address, since "Public"/"Private" in the name is a common and
# reliable convention (as seen in real templates), then default to PublicSubnet.
_SUBNET_TYPES = {"aws_subnet", "AWS::EC2::Subnet"}


def _icon_for(resource_type: str, resource_name: str = "") -> type:
    if resource_type in _SUBNET_TYPES:
        name_lower = resource_name.lower()
        if "private" in name_lower:
            return PrivateSubnet
        return PublicSubnet
    return _ICON_MAP.get(resource_type, General)


def build_architecture_diagram(resources: list[ResourceChange]) -> bytes | None:
    """Render an AWS-icon architecture diagram from the resource list, using the cross-resource
    `references` already extracted for each ResourceChange. Returns PNG bytes, or None if there's
    nothing to draw, Graphviz isn't installed, or rendering fails for any other reason -- a
    diagram problem should never break the review itself."""
    if not resources:
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            out_base = str(Path(tmp) / "architecture")
            with Diagram(
                name="",
                filename=out_base,
                outformat="png",
                show=False,
            ):
                nodes = {rc.address: _icon_for(rc.type, rc.address)(rc.address) for rc in resources}
                for rc in resources:
                    for ref in rc.references:
                        if ref in nodes:
                            nodes[rc.address] >> nodes[ref]

            return (Path(tmp) / "architecture.png").read_bytes()
    except ExecutableNotFound:
        raise
    except Exception:
        return None
