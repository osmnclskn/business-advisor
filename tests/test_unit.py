# tests/test_unit.py

import pytest


class TestDiscoveryOutputStructure:

    def test_has_required_fields(self, sample_discovery_output):
        required = [
            "customer_stated_problem",
            "identified_business_problem",
            "hidden_root_risk",
            "chat_summary",
        ]

        for field in required:
            assert field in sample_discovery_output, f"Missing field: {field}"
            assert sample_discovery_output[field], f"Empty field: {field}"

    def test_conversation_turns_structure(self, sample_discovery_output):
        turns = sample_discovery_output.get("conversation_turns", [])

        assert len(turns) > 0, "No conversation turns"

        for turn in turns:
            assert "question" in turn, "Missing question"
            assert "answer" in turn, "Missing answer"
            assert "turn_number" in turn, "Missing turn_number"


class TestProblemTreeStructure:

    def test_has_required_fields(self, sample_problem_tree):
        assert "problem_type" in sample_problem_tree, "Missing problem_type"
        assert "main_problem" in sample_problem_tree, "Missing main_problem"
        assert "problem_tree" in sample_problem_tree, "Missing problem_tree"

    def test_valid_problem_type(self, sample_problem_tree):
        valid_types = [
            "growth", "cost", "operational", "technology",
            "regulation", "organizational", "hybrid",
        ]

        assert sample_problem_tree["problem_type"] in valid_types

    def test_tree_items_structure(self, sample_problem_tree):
        tree = sample_problem_tree["problem_tree"]

        assert isinstance(tree, list), "Tree should be a list"
        assert len(tree) >= 1, "Tree should have at least 1 item"

        for item in tree:
            assert "main_cause" in item, "Missing main_cause"
            assert "sub_causes" in item, "Missing sub_causes"
            assert len(item["sub_causes"]) >= 1, "Need at least 1 sub_cause"


class TestActionPlanStructure:

    def test_has_required_fields(self, sample_action_plan):
        required = ["short_term", "mid_term", "long_term", "quick_wins", "risks", "success_metrics"]

        for field in required:
            assert field in sample_action_plan, f"Missing field: {field}"

    def test_action_item_structure(self, sample_action_plan):
        action_fields = ["action", "timeline", "owner", "priority", "expected_outcome"]

        for action in sample_action_plan["short_term"]:
            for field in action_fields:
                assert field in action, f"Missing field in action: {field}"

    def test_valid_priority_values(self, sample_action_plan):
        valid_priorities = ["high", "medium", "low"]

        all_actions = (
            sample_action_plan["short_term"] +
            sample_action_plan["mid_term"] +
            sample_action_plan["long_term"]
        )

        for action in all_actions:
            assert action["priority"] in valid_priorities


class TestRiskAnalysisStructure:

    def test_has_required_fields(self, sample_risk_analysis):
        assert "risks" in sample_risk_analysis
        assert "overall_risk_level" in sample_risk_analysis
        assert "top_priority_risk" in sample_risk_analysis

    def test_risk_detail_structure(self, sample_risk_analysis):
        risk_fields = [
            "risk_name", "probability", "impact",
            "early_warning_signs", "mitigation_strategy", "contingency_plan"
        ]

        for risk in sample_risk_analysis["risks"]:
            for field in risk_fields:
                assert field in risk, f"Missing field in risk: {field}"

    def test_valid_risk_levels(self, sample_risk_analysis):
        valid_levels = ["low", "medium", "high", "critical"]

        assert sample_risk_analysis["overall_risk_level"] in valid_levels

        for risk in sample_risk_analysis["risks"]:
            assert risk["probability"] in valid_levels
            assert risk["impact"] in valid_levels


class TestBusinessReportStructure:

    def test_has_required_fields(self, sample_business_report):
        required = ["executive_summary", "report_markdown", "generated_at"]

        for field in required:
            assert field in sample_business_report, f"Missing field: {field}"
            assert sample_business_report[field], f"Empty field: {field}"

    def test_executive_summary_not_empty(self, sample_business_report):
        assert len(sample_business_report["executive_summary"]) > 20


class TestAgentFlowLogic:

    def test_non_business_ends_at_peer(self, sample_non_business_state):
        assert sample_non_business_state["agent_flow"] == ["peer"]
        assert sample_non_business_state["is_complete"] == True

    def test_business_problem_goes_to_discovery(self, sample_business_problem_state):
        flow = sample_business_problem_state["agent_flow"]

        assert "peer" in flow
        assert "discovery" in flow

    def test_completed_flow_has_all_agents(self, sample_completed_state):
        flow = sample_completed_state["agent_flow"]
        expected_agents = ["peer", "discovery", "structuring", "action_plan", "risk", "report"]

        for agent in expected_agents:
            assert agent in flow, f"Missing agent in flow: {agent}"

        assert sample_completed_state["is_complete"] == True

    def test_completed_has_all_outputs(self, sample_completed_state):
        assert sample_completed_state["discovery_output"] is not None
        assert sample_completed_state["problem_tree"] is not None
        assert sample_completed_state["action_plan"] is not None
        assert sample_completed_state["risk_analysis"] is not None
        assert sample_completed_state["business_report"] is not None


class TestSessionStateLogic:

    def test_awaiting_input_during_discovery(self, sample_business_problem_state):
        assert sample_business_problem_state["awaiting_user_input"] == True
        assert sample_business_problem_state["is_complete"] == False

    def test_not_awaiting_when_complete(self, sample_completed_state):
        assert sample_completed_state["awaiting_user_input"] == False
        assert sample_completed_state["is_complete"] == True