# tests/conftest.py

import pytest


@pytest.fixture
def sample_discovery_output():
    return {
        "customer_stated_problem": "Müşteri şikayetleri arttı",
        "identified_business_problem": "Teslimat ve kalite sorunları",
        "hidden_root_risk": "Tedarikçi yönetimi zayıf",
        "chat_summary": "5 soru-cevap ile analiz yapıldı",
        "conversation_turns": [
            {
                "question": "Şikayetler hangi konuda?",
                "answer": "Teslimat",
                "turn_number": 1,
            },
            {"question": "Ne zamandır var?", "answer": "3 aydır", "turn_number": 2},
        ],
    }


@pytest.fixture
def sample_problem_tree():
    return {
        "problem_type": "operational",
        "main_problem": "Teslimat Gecikmeleri",
        "problem_tree": [
            {
                "main_cause": "Depo Kapasitesi",
                "sub_causes": ["Yetersiz alan", "Kötü yerleşim"],
            },
            {
                "main_cause": "Lojistik Planlama",
                "sub_causes": ["Rota optimizasyonu yok", "Araç yetersiz"],
            },
        ],
    }


@pytest.fixture
def sample_action_plan():
    return {
        "short_term": [
            {
                "action": "Lojistik süreç analizi",
                "timeline": "2 hafta",
                "owner": "Operasyon",
                "priority": "high",
                "expected_outcome": "Darboğaz tespiti",
            },
        ],
        "mid_term": [
            {
                "action": "Yeni lojistik partner araştır",
                "timeline": "3 ay",
                "owner": "Tedarik Zinciri",
                "priority": "high",
                "expected_outcome": "Teslimat süresini kısalt",
            },
        ],
        "long_term": [
            {
                "action": "Otomasyon yatırımı",
                "timeline": "8 ay",
                "owner": "IT",
                "priority": "medium",
                "expected_outcome": "Verimlilik artışı",
            },
        ],
        "quick_wins": ["Şikayet hattı kur", "SMS bildirimi başlat"],
        "risks": ["Kaynak yetersizliği", "Tedarikçi direnci"],
        "success_metrics": ["Şikayetlerde %20 azalma", "Teslimat süresinde %15 iyileşme"],
    }


@pytest.fixture
def sample_risk_analysis():
    return {
        "risks": [
            {
                "risk_name": "Kaynak yetersizliği",
                "probability": "high",
                "impact": "critical",
                "early_warning_signs": ["Milestone gecikmeleri", "Ekip yorgunluğu"],
                "mitigation_strategy": "Önceliklendirme yap, kritik aksiyonlara odaklan",
                "contingency_plan": "Planı 2 faza böl",
            },
        ],
        "overall_risk_level": "high",
        "top_priority_risk": "Kaynak yetersizliği",
    }


@pytest.fixture
def sample_business_report():
    return {
        "executive_summary": "Şirket operasyonel sorunlar yaşıyor. Öncelikli aksiyon gerekli.",
        "report_markdown": "# Rapor\n\n## Özet\n...",
        "generated_at": "2026-02-01 15:30",
    }


@pytest.fixture
def sample_business_problem_state():
    return {
        "session_id": "test-session-123",
        "user_input": "Satışlarımız düşüyor",
        "intent": "business_problem",
        "peer_response": {
            "intent": "business_problem",
            "message": "Problem analizi gerekiyor",
            "route_to": "discovery",
        },
        "discovery_question": "Satış düşüşü ne zaman başladı?",
        "discovery_output": None,
        "awaiting_user_input": True,
        "problem_tree": None,
        "action_plan": None,
        "risk_analysis": None,
        "business_report": None,
        "current_agent": "discovery",
        "agent_flow": ["peer", "discovery"],
        "is_complete": False,
        "error": None,
    }


@pytest.fixture
def sample_non_business_state():
    return {
        "session_id": "test-session-456",
        "user_input": "Bugün hava nasıl?",
        "intent": "non_business",
        "peer_response": {
            "intent": "non_business",
            "message": "Bu sistem business konularında uzmanlaşmıştır.",
        },
        "discovery_question": None,
        "discovery_output": None,
        "awaiting_user_input": False,
        "problem_tree": None,
        "action_plan": None,
        "risk_analysis": None,
        "business_report": None,
        "current_agent": "peer",
        "agent_flow": ["peer"],
        "is_complete": True,
        "error": None,
    }


@pytest.fixture
def sample_completed_state(
    sample_discovery_output, sample_problem_tree, sample_action_plan,
    sample_risk_analysis, sample_business_report
):
    return {
        "session_id": "test-session-789",
        "user_input": "Son cevap",
        "intent": "business_problem",
        "peer_response": None,
        "discovery_question": None,
        "discovery_output": sample_discovery_output,
        "awaiting_user_input": False,
        "problem_tree": sample_problem_tree,
        "action_plan": sample_action_plan,
        "risk_analysis": sample_risk_analysis,
        "business_report": sample_business_report,
        "current_agent": "report",
        "agent_flow": ["peer", "discovery", "structuring", "action_plan", "risk", "report"],
        "is_complete": True,
        "error": None,
    }