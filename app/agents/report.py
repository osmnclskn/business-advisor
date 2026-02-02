# app/agents/report.py

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


class ReportAgent(BaseAgent):
    """
    Tüm analiz çıktılarını profesyonel rapora dönüştürür.
    
    Halüsinasyon riski yok - sadece mevcut veriyi formatlar.
    Executive summary için LLM kullanılır, geri kalan template-based.
    """

    def __init__(self):
        super().__init__(llm=get_report_llm())

    def generate_report(
        self,
        discovery_output: DiscoveryOutput,
        problem_tree: StructuredProblemTree,
        action_plan: ActionPlan,
    ) -> BusinessReport:
        """Tam rapor oluştur."""
        executive_summary = self._generate_summary(
            discovery_output, problem_tree, action_plan
        )
        
        report_markdown = self._build_markdown(
            discovery_output, problem_tree, action_plan, executive_summary
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
    ) -> BusinessReport:
        """FastAPI endpoint'lerinde kullanılacak."""
        executive_summary = await self._generate_summary_async(
            discovery_output, problem_tree, action_plan
        )
        
        report_markdown = self._build_markdown(
            discovery_output, problem_tree, action_plan, executive_summary
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
    ) -> str:
        """LLM ile executive summary oluştur."""
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
            },
        )
        return summary_response.strip()

    async def _generate_summary_async(
        self,
        discovery: DiscoveryOutput,
        tree: StructuredProblemTree,
        plan: ActionPlan,
    ) -> str:
        """Async executive summary."""
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
            },
        )
        return summary_response.strip()

    def _build_action_table(self, actions: list[ActionItem]) -> str:
        """Aksiyon listesini Markdown tablosuna çevir."""
        if not actions:
            return "*Bu dönem için aksiyon tanımlanmamış.*\n"
        
        table_lines = [
            "| Aksiyon | Süre | Sorumlu | Öncelik |",
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
    ) -> str:
        """Template-based Markdown rapor oluştur."""
        
        report_date = datetime.now().strftime("%d %B %Y")
        
        # Problem ağacı formatla
        problem_tree_text = ""
        for node in tree.problem_tree:
            problem_tree_text += f"**{node.main_cause}**\n"
            for sub in node.sub_causes:
                problem_tree_text += f"  - {sub}\n"
            problem_tree_text += "\n"
        
        # Quick wins formatla
        quick_wins_text = "\n".join(f"- ⚡ {win}" for win in plan.quick_wins)
        
        # Riskler formatla
        risks_text = "\n".join(f"- ⚠️ {risk}" for risk in plan.risks)
        
        # Metrikler formatla
        metrics_text = "\n".join(f"- 📊 {metric}" for metric in plan.success_metrics)
        
        report_template = f"""# İş Problemi Analiz Raporu

*Oluşturulma: {report_date}*

## Yönetici Özeti

{executive_summary}

## Problem Tanımı

**Müşteri İfadesi:** {discovery.customer_stated_problem}

**Tespit Edilen Problem:** {discovery.identified_business_problem}

**Gizli Risk:** {discovery.hidden_root_risk}

## Problem Analizi

**Problem Tipi:** {tree.problem_type.value.upper()}

**Ana Problem:** {tree.main_problem}

### Kök Nedenler

{problem_tree_text}

## Aksiyon Planı

### Kısa Vade (0-3 Ay)

{self._build_action_table(plan.short_term)}

### Orta Vade (3-6 Ay)

{self._build_action_table(plan.mid_term)}

### Uzun Vade (6-12 Ay)

{self._build_action_table(plan.long_term)}

## Hızlı Kazanımlar

{quick_wins_text}

## Riskler

{risks_text}

## Başarı Metrikleri

{metrics_text}

## Ek: Keşif Görüşmesi Özeti

{discovery.chat_summary}
"""
        return report_template


if __name__ == "__main__":
    from app.models.domain import ConversationTurn, ProblemNode, ProblemType

    agent = ReportAgent()

    test_discovery = DiscoveryOutput(
        customer_stated_problem="Müşteri şikayetleri çok arttı",
        identified_business_problem="Operasyonel verimsizlik ve kalite kontrol eksikliği",
        hidden_root_risk="Müşteri kaybı ve marka itibar hasarı",
        chat_summary="Müşteri son 6 ayda şikayetlerin %45 arttığını belirtti.",
        conversation_turns=[
            ConversationTurn(question="Ne zaman başladı?", answer="6 ay önce", turn_number=1)
        ],
    )

    test_tree = StructuredProblemTree(
        problem_type=ProblemType.OPERATIONAL,
        main_problem="Müşteri Şikayetlerinde Artış",
        problem_tree=[
            ProblemNode(
                main_cause="Teslimat Gecikmeleri",
                sub_causes=["Lojistik altyapı yetersiz", "Stok yönetimi zayıf"],
            ),
            ProblemNode(
                main_cause="Ürün Kalite Sorunları",
                sub_causes=["Kalite kontrol eksik", "Tedarikçi problemleri"],
            ),
        ],
    )

    test_plan = ActionPlan(
        short_term=[
            ActionItem(
                action="Lojistik süreç analizi",
                timeline="2 hafta",
                owner="Operasyon",
                priority="high",
                expected_outcome="Darboğazları tespit et",
            ),
            ActionItem(
                action="Kalite kontrol sıklığını artır",
                timeline="1 hafta",
                owner="Kalite Ekibi",
                priority="high",
                expected_outcome="Hatalı ürün oranını düşür",
            ),
        ],
        mid_term=[
            ActionItem(
                action="Yeni lojistik partner araştır",
                timeline="3 ay",
                owner="Tedarik Zinciri",
                priority="high",
                expected_outcome="Teslimat süresini kısalt",
            ),
        ],
        long_term=[
            ActionItem(
                action="Otomasyon yatırımı",
                timeline="8 ay",
                owner="IT",
                priority="medium",
                expected_outcome="Operasyonel verimlilik",
            ),
        ],
        quick_wins=["Müşteri şikayet hattı kur", "Teslimat takip SMS'i başlat"],
        risks=["Kaynak yetersizliği", "Tedarikçi direnci"],
        success_metrics=["3 ayda şikayetlerde %20 azalma", "Teslimat süresinde %15 iyileşme"],
    )

    print("Rapor oluşturuluyor...\n")
    report = agent.generate_report(test_discovery, test_tree, test_plan)

    print("EXECUTIVE SUMMARY:")
    print("-" * 40)
    print(report.executive_summary)
    print("\nFULL REPORT (ilk 2000 karakter):")
    print("-" * 40)
    print(report.report_markdown[:200000])