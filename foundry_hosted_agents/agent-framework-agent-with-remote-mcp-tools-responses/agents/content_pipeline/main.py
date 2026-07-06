# Copyright (c) Microsoft. All rights reserved.
#
# STJP grouped hosted agents — content_pipeline role group (validated protocol).
# Order: ResearchBrief -> SubmitDraft -> Approve -> Published. Nothing is
# published before the Editor approves it (no publish-before-review).

import logging
import os

from agent_framework import Agent, WorkflowAgent, WorkflowBuilder
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

RESEARCHER = (
    "You are the Researcher. Do NOT ask questions — INVENT a concrete topic and "
    "3 key points. Output exactly one line:\n"
    "  ResearchBrief: <topic> | points: <p1>; <p2>; <p3>\nThen stop."
)
WRITER = (
    "You are the Writer. You just received a ResearchBrief. Write a short article "
    "and submit it to the Editor (never straight to publishing). Do NOT ask "
    "questions. Output exactly one line:\n"
    "  SubmitDraft: \"<title>\" — <one-sentence summary>\nThen stop."
)
EDITOR = (
    "You are the Editor. You just received SubmitDraft. Review it and, if fine, "
    "approve it for publication (only the Editor may approve). Do NOT ask "
    "questions. Output exactly one line:\n"
    "  Approve: \"<title>\" approved for publication\nThen stop."
)
PUBLISHER = (
    "You are the Publisher. You just received Approve from the Editor, so you may "
    "publish now (never before approval). Do NOT ask questions. Output exactly one "
    "line:\n  Published: \"<title>\" is live at <url>\nThen stop."
)


def main():
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        credential=DefaultAzureCredential(),
    )
    researcher = Agent(client, RESEARCHER, name="Researcher",
                       description="Briefs the Writer")
    writer = Agent(client, WRITER, name="Writer",
                   description="Drafts and submits to the Editor")
    editor = Agent(client, EDITOR, name="Editor",
                   description="Approves before publication")
    publisher = Agent(client, PUBLISHER, name="Publisher",
                      description="Publishes only after approval")

    workflow = (
        WorkflowBuilder(start_executor=researcher, name="stjp-content-pipeline",
                        description="STJP content-pipeline role group (validated)")
        .add_chain([researcher, writer, editor, publisher])
        .build()
    )
    group = WorkflowAgent(
        workflow, name="stjp-content-pipeline-group",
        description="STJP content_pipeline hosted as one grouped workflow "
                    "(Researcher + Writer + Editor + Publisher), review-before-publish.",
    )
    ResponsesHostServer(group).run()


if __name__ == "__main__":
    main()
