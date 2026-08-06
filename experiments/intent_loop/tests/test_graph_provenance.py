from experiments.intent_loop.protocol_graph import graph_payload


def test_graph_message_and_edge_map_to_intent_and_scribble():
    protocol = """global protocol Delivery(role Analyst, role Requester) {
        FinalReport(String) from Analyst to Requester;
    }"""
    distilled = {
        "roles": [
            {"name": "Analyst", "description": "prepares the report"},
            {"name": "Requester", "description": "receives the report"}],
        "interactions": [{
            "iid": "I7", "sender": "Analyst", "receiver": "Requester",
            "what": "delivers the final report", "when": "after approval",
            "cardinality": "exactly once", "waits_for": ["I6"],
            "carries": [{"name": "report", "type": "string",
                         "constraint": "non-empty"}]}]}

    payload = graph_payload(protocol, distilled)

    message = payload["messages"][0]
    assert message["line"] == 2
    assert message["scribble"] == \
        "FinalReport(String) from Analyst to Requester;"
    assert message["intent_interactions"][0]["iid"] == "I7"
    assert payload["edges"][0]["intent_interactions"][0]["what"] == \
        "delivers the final report"
    assert payload["role_details"][0]["intent_role"]["description"] == \
        "prepares the report"