# app/agents/action.py

import json

from app.agents.base import BaseAgent
from app.llm import get_action_llm
from app.models.domain import ActionItem, ActionPlan, StructuredProblemTree
from app.utils import clean_llm_json_response


class ActionPlanAgent(BaseAgent):
    def __init__(self):
        super().__init__(llm=get_action_llm())

    def create_plan(
        self, problem_tree: StructuredProblemTree, chat_summary: str
    ) -> ActionPlan:
        planning_response = self.invoke_llm(
            prompt_name="action_plan",
            prompt_variables={
                "problem_type": problem_tree.problem_type.value,
                "main_problem": problem_tree.main_problem,
                "problem_tree_formatted": self._format_tree(problem_tree),
                "chat_summary": chat_summary,
            },
        )
        return self._parse_plan(planning_response)

    async def create_plan_async(
        self, problem_tree: StructuredProblemTree, chat_summary: str
    ) -> ActionPlan:
        planning_response = await self.invoke_llm_async(
            prompt_name="action_plan",
            prompt_variables={
                "problem_type": problem_tree.problem_type.value,
                "main_problem": problem_tree.main_problem,
                "problem_tree_formatted": self._format_tree(problem_tree),
                "chat_summary": chat_summary,
            },
        )
        return self._parse_plan(planning_response)

    def _format_tree(self, problem_tree: StructuredProblemTree) -> str:
        lines = []
        for node in problem_tree.problem_tree:
            lines.append(f"- {node.main_cause}")
            for sub in node.sub_causes:
                lines.append(f"  - {sub}")
        return "\n".join(lines)

    def _parse_plan(self, llm_response: str) -> ActionPlan:
        #print(f"LLM Response for Action Plan:\n{llm_response}\n")
        try:
            cleaned = clean_llm_json_response(llm_response)
            #print(f"Cleaned LLM Response for Action Plan:\n{cleaned}\n")
            parsed = json.loads(cleaned)

            return ActionPlan(
                short_term=self._parse_action_items(parsed.get("short_term", [])),
                mid_term=self._parse_action_items(parsed.get("mid_term", [])),
                long_term=self._parse_action_items(parsed.get("long_term", [])),
                quick_wins=parsed.get("quick_wins", []),
                risks=parsed.get("risks", []),
                success_metrics=parsed.get("success_metrics", []),
            )
        except json.JSONDecodeError:
            return self._fallback_plan()

    def _parse_action_items(self, items_data: list) -> list[ActionItem]:
        action_items = []
        for item in items_data:
            action_items.append(
                ActionItem(
                    action=item.get("action", ""),
                    timeline=item.get("timeline", ""),
                    owner=item.get("owner", ""),
                    priority=item.get("priority", "medium"),
                    expected_outcome=item.get("expected_outcome", ""),
                )
            )
        return action_items

    def _fallback_plan(self) -> ActionPlan:
        return ActionPlan(
            short_term=[
                ActionItem(
                    action="Manuel aksiyon planı oluştur",
                    timeline="1 hafta",
                    owner="Proje yöneticisi",
                    priority="high",
                    expected_outcome="Detaylı plan hazırla",
                )
            ],
            mid_term=[],
            long_term=[],
            quick_wins=["Otomatik analiz başarısız - manuel değerlendirme önerilir"],
            risks=["Veri yetersizliği"],
            success_metrics=["Plan tamamlanması"],
        )