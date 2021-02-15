#!/usr/bin/env python3

from aws_cdk import core

from sqs_stack.sqs_stack_stack import SqsStackStack


app = core.App()
_env = 'ap-northeast-2'
core_env = core.Environment(region=_env)
SqsStackStack(app, "sqs-stack", env=core_env)

app.synth()
