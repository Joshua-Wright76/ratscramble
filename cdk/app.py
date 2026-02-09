#!/usr/bin/env python3
from aws_cdk import App, Environment

from ratscramble_stack import RatScrambleSupportStack

app = App()

RatScrambleSupportStack(
    app,
    "RatScrambleSupportStack",
    env=Environment(region="us-west-2"),
)

app.synth()
