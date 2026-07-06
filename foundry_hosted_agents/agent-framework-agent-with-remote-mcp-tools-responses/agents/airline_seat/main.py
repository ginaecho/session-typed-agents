# Copyright (c) Microsoft. All rights reserved.
#
# STJP grouped hosted agents — airline_seat role group (validated protocol).
# Order: AssignFlight (Triage) -> UpdateSeat (SeatBooking) -> SeatConfirmed
# (FlightSystem). A seat is only changed AFTER a flight has been assigned.

import logging
import os

from agent_framework import Agent, WorkflowAgent, WorkflowBuilder
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

TRIAGE = (
    "You are the airline Triage agent. A customer wants to change their seat. Do "
    "NOT ask questions — INVENT reasonable details (confirmation number, and a "
    "flight number). Assign the flight to this booking FIRST. Output exactly one "
    "line:\n  AssignFlight: <flight-no> for booking <confirmation-no>\nThen stop."
)
SEAT = (
    "You are the Seat Booking agent. You just received AssignFlight from Triage, "
    "so a flight is now assigned. Apply the seat change (never before a flight is "
    "assigned). Carry the same flight/booking forward and pick a concrete seat. "
    "Do NOT ask questions. Output exactly one line:\n"
    "  UpdateSeat: seat <seat> on <flight-no> for booking <confirmation-no>\nThen stop."
)
FLIGHT = (
    "You are the Flight System of record. You just received UpdateSeat. Apply it "
    "and confirm. Do NOT ask questions. Output exactly one line:\n"
    "  SeatConfirmed: seat <seat> confirmed on <flight-no>\nThen stop."
)


def main():
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        credential=DefaultAzureCredential(),
    )
    triage = Agent(client, TRIAGE, name="Triage",
                   description="Assigns the flight to the booking first")
    seat = Agent(client, SEAT, name="SeatBooking",
                 description="Applies the seat change after a flight is assigned")
    flight = Agent(client, FLIGHT, name="FlightSystem",
                   description="Confirms the seat change")

    workflow = (
        WorkflowBuilder(start_executor=triage, name="stjp-airline-seat",
                        description="STJP airline-seat role group (validated)")
        .add_chain([triage, seat, flight])
        .build()
    )
    group = WorkflowAgent(
        workflow, name="stjp-airline-seat-group",
        description="STJP airline_seat hosted as one grouped workflow "
                    "(Triage + SeatBooking + FlightSystem), flight-assigned-first.",
    )
    ResponsesHostServer(group).run()


if __name__ == "__main__":
    main()
