from functools import lru_cache
from typing import Literal, TypedDict

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, StateGraph
from pymongo import MongoClient

from app.agents.action import ActionPlanAgent
from app.agents.discovery import DiscoveryAgent
from app.agents.peer import PeerAgent
from app.agents.report import ReportAgent
from app.agents.risk import RiskAgent
from app.agents.structuring import StructuringAgent
from app.config import get_settings
from app.models.domain import (
    ActionItem,
    ActionPlan,
    ConversationTurn,
    DiscoveryOutput,
    IntentType,
    ProblemNode,
    ProblemType,
    StructuredProblemTree,
)


class WorkflowState(TypedDict):
    session_id: str
    user_input: str
    language: str  # "Turkish" or "English" — detected by PeerAgent, propagated to all agents
    intent: str | None
    peer_response: dict | None
    discovery_question: str | None
    discovery_output: dict | None
    awaiting_user_input: bool
    problem_tree: dict | None
    action_plan: dict | None
    risk_analysis: dict | None
    business_report: dict | None
    current_agent: str
    agent_flow: list[str]
    is_complete: bool
    error: str | None


def create_initial_state(session_id: str, user_input: str) -> WorkflowState:
    return WorkflowState(
        session_id=session_id,
        user_input=user_input,
        language="Turkish",  # default, overridden by PeerAgent detection
        intent=None,
        peer_response=None,
        discovery_question=None,
        discovery_output=None,
        awaiting_user_input=False,
        problem_tree=None,
        action_plan=None,
        risk_analysis=None,
        business_report=None,
        current_agent="peer",
        agent_flow=[],
        is_complete=False,
        error=None,
    )


class AdvisorWorkflow:

    def __init__(self, checkpointer: MongoDBSaver | None = None):
        self._peer_agent = PeerAgent()
        self._structuring_agent = StructuringAgent()
        self._action_plan_agent = ActionPlanAgent()
        self._risk_agent = RiskAgent()
        self._report_agent = ReportAgent()
        self._discovery_agents: dict[str, DiscoveryAgent] = {}
        self._checkpointer = checkpointer
        self.graph = self._build_graph()

    def _get_discovery_agent(self, session_id: str) -> DiscoveryAgent:
        if session_id not in self._discovery_agents:
            self._discovery_agents[session_id] = DiscoveryAgent()
        return self._discovery_agents[session_id]

    def _cleanup_session(self, session_id: str):
        if session_id in self._discovery_agents:
            del self._discovery_agents[session_id]

    def _enter_node(self, state: WorkflowState, node_name: str):
        if node_name not in state["agent_flow"]:
            state["agent_flow"].append(node_name)
        state["current_agent"] = node_name

    def _to_discovery_output(self, data: dict) -> DiscoveryOutput:
        return DiscoveryOutput(
            customer_stated_problem=data["customer_stated_problem"],
            identified_business_problem=data["identified_business_problem"],
            hidden_root_risk=data["hidden_root_risk"],
            chat_summary=data["chat_summary"],
            conversation_turns=[
                ConversationTurn(**turn) 
                for turn in data.get("conversation_turns", [])
            ],
        )

    def _to_problem_tree(self, data: dict) -> StructuredProblemTree:
        return StructuredProblemTree(
            problem_type=ProblemType(data["problem_type"]),
            main_problem=data["main_problem"],
            problem_tree=[ProblemNode(**node) for node in data["problem_tree"]],
        )

    def _to_action_plan(self, data: dict) -> ActionPlan:
        return ActionPlan(
            short_term=[ActionItem(**a) for a in data["short_term"]],
            mid_term=[ActionItem(**a) for a in data["mid_term"]],
            long_term=[ActionItem(**a) for a in data["long_term"]],
            quick_wins=data["quick_wins"],
            risks=data["risks"],
            success_metrics=data["success_metrics"],
        )

    def _set_error(self, state: WorkflowState, agent: str, error: Exception):
        state["error"] = f"{agent} error: {str(error)}"
        state["is_complete"] = True

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(WorkflowState)

        workflow.add_node("peer", self._peer_node)
        workflow.add_node("discovery", self._discovery_node)
        workflow.add_node("structuring", self._structuring_node)
        workflow.add_node("action_plan", self._action_plan_node)
        workflow.add_node("risk", self._risk_node)
        workflow.add_node("report", self._report_node)

        workflow.set_entry_point("peer")

        workflow.add_conditional_edges(
            "peer", 
            self._route_after_peer, 
            {"discovery": "discovery", "end": END}
        )

        workflow.add_conditional_edges(
            "discovery",
            self._route_after_discovery,
            {"structuring": "structuring", "await_input": END, "end": END},
        )

        workflow.add_edge("structuring", "action_plan")
        workflow.add_edge("action_plan", "risk")
        workflow.add_edge("risk", "report")
        workflow.add_edge("report", END)

        return workflow.compile(checkpointer=self._checkpointer)

    def _peer_node(self, state: WorkflowState) -> WorkflowState:
        self._enter_node(state, "peer")

        try:
            peer_result = self._peer_agent.process(state["user_input"])
            state["intent"] = peer_result["intent"]
            state["language"] = peer_result.get("language", "Turkish")
            state["peer_response"] = peer_result

            if peer_result["intent"] != IntentType.BUSINESS_PROBLEM.value:
                state["is_complete"] = True

        except Exception as e:
            self._set_error(state, "PeerAgent", e)

        return state

    def _discovery_node(self, state: WorkflowState) -> WorkflowState:
        self._enter_node(state, "discovery")

        try:
            discovery_agent = self._get_discovery_agent(state["session_id"])

            if state["discovery_question"] is None:
                first_question = discovery_agent.start_discovery(
                    state["user_input"], language=state.get("language", "Turkish")
                )
                state["discovery_question"] = first_question
                state["awaiting_user_input"] = True
            else:
                discovery_result = discovery_agent.continue_discovery(state["user_input"])

                if isinstance(discovery_result, DiscoveryOutput):
                    state["discovery_output"] = discovery_result.model_dump()
                    state["awaiting_user_input"] = False
                else:
                    state["discovery_question"] = discovery_result
                    state["awaiting_user_input"] = True

        except Exception as e:
            self._set_error(state, "DiscoveryAgent", e)

        return state

    def _structuring_node(self, state: WorkflowState) -> WorkflowState:
        self._enter_node(state, "structuring")

        try:
            if state["discovery_output"] is None:
                self._set_error(state, "StructuringAgent", Exception("Discovery output missing"))
                return state

            discovery_output = self._to_discovery_output(state["discovery_output"])
            structured_tree = self._structuring_agent.structure_problem(
                discovery_output, response_language=state.get("language", "Turkish")
            )
            state["problem_tree"] = structured_tree.model_dump()

        except Exception as e:
            self._set_error(state, "StructuringAgent", e)

        return state

    def _action_plan_node(self, state: WorkflowState) -> WorkflowState:
        self._enter_node(state, "action_plan")

        try:
            if state["problem_tree"] is None:
                self._set_error(state, "ActionPlanAgent", Exception("Problem tree missing"))
                return state

            problem_tree = self._to_problem_tree(state["problem_tree"])
            chat_summary = state["discovery_output"]["chat_summary"]

            generated_plan = self._action_plan_agent.create_plan(
                problem_tree, chat_summary, response_language=state.get("language", "Turkish")
            )
            state["action_plan"] = generated_plan.model_dump()

        except Exception as e:
            self._set_error(state, "ActionPlanAgent", e)

        return state

    def _risk_node(self, state: WorkflowState) -> WorkflowState:
        self._enter_node(state, "risk")

        try:
            if state["action_plan"] is None:
                self._set_error(state, "RiskAgent", Exception("Action plan missing"))
                return state

            action_plan = self._to_action_plan(state["action_plan"])
            problem_tree = self._to_problem_tree(state["problem_tree"])

            analyzed_risks = self._risk_agent.analyze_risks(
                action_plan, problem_tree, response_language=state.get("language", "Turkish")
            )
            state["risk_analysis"] = analyzed_risks.model_dump()

        except Exception as e:
            self._set_error(state, "RiskAgent", e)

        return state

    def _report_node(self, state: WorkflowState) -> WorkflowState:
        self._enter_node(state, "report")

        try:
            discovery_output = self._to_discovery_output(state["discovery_output"])
            problem_tree = self._to_problem_tree(state["problem_tree"])
            action_plan = self._to_action_plan(state["action_plan"])

            final_report = self._report_agent.generate_report(
                discovery_output, problem_tree, action_plan,
                response_language=state.get("language", "Turkish")
            )
            state["business_report"] = final_report.model_dump()
            state["is_complete"] = True

            self._cleanup_session(state["session_id"])

        except Exception as e:
            self._set_error(state, "ReportAgent", e)

        return state

    def _route_after_peer(self, state: WorkflowState) -> Literal["discovery", "end"]:
        if state.get("error"):
            return "end"

        if state["intent"] == IntentType.BUSINESS_PROBLEM.value:
            return "discovery"

        return "end"

    def _route_after_discovery(
        self, state: WorkflowState
    ) -> Literal["structuring", "await_input", "end"]:
        if state.get("error"):
            return "end"

        if state["awaiting_user_input"]:
            return "await_input"

        return "structuring"

    def run(self, session_id: str, user_input: str) -> WorkflowState:
        state = create_initial_state(session_id, user_input)
        config = {"configurable": {"thread_id": session_id}}
        return self.graph.invoke(state, config)

    def continue_session(self, state: WorkflowState, user_answer: str) -> WorkflowState:
        state["user_input"] = user_answer
        response_lang = state.get("language", "Turkish")

        discovery_agent = self._get_discovery_agent(state["session_id"])

        try:
            discovery_result = discovery_agent.continue_discovery(user_answer)
        except Exception as e:
            self._set_error(state, "DiscoveryAgent", e)
            return state

        # Discovery still in progress
        if not isinstance(discovery_result, DiscoveryOutput):
            state["discovery_question"] = discovery_result
            state["awaiting_user_input"] = True
            return state

        # Discovery complete — chain remaining agents with detected language
        state["discovery_output"] = discovery_result.model_dump()
        state["awaiting_user_input"] = False

        # Structuring
        try:
            structured_tree = self._structuring_agent.structure_problem(
                discovery_result, response_language=response_lang
            )
            state["problem_tree"] = structured_tree.model_dump()
            state["agent_flow"].append("structuring")
        except Exception as e:
            self._set_error(state, "StructuringAgent", e)
            return state

        # ActionPlan
        try:
            generated_plan = self._action_plan_agent.create_plan(
                structured_tree, discovery_result.chat_summary,
                response_language=response_lang
            )
            state["action_plan"] = generated_plan.model_dump()
            state["agent_flow"].append("action_plan")
        except Exception as e:
            self._set_error(state, "ActionPlanAgent", e)
            return state

        # Risk
        try:
            analyzed_risks = self._risk_agent.analyze_risks(
                generated_plan, structured_tree, response_language=response_lang
            )
            state["risk_analysis"] = analyzed_risks.model_dump()
            state["agent_flow"].append("risk")
        except Exception as e:
            self._set_error(state, "RiskAgent", e)
            return state

        # Report
        try:
            final_report = self._report_agent.generate_report(
                discovery_result, structured_tree, generated_plan,
                response_language=response_lang
            )
            state["business_report"] = final_report.model_dump()
            state["agent_flow"].append("report")
        except Exception as e:
            self._set_error(state, "ReportAgent", e)
            return state

        state["is_complete"] = True
        self._cleanup_session(state["session_id"])

        return state


def create_workflow_with_checkpointer() -> AdvisorWorkflow:
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]
    checkpointer = MongoDBSaver(db)
    return AdvisorWorkflow(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_advisor_workflow() -> AdvisorWorkflow:
    return AdvisorWorkflow()