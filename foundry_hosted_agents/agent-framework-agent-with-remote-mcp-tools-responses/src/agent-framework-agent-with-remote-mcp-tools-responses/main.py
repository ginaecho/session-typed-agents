# Copyright (c) Microsoft. All rights reserved.
#
# STJP grouped hosted agents — booking_saga role group.
#
# Instead of hosting one agent (or scattering N separate Agent Service agents),
# this hosts the *group* for one use case as a single Agent Framework Workflow,
# wrapped as one WorkflowAgent and served via ResponsesHostServer. A single run
# therefore emits ONE group-interaction trace covering all roles talking to each
# other — which is what shows up under the Foundry "Workflows" surface.
#
# The role instructions follow the STJP-validated booking_saga protocol order
# (reserve-first, breaking the pay-vs-reserve deadlock): Traveler requests, Hotel
# holds the room, Payment captures the charge, Hotel confirms.

import logging
import os

from agent_framework import Agent, WorkflowAgent, WorkflowBuilder
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# STJP-validated per-role instructions (booking_saga). Order enforced by the
# validated global protocol: RequestBooking -> RoomHeld -> PaymentCaptured ->
# BookingConfirmed. No role waits on a message the protocol never lets it reach.
# ---------------------------------------------------------------------------
TRAVELER = (
    "You are the Traveler in a hotel booking. Start by requesting a booking "
    "(state the stay you want). Then wait for the final booking confirmation "
    "and acknowledge it. Keep messages short."
)
HOTEL = (
    "You are the Hotel reservation service. When the Traveler requests a "
    "booking, FIRST hold the room and tell the Payment service the room is held "
    "(RoomHeld). After Payment confirms the charge is captured, confirm the "
    "booking back to the Traveler (BookingConfirmed). Never confirm before "
    "payment is captured, and never ask Payment to charge before the room is "
    "held. Keep messages short."
)
PAYMENT = (
    "You are the Payment service. Capture the charge ONLY after the Hotel tells "
    "you the room is held (RoomHeld), then report PaymentCaptured with the "
    "amount back to the Hotel. Never charge for a room that was not held. Keep "
    "messages short."
)


def main():
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        credential=DefaultAzureCredential(),
    )

    traveler = Agent(client, TRAVELER, name="Traveler",
                     description="Requests the booking and receives confirmation")
    hotel = Agent(client, HOTEL, name="Hotel",
                  description="Holds and confirms the room")
    payment = Agent(client, PAYMENT, name="Payment",
                    description="Captures the charge after the room is held")

    # Sequential group in validated protocol order. add_chain wires
    # Traveler -> Hotel -> Payment as one workflow; the run is a single grouped
    # interaction (not three separate hosted agents).
    workflow = (
        WorkflowBuilder(start_executor=traveler, name="stjp-booking-saga",
                        description="STJP booking-saga role group (validated)")
        .add_chain([traveler, hotel, payment])
        .build()
    )

    group = WorkflowAgent(
        workflow,
        name="stjp-booking-saga-group",
        description="STJP booking_saga hosted as one grouped workflow "
                    "(Traveler + Hotel + Payment) following the validated protocol.",
    )

    server = ResponsesHostServer(group)
    server.run()


if __name__ == "__main__":
    main()
