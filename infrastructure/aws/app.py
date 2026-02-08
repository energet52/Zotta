#!/usr/bin/env python3
"""AWS CDK entry point for Zotta infrastructure."""

import aws_cdk as cdk
from zotta_stack import ZottaStack

app = cdk.App()

ZottaStack(
    app,
    "ZottaStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

app.synth()
