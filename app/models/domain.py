from enum import Enum

from pydantic import BaseModel, Field, computed_field


class IntentType(str, Enum):
    BUSINESS_INFO = "business_info"  # Doğrudan cevaplanacak bilgi sorusu
    BUSINESS_PROBLEM = "business_problem"  # Discovery'ye yönlendirilecek
    NON_BUSINESS = "non_business"  # Kapsam dışı


class ProblemType(str, Enum):
    GROWTH = "growth"
    COST = "cost"
    OPERATIONAL = "operational"
    TECHNOLOGY = "technology"
    REGULATION = "regulation"
    ORGANIZATIONAL = "organizational"
    HYBRID = "hybrid"


class ConversationTurn(BaseModel):
    question: str
    answer: str
    turn_number: int


class DiscoveryOutput(BaseModel):
    customer_stated_problem: str = Field(
        description="Müşterinin kendi ifadeleriyle tanımladığı problem"
    )
    identified_business_problem: str = Field(
        description="Agent tarafından netleştirilmiş iş problemi"
    )
    hidden_root_risk: str = Field(
        description="Müşterinin ifade etmediği ama risk oluşturan kök problem"
    )
    chat_summary: str = Field(description="Tüm soru-cevap akışının özeti")
    conversation_turns: list[ConversationTurn] = Field(default_factory=list)


class ProblemNode(BaseModel):
    main_cause: str
    sub_causes: list[str]


class StructuredProblemTree(BaseModel):
    problem_type: ProblemType
    main_problem: str
    problem_tree: list[ProblemNode]


class ResearchSource(BaseModel):
    title: str
    url: str

class ActionItem(BaseModel):
    action: str
    timeline: str
    owner: str
    priority: str
    expected_outcome: str

class ActionPlan(BaseModel):
    short_term: list[ActionItem] = Field(description="0-3 ay")
    mid_term: list[ActionItem] = Field(description="3-6 ay")
    long_term: list[ActionItem]  = Field(description="6+ ay")
    quick_wins: list[str] = Field(description="Hemen yapilabilecek kucuk iyilestirmeler")
    risks: list[str] = Field(description="Olası riskler ve engeller")
    success_metrics: list[str] = Field(description="Başarı ölçütleri ve KPI'lar")

class BusinessReport(BaseModel):
    executive_summary: str = Field(description="Üst yönetim özeti")
    report_markdown: str = Field(description="Tam rapor Markdown formatında")
    generated_at: str = Field(description="Rapor oluşturma zamanı")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskDetail(BaseModel):
    """Detaylı risk analizi."""
    risk_name: str = Field(description="Risk adı")
    probability: RiskLevel = Field(description="Gerçekleşme olasılığı")
    impact: RiskLevel = Field(description="Etki seviyesi")
    early_warning_signs: list[str] = Field(description="Erken uyarı sinyalleri")
    mitigation_strategy: str = Field(description="Risk azaltma stratejisi")
    contingency_plan: str = Field(description="B planı - risk gerçekleşirse")


class RiskAnalysis(BaseModel):
    """Tüm risklerin detaylı analizi."""
    risks: list[RiskDetail] = Field(description="Detaylandırılmış riskler")
    overall_risk_level: RiskLevel = Field(description="Genel risk seviyesi")
    top_priority_risk: str = Field(description="En öncelikli risk")
class ResearchResult(BaseModel):
    content: str = ""
    sources: list[ResearchSource] = Field(default_factory=list)
    elapsed_seconds: float = 0
    error: str | None = None

    @computed_field
    @property
    def source_urls(self) -> list[str]:
        return [src.url for src in self.sources]

    @computed_field
    @property
    def is_successful(self) -> bool:
        return self.error is None and len(self.content) > 0
