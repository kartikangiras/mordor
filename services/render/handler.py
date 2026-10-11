"""Render step for Step Functions (M4). Day 1 renders inside forecast.publish; this entry point
exists so the state machine can split advect and render across two Lambdas later."""
from __future__ import annotations


def handler(event, context):
    raise NotImplementedError("wired in M4 - see forecast.publish.write_run")
