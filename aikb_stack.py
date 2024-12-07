from aws_cdk import (
    App,
    Stack,
    aws_kinesis as kinesis,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda_event_sources as event_sources,
    RemovalPolicy,
    Duration,
    aws_s3_deployment as s3_deployment,
    aws_ec2 as ec2,
)
from constructs import Construct


class AikbStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create the VPC with a specific CIDR block
        vpc = ec2.Vpc(self, "MyVPC",
            cidr="192.168.21.0/24",  # VPC CIDR block
            max_azs=2,  # Use 2 Availability Zones
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet1",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=26  # This will split the VPC into multiple subnets, each with a /26 range
                ),
                ec2.SubnetConfiguration(
                    name="PublicSubnet2",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=26
                )
            ]
        )
        

        # Use the latest Amazon Linux 2023 AMI
        al2023_ami = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2023,
        )

        # Create a security group
        security_group = ec2.SecurityGroup(
            self, "MySecurityGroup",
            vpc=vpc,  # Attach the security group to an existing VPC
            security_group_name="MyCustomSG",  # Optional: Name the security group
            description="Security group for my EC2 instance",  # Optional description
            allow_all_outbound=True,  # Allow all outbound traffic (default is True)
        )

        # Add inbound rule to allow SSH from anywhere (port 22)
        security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),  # Allow connections from any IPv4 address
            ec2.Port.tcp(22),      # Allow SSH traffic (port 22)
            "Allow SSH access from anywhere",
        )

        # Add inbound rule to allow HTTP traffic (port 80)
        security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "Allow HTTP access from anywhere"
        )

        # Create an EC2 instance
        instance = ec2.Instance(
            self, "MyEC2Instance",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=al2023_ami,
            vpc=vpc,
            security_group=security_group,
        )

        # Create a Kinesis Data Stream
        kinesis_stream = kinesis.Stream(
            self,
            "LogStream",
            stream_name="LogDataStream",
            shard_count=1,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create an S3 bucket for the knowledge base
        knowledge_base_bucket = s3.Bucket(
            self,
            "Knowledge-Base-Home-Practice-Bucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Lambda function to process Kinesis stream data
        ai_agent_lambda = _lambda.Function(
            self,
            "AI-Agent-Lambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.handler",
            code=_lambda.Code.from_asset("lambda_ai"),
            timeout=Duration.seconds(120),
            environment={
                "BEDROCK_MODEL_ID": "anthropic.claude-v2",
                "KNOWLEDGE_BASE_BUCKET": knowledge_base_bucket.bucket_name,
                "INSTANCE_ID": instance.instance_id,
            },
        )

        # Add Kinesis event source to Lambda
        ai_agent_lambda.add_event_source(
            event_sources.KinesisEventSource(
                kinesis_stream,
                starting_position=_lambda.StartingPosition.LATEST,
                batch_size=100,
            )
        )

        # Grant permissions to Lambda for Kinesis, S3, Bedrock, and EC2
        kinesis_stream.grant_read(ai_agent_lambda)
        knowledge_base_bucket.grant_read(ai_agent_lambda)
        ai_agent_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["*"],  # Restrict to specific model ARN in production
            )
        )
        ai_agent_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ec2:RebootInstances", "ec2:TerminateInstances"],
                resources=["*"],  # Restrict to specific EC2 instance ARNs
            )
        )

        # Lambda function to process Kinesis stream data
        kinesis_log_lambda = _lambda.Function(
            self,
            "Kinesis-Message-Lambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.handler",
            code=_lambda.Code.from_asset("lambda_kinesis"),
            timeout=Duration.seconds(120),
        )
        kinesis_log_lambda.role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("AmazonKinesisFullAccess"))

        # Deploy local files to the bucket
        s3_deployment.BucketDeployment(
            self, "DeployFiles",
            sources=[s3_deployment.Source.asset("config")],
            destination_bucket=knowledge_base_bucket
        )