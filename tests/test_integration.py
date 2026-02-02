# tests/test_integration.py

import time

import pytest
import requests

BASE_URL = "http://localhost:8000"
TIMEOUT_SHORT = 30
TIMEOUT_LONG = 180  # Full flow için artırıldı


def submit_task(task: str, session_id: str | None = None) -> str:
    payload = {"task": task}
    if session_id:
        payload["session_id"] = session_id

    response = requests.post(f"{BASE_URL}/v1/agent/execute", json=payload)
    assert response.status_code == 200, f"Submit failed: {response.text}"

    return response.json()["task_id"]


def wait_for_task(task_id: str, timeout: int = TIMEOUT_SHORT) -> dict:
    start = time.time()

    while time.time() - start < timeout:
        response = requests.get(f"{BASE_URL}/v1/tasks/{task_id}")
        data = response.json()

        if data["status"] in ["completed", "failed"]:
            return data

        time.sleep(2)

    raise TimeoutError(f"Task {task_id} timed out after {timeout}s")


def execute_and_wait(
    task: str, session_id: str | None = None, timeout: int = TIMEOUT_SHORT
) -> dict:
    task_id = submit_task(task, session_id)
    return wait_for_task(task_id, timeout)


class TestHealthCheck:

    def test_health_returns_ok(self):
        response = requests.get(f"{BASE_URL}/health")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "mongodb" in data
        assert "redis" in data


class TestErrorHandling:

    def test_empty_task_returns_400(self):
        response = requests.post(f"{BASE_URL}/v1/agent/execute", json={"task": ""})

        assert response.status_code in [400, 422]

    def test_invalid_session_returns_404(self):
        response = requests.post(
            f"{BASE_URL}/v1/agent/execute",
            json={"task": "Test mesajı", "session_id": "gecersiz-session-id"},
        )

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]


class TestNonBusinessFlow:

    def test_non_business_rejected(self):
        result = execute_and_wait("Bugün hava nasıl?")

        assert result["status"] == "completed"

        response = result["result"]
        assert response["intent"] == "non_business"
        assert response["is_complete"] == True
        assert response["requires_input"] == False


class TestBusinessProblemFlow:

    def test_discovery_starts_with_question(self):
        result = execute_and_wait("Satışlarımız son 3 ayda %30 düştü")

        assert result["status"] == "completed"

        response = result["result"]
        assert response["intent"] == "business_problem"
        assert response["requires_input"] == True
        assert response["is_complete"] == False
        assert len(response["message"]) > 10

    def test_discovery_continues_with_session(self):
        result1 = execute_and_wait("Müşteri şikayetleri arttı")
        session_id = result1["result"]["session_id"]

        assert result1["result"]["requires_input"] == True

        result2 = execute_and_wait("Teslimat gecikmeleri konusunda", session_id)

        assert result2["status"] == "completed"
        assert result2["result"]["session_id"] == session_id


class TestBusinessInfoFlow:

    @pytest.mark.slow
    def test_business_info_returns_sources(self):
        result = execute_and_wait(
            "Türkiye e-ticaret sektöründe lider şirketler kimler?",
            timeout=TIMEOUT_LONG
        )

        assert result["status"] == "completed"

        response = result["result"]
        assert response["intent"] == "business_info"
        assert response["is_complete"] == True
        assert response["data"] is not None
        assert "sources" in response["data"]


class TestFullWorkflowFlow:

    @pytest.mark.slow
    def test_full_flow_produces_all_outputs(self):
        """
        Tam akış testi: Peer → Discovery (multi-turn) → Structuring → ActionPlan → Risk → Report
        
        Bu test gerçek LLM çağrısı yapar, maliyet oluşturabilir.
        """
        # İlk istek - Discovery başlasın
        result1 = execute_and_wait("Şirketimizde müşteri şikayetleri çok arttı")
        session_id = result1["result"]["session_id"]

        assert result1["result"]["requires_input"] == True

        # Discovery cevapları - 5 tur simülasyonu
        answers = [
            "Teslimat gecikmeleri ve ürün kalitesi konusunda",
            "Son 6 ayda başladı",
            "Aylık ortalama 200 şikayet alıyoruz",
            "Henüz sistematik bir çözüm denemedik",
            "Evet, önce sebebi anlamak istiyorum",
        ]

        final_result = None
        for answer in answers:
            result = execute_and_wait(answer, session_id, timeout=TIMEOUT_LONG)

            if result["result"]["is_complete"]:
                final_result = result
                break

        # Tam akış tamamlanmalı
        assert final_result is not None, "Flow did not complete"
        assert final_result["status"] == "completed"

        response_data = final_result["result"]["data"]

        # Tüm çıktılar mevcut olmalı
        assert "discovery_output" in response_data, "Missing discovery_output"
        assert "problem_tree" in response_data, "Missing problem_tree"
        assert "action_plan" in response_data, "Missing action_plan"
        assert "risk_analysis" in response_data, "Missing risk_analysis"
        assert "business_report" in response_data, "Missing business_report"

        # Problem tree yapısı doğru olmalı
        tree = response_data["problem_tree"]
        assert "problem_type" in tree
        assert "main_problem" in tree
        assert len(tree["problem_tree"]) >= 1

        # Action plan yapısı doğru olmalı
        plan = response_data["action_plan"]
        assert len(plan["short_term"]) >= 1
        assert len(plan["risks"]) >= 1
        assert len(plan["success_metrics"]) >= 1

        # Risk analysis yapısı doğru olmalı
        risks = response_data["risk_analysis"]
        assert len(risks["risks"]) >= 1
        assert "overall_risk_level" in risks

        # Report yapısı doğru olmalı
        report = response_data["business_report"]
        assert len(report["executive_summary"]) > 50
        assert len(report["report_markdown"]) > 100