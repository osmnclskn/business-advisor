import json

from app.agents.base import BaseAgent
from app.llm import get_risk_llm
from app.models.domain import (
    ActionPlan,
    RiskAnalysis,
    RiskDetail,
    RiskLevel,
    StructuredProblemTree,
)
from app.utils import clean_llm_json_response


class RiskAgent(BaseAgent):
    def __init__(self):
        super().__init__(llm=get_risk_llm())

    def analyze_risks(
        self,
        action_plan: ActionPlan,
        problem_tree: StructuredProblemTree,
    ) -> RiskAnalysis:
        risks_formatted = "\n".join(f"- {risk}" for risk in action_plan.risks)

        analysis_response = self.invoke_llm(
            prompt_name="risk_analysis",
            prompt_variables={
                "main_problem": problem_tree.main_problem,
                "problem_type": problem_tree.problem_type.value,
                "risks_list": risks_formatted,
                "short_term_count": len(action_plan.short_term),
                "mid_term_count": len(action_plan.mid_term),
                "long_term_count": len(action_plan.long_term),
            },
        )
        return self._parse_analysis(analysis_response, action_plan.risks)

    async def analyze_risks_async(
        self,
        action_plan: ActionPlan,
        problem_tree: StructuredProblemTree,
    ) -> RiskAnalysis:
        risks_formatted = "\n".join(f"- {risk}" for risk in action_plan.risks)

        analysis_response = await self.invoke_llm_async(
            prompt_name="risk_analysis",
            prompt_variables={
                "main_problem": problem_tree.main_problem,
                "problem_type": problem_tree.problem_type.value,
                "risks_list": risks_formatted,
                "short_term_count": len(action_plan.short_term),
                "mid_term_count": len(action_plan.mid_term),
                "long_term_count": len(action_plan.long_term),
            },
        )
        return self._parse_analysis(analysis_response, action_plan.risks)

    def _parse_analysis(self, llm_response: str, original_risks: list[str]) -> RiskAnalysis:
        try:
            cleaned = clean_llm_json_response(llm_response)
            parsed = json.loads(cleaned)

            risk_details = []
            for risk_data in parsed.get("risks", []):
                risk_details.append(
                    RiskDetail(
                        risk_name=risk_data.get("risk_name", ""),
                        probability=self._parse_level(risk_data.get("probability", "medium")),
                        impact=self._parse_level(risk_data.get("impact", "medium")),
                        early_warning_signs=risk_data.get("early_warning_signs", []),
                        mitigation_strategy=risk_data.get("mitigation_strategy", ""),
                        contingency_plan=risk_data.get("contingency_plan", ""),
                    )
                )

            return RiskAnalysis(
                risks=risk_details,
                overall_risk_level=self._parse_level(parsed.get("overall_risk_level", "medium")),
                top_priority_risk=parsed.get("top_priority_risk", original_risks[0] if original_risks else ""),
            )
        except json.JSONDecodeError:
            return self._fallback_analysis(original_risks)

    def _parse_level(self, level_str: str) -> RiskLevel:
        level_lower = level_str.lower()
        for level in RiskLevel:
            if level.value == level_lower:
                return level
        return RiskLevel.MEDIUM

    def _fallback_analysis(self, original_risks: list[str]) -> RiskAnalysis:
        fallback_risks = [
            RiskDetail(
                risk_name=risk,
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                early_warning_signs=["Manuel değerlendirme gerekli"],
                mitigation_strategy="Detaylı analiz yapılmalı",
                contingency_plan="Alternatif plan oluşturulmalı",
            )
            for risk in original_risks
        ]
        return RiskAnalysis(
            risks=fallback_risks,
            overall_risk_level=RiskLevel.MEDIUM,
            top_priority_risk=original_risks[0] if original_risks else "Belirsiz",
        )
