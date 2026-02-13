import json

from app.agents.base import BaseAgent
from app.llm import get_structuring_llm
from app.models.domain import (
    DiscoveryOutput,
    ProblemNode,
    ProblemType,
    StructuredProblemTree,
)
from app.utils import clean_llm_json_response


class StructuringAgent(BaseAgent):
    def __init__(self):
        super().__init__(llm=get_structuring_llm())

    def structure_problem(
        self, discovery_output: DiscoveryOutput, response_language: str = "Turkish"
    ) -> StructuredProblemTree:
        structuring_response = self.invoke_llm(
            prompt_name="structure_tree",
            prompt_variables={
                "customer_stated_problem": discovery_output.customer_stated_problem,
                "identified_business_problem": discovery_output.identified_business_problem,
                "hidden_root_risk": discovery_output.hidden_root_risk,
                "chat_summary": discovery_output.chat_summary,
                "response_language": response_language,
            },
        )
        return self._parse_response(structuring_response)

    async def structure_problem_async(
        self, discovery_output: DiscoveryOutput, response_language: str = "Turkish"
    ) -> StructuredProblemTree:
        structuring_response = await self.invoke_llm_async(
            prompt_name="structure_tree",
            prompt_variables={
                "customer_stated_problem": discovery_output.customer_stated_problem,
                "identified_business_problem": discovery_output.identified_business_problem,
                "hidden_root_risk": discovery_output.hidden_root_risk,
                "chat_summary": discovery_output.chat_summary,
                "response_language": response_language,
            },
        )
        return self._parse_response(structuring_response)

    def _parse_response(self, llm_response: str) -> StructuredProblemTree:
        try:
            cleaned = clean_llm_json_response(llm_response)
            parsed = json.loads(cleaned)

            problem_type = self._parse_problem_type(
                parsed.get("problem_type", "Hybrid")
            )

            problem_nodes = []
            for node_data in parsed.get("problem_tree", []):
                problem_nodes.append(
                    ProblemNode(
                        main_cause=node_data.get("main_cause", ""),
                        sub_causes=node_data.get("sub_causes", []),
                    )
                )

            return StructuredProblemTree(
                problem_type=problem_type,
                main_problem=parsed.get("main_problem", ""),
                problem_tree=problem_nodes,
            )
        except json.JSONDecodeError:
            return self._fallback_response()

    def _parse_problem_type(self, type_string: str) -> ProblemType:
        type_lower = type_string.lower()

        for problem_type in ProblemType:
            if problem_type.value == type_lower:
                return problem_type

        return ProblemType.HYBRID

    def _fallback_response(self) -> StructuredProblemTree:
        return StructuredProblemTree(
            problem_type=ProblemType.HYBRID,
            main_problem="Analiz tamamlanamadÄ± - manuel deÄŸerlendirme gerekli",
            problem_tree=[
                ProblemNode(
                    main_cause="Veri YetersizliÄŸi",
                    sub_causes=[
                        "Otomatik analiz baÅŸarÄ±sÄ±z",
                        "Manuel inceleme Ã¶nerilir",
                    ],
                )
            ],
        )