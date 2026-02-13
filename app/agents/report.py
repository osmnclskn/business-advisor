from datetime import datetime
from app.agents.base import BaseAgent
from app.llm import get_report_llm
from app.models.domain import (
    ActionItem,
    ActionPlan,
    BusinessReport,
    DiscoveryOutput,
    StructuredProblemTree,
)


REPORT_LABELS = {
    "Turkish": {
        "title": "İş Problemi Analiz Raporu",
        "generated": "Oluşturulma",
        "exec_summary": "Yönetici Özeti",
        "problem_def": "Problem Tanımı",
        "customer_statement": "Müşteri İfadesi",
        "identified_problem": "Tespit Edilen Problem",
        "hidden_risk": "Gizli Risk",
        "problem_analysis": "Problem Analizi",
        "problem_type": "Problem Tipi",
        "main_problem": "Ana Problem",
        "root_causes": "Kök Nedenler",
        "action_plan": "Aksiyon Planı",
        "short_term": "Kısa Vade (0-3 Ay)",
        "mid_term": "Orta Vade (3-6 Ay)",
        "long_term": "Uzun Vade (6-12 Ay)",
        "quick_wins": "Hızlı Kazanımlar",
        "risks": "Riskler",
        "success_metrics": "Başarı Metrikleri",
        "appendix": "Ek: Keşif Görüşmesi Özeti",
        "action_col": "Aksiyon",
        "timeline_col": "Süre",
        "owner_col": "Sorumlu",
        "priority_col": "Öncelik",
        "no_actions": "Bu dönem için aksiyon tanımlanmamış.",
    },
    "English": {
        "title": "Business Problem Analysis Report",
        "generated": "Generated",
        "exec_summary": "Executive Summary",
        "problem_def": "Problem Definition",
        "customer_statement": "Customer Statement",
        "identified_problem": "Identified Problem",
        "hidden_risk": "Hidden Risk",
        "problem_analysis": "Problem Analysis",
        "problem_type": "Problem Type",
        "main_problem": "Main Problem",
        "root_causes": "Root Causes",
        "action_plan": "Action Plan",
        "short_term": "Short Term (0-3 Months)",
        "mid_term": "Mid Term (3-6 Months)",
        "long_term": "Long Term (6-12 Months)",
        "quick_wins": "Quick Wins",
        "risks": "Risks",
        "success_metrics": "Success Metrics",
        "appendix": "Appendix: Discovery Session Summary",
        "action_col": "Action",
        "timeline_col": "Timeline",
        "owner_col": "Owner",
        "priority_col": "Priority",
        "no_actions": "No actions defined for this period.",
    },
}


class ReportAgent(BaseAgent):
    def __init__(self):
        super().__init__(llm=get_report_llm())

    def generate_report(
        self,
        discovery_output: DiscoveryOutput,
        problem_tree: StructuredProblemTree,
        action_plan: ActionPlan,
        response_language: str = "Turkish",
    ) -> BusinessReport:
        """Generate the full business report."""
        executive_summary = self._generate_summary(
            discovery_output, problem_tree, action_plan, response_language
        )

        report_markdown = self._build_markdown(
            discovery_output, problem_tree, action_plan, executive_summary, response_language
        )

        return BusinessReport(
            executive_summary=executive_summary,
            report_markdown=report_markdown,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    async def generate_report_async(
        self,
        discovery_output: DiscoveryOutput,
        problem_tree: StructuredProblemTree,
        action_plan: ActionPlan,
        response_language: str = "Turkish",
    ) -> BusinessReport:
        executive_summary = await self._generate_summary_async(
            discovery_output, problem_tree, action_plan, response_language
        )

        report_markdown = self._build_markdown(
            discovery_output, problem_tree, action_plan, executive_summary, response_language
        )

        return BusinessReport(
            executive_summary=executive_summary,
            report_markdown=report_markdown,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def _generate_summary(
        self,
        discovery: DiscoveryOutput,
        tree: StructuredProblemTree,
        plan: ActionPlan,
        response_language: str = "Turkish",
    ) -> str:
        short_term_actions = "\n".join(
            f"- {a.action} ({a.timeline})" for a in plan.short_term[:3]
        )
        success_metrics = "\n".join(f"- {m}" for m in plan.success_metrics[:3])

        summary_response = self.invoke_llm(
            prompt_name="report_summary",
            prompt_variables={
                "customer_stated_problem": discovery.customer_stated_problem,
                "identified_problem": discovery.identified_business_problem,
                "problem_type": tree.problem_type.value,
                "main_problem": tree.main_problem,
                "short_term_actions": short_term_actions,
                "success_metrics": success_metrics,
                "response_language": response_language,
            },
        )
        return summary_response.strip()

    async def _generate_summary_async(
        self,
        discovery: DiscoveryOutput,
        tree: StructuredProblemTree,
        plan: ActionPlan,
        response_language: str = "Turkish",
    ) -> str:
        short_term_actions = "\n".join(
            f"- {a.action} ({a.timeline})" for a in plan.short_term[:3]
        )
        success_metrics = "\n".join(f"- {m}" for m in plan.success_metrics[:3])

        summary_response = await self.invoke_llm_async(
            prompt_name="report_summary",
            prompt_variables={
                "customer_stated_problem": discovery.customer_stated_problem,
                "identified_problem": discovery.identified_business_problem,
                "problem_type": tree.problem_type.value,
                "main_problem": tree.main_problem,
                "short_term_actions": short_term_actions,
                "success_metrics": success_metrics,
                "response_language": response_language,
            },
        )
        return summary_response.strip()

    def _build_action_table(self, actions: list[ActionItem], labels: dict) -> str:
        """Convert action list to Markdown table with language-adaptive headers."""
        if not actions:
            return f"*{labels['no_actions']}*\n"

        table_lines = [
            f"| {labels['action_col']} | {labels['timeline_col']} | {labels['owner_col']} | {labels['priority_col']} |",
            "|---------|------|---------|---------|",
        ]
        for action in actions:
            table_lines.append(
                f"| {action.action} | {action.timeline} | {action.owner} | {action.priority} |"
            )
        return "\n".join(table_lines) + "\n"

    def _build_markdown(
        self,
        discovery: DiscoveryOutput,
        tree: StructuredProblemTree,
        plan: ActionPlan,
        executive_summary: str,
        response_language: str = "Turkish",
    ) -> str:
        """Template-based Markdown report — headers adapt to detected language."""

        report_date = datetime.now().strftime("%d %B %Y")
        labels = REPORT_LABELS.get(response_language, REPORT_LABELS["English"])

        # Format problem tree
        problem_tree_text = ""
        for node in tree.problem_tree:
            problem_tree_text += f"**{node.main_cause}**\n"
            for sub in node.sub_causes:
                problem_tree_text += f"  - {sub}\n"
            problem_tree_text += "\n"

        quick_wins_text = "\n".join(f"- ⚡ {win}" for win in plan.quick_wins)
        risks_text = "\n".join(f"- ⚠️ {risk}" for risk in plan.risks)
        metrics_text = "\n".join(f"- 📊 {metric}" for metric in plan.success_metrics)

        report_template = f"""# {labels["title"]}

*{labels["generated"]}: {report_date}*

## {labels["exec_summary"]}

{executive_summary}

## {labels["problem_def"]}

**{labels["customer_statement"]}:** {discovery.customer_stated_problem}

**{labels["identified_problem"]}:** {discovery.identified_business_problem}

**{labels["hidden_risk"]}:** {discovery.hidden_root_risk}

## {labels["problem_analysis"]}

**{labels["problem_type"]}:** {tree.problem_type.value.upper()}

**{labels["main_problem"]}:** {tree.main_problem}

### {labels["root_causes"]}

{problem_tree_text}

## {labels["action_plan"]}

### {labels["short_term"]}

{self._build_action_table(plan.short_term, labels)}

### {labels["mid_term"]}

{self._build_action_table(plan.mid_term, labels)}

### {labels["long_term"]}

{self._build_action_table(plan.long_term, labels)}

## {labels["quick_wins"]}

{quick_wins_text}

## {labels["risks"]}

{risks_text}

## {labels["success_metrics"]}

{metrics_text}

## {labels["appendix"]}

{discovery.chat_summary}
"""
        return report_template