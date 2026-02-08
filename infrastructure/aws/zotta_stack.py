"""AWS CDK Stack for Zotta Lending Application.

Provisions:
- VPC with public/private subnets
- RDS PostgreSQL (private subnet)
- ElastiCache Redis (private subnet)
- ECS Fargate for API + Celery worker
- S3 buckets for frontend + document storage
- CloudFront distribution
- Secrets Manager for sensitive config
- Application Load Balancer
"""

from constructs import Construct
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_rds as rds,
    aws_elasticache as elasticache,
    aws_s3 as s3,
    aws_s3_deployment as s3_deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_secretsmanager as secretsmanager,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
    CfnOutput,
)


class ZottaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── VPC ────────────────────────────────────────
        vpc = ec2.Vpc(
            self, "ZottaVPC",
            max_azs=2,
            nat_gateways=1,
        )

        # ── Secrets ────────────────────────────────────
        db_secret = secretsmanager.Secret(
            self, "ZottaDBSecret",
            description="Zotta RDS credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "zotta"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        app_secret = secretsmanager.Secret(
            self, "ZottaAppSecret",
            description="Zotta application secrets (JWT key, API keys)",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=64,
                exclude_punctuation=True,
            ),
        )

        # ── RDS PostgreSQL ─────────────────────────────
        db_sg = ec2.SecurityGroup(self, "DBSG", vpc=vpc, description="RDS Security Group")
        db_sg.add_ingress_rule(ec2.Peer.ipv4(vpc.vpc_cidr_block), ec2.Port.tcp(5432))

        database = rds.DatabaseInstance(
            self, "ZottaDB",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[db_sg],
            database_name="zotta",
            credentials=rds.Credentials.from_secret(db_secret),
            multi_az=False,
            allocated_storage=20,
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False,
        )

        # ── ElastiCache Redis ──────────────────────────
        redis_sg = ec2.SecurityGroup(self, "RedisSG", vpc=vpc, description="Redis Security Group")
        redis_sg.add_ingress_rule(ec2.Peer.ipv4(vpc.vpc_cidr_block), ec2.Port.tcp(6379))

        redis_subnet_group = elasticache.CfnSubnetGroup(
            self, "RedisSubnetGroup",
            description="Redis subnet group",
            subnet_ids=[s.subnet_id for s in vpc.private_subnets],
        )

        redis = elasticache.CfnCacheCluster(
            self, "ZottaRedis",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            vpc_security_group_ids=[redis_sg.security_group_id],
            cache_subnet_group_name=redis_subnet_group.ref,
        )

        # ── S3 Buckets ────────────────────────────────
        frontend_bucket = s3.Bucket(
            self, "FrontendBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        docs_bucket = s3.Bucket(
            self, "DocsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # ── ECS Cluster ───────────────────────────────
        cluster = ecs.Cluster(
            self, "ZottaCluster",
            vpc=vpc,
        )

        # ── API Service (Fargate) ──────────────────────
        api_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "ZottaAPI",
            cluster=cluster,
            cpu=256,
            memory_limit_mib=512,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset("../../backend", file="Dockerfile.prod"),
                container_port=8000,
                environment={
                    "ENVIRONMENT": "production",
                    "DEBUG": "false",
                    "CORS_ORIGINS": "*",
                    "CREDIT_BUREAU_PROVIDER": "mock",
                    "ID_VERIFICATION_PROVIDER": "mock",
                },
                secrets={
                    "SECRET_KEY": ecs.Secret.from_secrets_manager(app_secret),
                },
            ),
            public_load_balancer=True,
        )

        # Grant permissions
        db_secret.grant_read(api_service.task_definition.task_role)
        docs_bucket.grant_read_write(api_service.task_definition.task_role)

        # Health check
        api_service.target_group.configure_health_check(
            path="/api/health",
            healthy_http_codes="200",
        )

        # ── Celery Worker (Fargate) ────────────────────
        worker_task = ecs.FargateTaskDefinition(
            self, "WorkerTask",
            cpu=256,
            memory_limit_mib=512,
        )

        worker_task.add_container(
            "worker",
            image=ecs.ContainerImage.from_asset("../../backend", file="Dockerfile.prod"),
            command=["celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="zotta-worker"),
            environment={
                "ENVIRONMENT": "production",
            },
        )

        db_secret.grant_read(worker_task.task_role)

        ecs.FargateService(
            self, "WorkerService",
            cluster=cluster,
            task_definition=worker_task,
            desired_count=1,
        )

        # ── CloudFront ─────────────────────────────────
        distribution = cloudfront.Distribution(
            self, "ZottaCDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_identity(frontend_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.LoadBalancerV2Origin(
                        api_service.load_balancer,
                        protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
                    ),
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                ),
            },
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
        )

        # ── Outputs ────────────────────────────────────
        CfnOutput(self, "CloudFrontURL", value=f"https://{distribution.distribution_domain_name}")
        CfnOutput(self, "APIURL", value=f"http://{api_service.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "FrontendBucketName", value=frontend_bucket.bucket_name)
        CfnOutput(self, "DocsBucketName", value=docs_bucket.bucket_name)
