# Copyright (c) Microsoft. All rights reserved.
#
# STJP unified hosted agent group — the MAF-orchestrator design.
#
# Each case is hosted as ONE Foundry agent group: a Microsoft Agent Framework
# GroupChat whose ORCHESTRATOR holds the validated coordination protocol (it
# selects which participant speaks each round) and whose PARTICIPANTS each hold
# only their projected local contract. This is the hosted-surface twin of the
# maf_groupchat_llmvalid_orch benchmark arm.
#
# Prompts are pre-rendered (scribble-java projection runs at authoring time) and
# baked into group_spec.json, so this container needs no Java — only the JSON.
# Which case is served is chosen by STJP_GROUP_SPEC (path to the group_spec.json
# copied in at build time); the model is AZURE_AI_MODEL_DEPLOYMENT_NAME.

import json
import logging
import os
from pathlib import Path

from agent_framework import Agent, WorkflowAgent
from agent_framework.orchestrations import GroupChatBuilder
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def load_spec() -> dict:
    spec_path = Path(os.environ.get("STJP_GROUP_SPEC", "group_spec.json"))
    if not spec_path.exists():
        # fall back to the single spec copied next to this entrypoint
        spec_path = Path(__file__).parent / "group_spec.json"
    return json.loads(spec_path.read_text(encoding="utf-8"))


def build_group(spec: dict, client) -> WorkflowAgent:
    participants = [
        Agent(client, spec["participants"][role], name=role,
              description=f"{role} — projected local contract "
                          f"({spec['case_id']})")
        for role in spec["roles"]
    ]
    # Collision-proof name: a case may have a role literally named
    # "Orchestrator" (e.g. gem_dev_team), which would duplicate the executor ID.
    orch_name = "StjpProtocolOrchestrator"
    while orch_name in spec["roles"]:
        orch_name = "_" + orch_name
    orchestrator = Agent(
        client, spec["orchestrator_prompt"], name=orch_name,
        description=f"Protocol-holding speaker selector for {spec['case_id']}",
    )
    workflow = (
        GroupChatBuilder(
            participants=participants,
            orchestrator_agent=orchestrator,
        )
        .with_max_rounds(int(spec["max_rounds"]))
        .build()
    )
    return WorkflowAgent(
        workflow, name=spec["group_name"],
        description=f"STJP {spec['case_id']} hosted as one MAF group — "
                    f"orchestrator holds the validated protocol, each agent "
                    f"holds only its projected local contract.",
    )


def main():
    spec = load_spec()
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        credential=DefaultAzureCredential(),
    )
    group = build_group(spec, client)
    logger.info("hosting group %s (%d roles, model %s)",
                spec["group_name"], len(spec["roles"]),
                os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME"))
    ResponsesHostServer(group).run()


if __name__ == "__main__":
    main()
