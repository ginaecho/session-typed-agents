# Copyright (c) Microsoft. All rights reserved.
#
# STJP grouped hosted agents — code_execution role group (validated protocol).
# Order: SubmitCode -> Approve -> ResultReturned. Code runs ONLY after the
# Reviewer approves it (no execute-before-review).

import logging
import os

from agent_framework import Agent, WorkflowAgent, WorkflowBuilder
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

CODER = (
    "You are the Coder. Do NOT ask questions — INVENT a small concrete task and "
    "write a short snippet for it. Submit the code to the Reviewer (never straight "
    "to the Executor). Output exactly one line:\n"
    "  SubmitCode: <lang> — <one-line code>\nThen stop."
)
REVIEWER = (
    "You are the Reviewer. You just received SubmitCode. Inspect it for safety and "
    "correctness and, if fine, approve it for execution (only you may approve). Do "
    "NOT ask questions. Output exactly one line:\n"
    "  Approve: code reviewed, safe to run\nThen stop."
)
EXECUTOR = (
    "You are the Executor. You just received Approve from the Reviewer, so you may "
    "run the code now (never before approval). Do NOT ask questions. Output exactly "
    "one line:\n  ResultReturned: <output>\nThen stop."
)


def main():
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        credential=DefaultAzureCredential(),
    )
    coder = Agent(client, CODER, name="Coder",
                  description="Writes and submits code to the Reviewer")
    reviewer = Agent(client, REVIEWER, name="Reviewer",
                     description="Approves before execution")
    executor = Agent(client, EXECUTOR, name="Executor",
                     description="Runs the code only after approval")

    workflow = (
        WorkflowBuilder(start_executor=coder, name="stjp-code-execution",
                        description="STJP code-execution role group (validated)")
        .add_chain([coder, reviewer, executor])
        .build()
    )
    group = WorkflowAgent(
        workflow, name="stjp-code-execution-group",
        description="STJP code_execution hosted as one grouped workflow "
                    "(Coder + Reviewer + Executor), review-before-execute.",
    )
    ResponsesHostServer(group).run()


if __name__ == "__main__":
    main()
