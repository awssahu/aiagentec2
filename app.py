#!/usr/bin/env python3
import os
from aws_cdk import (
    App,
    Environment
)

from aikb.aikb_stack import AikbStack

print(os.getenv("AWS_REGION"))
app = App()
AikbStack(app, "BedrockAgentWithKinesisStack")
app.synth()

