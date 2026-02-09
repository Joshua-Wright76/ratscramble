from __future__ import annotations

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct


class RatScrambleSupportStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        s3.Bucket(
            self,
            "RatScrambleLogsArchive",
            versioned=False,
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        logs.LogGroup(
            self,
            "RatScrambleSimulationLogs",
            retention=logs.RetentionDays.ONE_MONTH,
        )

        iam.ManagedPolicy(
            self,
            "RatScrambleBedrockInvokePolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                    resources=["*"],
                )
            ],
            description="Policy scaffold for local principals to invoke Bedrock models.",
        )
