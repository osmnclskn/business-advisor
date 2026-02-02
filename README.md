# Business Advisor API

Çok ajanlı iş danışmanlığı sistemi. İş problemlerini analiz eder, kök nedenleri tespit eder, aksiyon planı oluşturur ve risk değerlendirmesi yapar.

## İçindekiler

- [Özellikler](#özellikler)
- [Mimari](#mimari)
- [Agent Akışı](#agent-akışı)
- [LLM Seçimleri](#llm-seçimleri)
- [Prompt Mühendisliği](#prompt-mühendisliği)
- [Kurulum](#kurulum)
- [API Kullanımı](#api-kullanımı)
- [Örnek Senaryo](#örnek-senaryo)
- [Test](#test)
- [Deployment](#deployment)
- [Geliştirme Notları](#geliştirme-notları)

## Özellikler

- 6 aşamalı analiz pipeline'ı
- Multi-turn konuşma desteği
- Asenkron task işleme (Celery)
- Rate limiting
- Structured JSON çıktılar

## Mimari

### Sistem Diyagramı

![Business Advisor System Architecture](docs/architecture.png)

Diyagram şu bileşenleri göstermektedir:

| Katman | Renk | Bileşenler |
|--------|------|------------|
| **API Layer** | Sarı | FastAPI :8000, Endpoints, SlowAPI Rate Limiting, Pydantic Validation, Error Handler |
| **Redis Layer** | Kırmızı | Session Store, Task Queue, Task Results, Rate Limits |
| **Background Processing** | Yeşil | Celery Worker (concurrency: 4, timeout: 5min) |
| **LangGraph Workflow** | Mor | 6 Agent Pipeline + Tavily Research API |
| **Data Layer** | Mavi | MongoDB :27017 (conversations, checkpoints, sessions) |

### Basit Akış
```
┌─────────────┐
│ API Consumer│
└──────┬──────┘
       │
       ▼
┌─────────────────┐     ┌─────────────┐     ┌─────────────┐
│  FastAPI + Rate │────▶│    Redis    │────▶│   Celery    │
│    Limiting     │     │   (Queue)   │     │   Worker    │
└─────────────────┘     └─────────────┘     └──────┬──────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │  LangGraph  │
                                            │  Workflow   │
                                            └──────┬──────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │   MongoDB   │
                                            └─────────────┘
```

### Neden Asenkron?

LLM çağrıları ve web araştırması 30-60 saniye sürebilir. Senkron işlemde HTTP timeout riski var. Celery ile task queue'ya atılır, client polling ile sonucu alır.

### Servisler

| Servis | Port | Rol |
|--------|------|-----|
| FastAPI | 8000 | REST API |
| Redis | 6379 | Queue, session, rate limit |
| MongoDB | 27017 | Log, checkpoint |
| Celery | - | Background worker |

### Neden MongoDB?

PostgreSQL yerine MongoDB tercih edildi:

- **Document model:** Conversation data'sı doğal olarak nested JSON yapısında. Her turn, her agent çıktısı iç içe document olarak saklanıyor. Relational model'de bu 5-6 tablo ve JOIN gerektirir.
- **Esnek schema:** Agent'lar geliştikçe çıktı yapıları değişiyor. MongoDB'de migration yapmadan yeni field eklenebilir.
- **LangGraph entegrasyonu:** `langgraph-checkpoint-mongodb` paketi hazır. PostgreSQL için manuel implementasyon gerekir.
- **Okuma ağırlıklı:** Bu sistemde yazma az, okuma çok. MongoDB'nin replica set'leri ile okuma scale edilebilir.

### Neden Redis?

Tek Redis instance üç farklı iş görüyor:

- **Session store:** Multi-turn conversation state'i (TTL: 1 saat)
- **Celery broker:** Task queue
- **Rate limiting:** SlowAPI backend'i (multi-instance uyumlu)

Memcached alternatifti ama rate limiting için sorted set gibi veri yapıları gerekti, Redis bunu native destekliyor.

## Agent Akışı
```
User Input
    │
    ▼
┌─────────┐
│  Peer   │──▶ business_info ──▶ Tavily Research ──▶ Cevap + Kaynaklar
│ (GPT)   │
└────┬────┘──▶ non_business ──▶ Kibarca Reddet
     │
     │ business_problem
     ▼
┌───────────┐
│ Discovery │ ◀──▶ 5 tur soru-cevap
│ (Claude)  │
└─────┬─────┘
      │
      ▼
┌─────────────┐
│ Structuring │──▶ Problem Ağacı
│  (Gemini)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ActionPlan  │──▶ Kısa/Orta/Uzun Vade Aksiyonlar
│  (Gemini)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Risk     │──▶ Risk Analizi + Mitigation
│  (Claude)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Report    │──▶ Executive Summary + Markdown Rapor
│   (GPT)     │
└─────────────┘
```

### Çıktı Yapısı
```
├── discovery_output
│   ├── customer_stated_problem
│   ├── identified_business_problem
│   ├── hidden_root_risk
│   └── conversation_turns[]
│
├── problem_tree
│   ├── problem_type
│   ├── main_problem
│   └── causes[] → sub_causes[]
│
├── action_plan
│   ├── short_term[] (0-3 ay)
│   ├── mid_term[] (3-6 ay)
│   ├── long_term[] (6-12 ay)
│   ├── quick_wins[]
│   └── success_metrics[]
│
├── risk_analysis
│   ├── risks[] → probability, impact, mitigation
│   └── overall_risk_level
│
└── business_report
    ├── executive_summary
    └── report_markdown
```

## LLM Seçimleri

| Agent | Model | Temp | Görev |
|-------|-------|------|-------|
| Peer | GPT-5.1 | 0.3 | Intent sınıflandırma |
| Discovery | Claude Sonnet 4.5 | 0.7 | Problem keşfi (5 tur) |
| Structuring | Gemini 2.5 Flash | 0.5 | Problem ağacı |
| ActionPlan | Gemini 2.5 Flash | 0.6 | Aksiyon planı |
| Risk | Claude Sonnet 4.5 | 0.5 | Risk değerlendirme |
| Report | GPT-5.1 | 0.4 | Rapor oluşturma |

### Neden Bu Modeller?

Her agent için model seçimi, o görevin doğasına göre yapıldı:

**GPT-5.1 (Peer, Report):** Classification ve formatting task'larında tutarlı. Peer agent'ta intent sınıflandırma %98 accuracy ile çalışıyor. Report agent'ta markdown formatting kalitesi yüksek.

**Claude Sonnet 4.5 (Discovery, Risk):** Multi-turn conversation'da context'i kaybetmiyor. Discovery agent 5 tur boyunca önceki cevapları hatırlayıp ilişkili sorular üretiyor. Risk agent'ta reasoning kalitesi önemli, Claude burada güçlü.

**Gemini 2.5 Flash (Structuring, ActionPlan):** Structured JSON output'ta hızlı ve tutarlı. Problem ağacı gibi nested yapılarda schema'ya sadık kalıyor. Maliyet-performans dengesi iyi.

### Temperature Seçimleri

- **0.3 (Peer):** Deterministic olmalı, aynı input aynı intent vermeli
- **0.5 (Structuring, Risk):** Dengeli, yaratıcılık ve tutarlılık arası
- **0.6-0.7 (Discovery, ActionPlan):** Yaratıcı sorular ve öneriler için

## Prompt Mühendisliği

Promptlar `app/prompts/` altında YAML formatında tutuluyor. Kod değişikliği yapmadan prompt güncellenebilir.

### Prompt Dosya Yapısı
```yaml
system: |
  [Rol tanımı]
  [Görev açıklaması]
  [Kısıtlamalar]
  [Few-shot örnekler]

user: |
  [Input template - {variable} formatında]
  [Output format talimatı]

temperature: 0.5
max_tokens: 1000
```

### Kullanılan Teknikler

**Few-shot Learning:** Her prompt'ta 2-3 örnek var. Model ne yapacağını açıklamadan değil, örnekten öğreniyor.
```yaml
# Örnek: peer_classify.yaml
system: |
  Kullanıcı mesajlarını kategorize et.
  
  ÖRNEKLER:
  
  Kullanıcı: "Rakiplerimiz kimler?"
  Kategori: business_info
  
  Kullanıcı: "Satışlar düşüyor"
  Kategori: business_problem
  
  Kullanıcı: "Hava nasıl?"
  Kategori: non_business
```

**Chain-of-thought:** Karmaşık görevlerde adım adım düşünme.
```yaml
# Discovery agent'ta reasoning
system: |
  Önce düşün:
  1. Müşteri ne söyledi?
  2. Hangi bilgi eksik?
  3. Bu bilgiyi almak için en iyi soru ne?
  
  Sonra soruyu yaz.
```

**Structured Output:** JSON schema ile çıktı formatı zorlama.
```yaml
# Structuring agent JSON output
system: |
  ÇIKTI FORMATI (sadece JSON):
  {
    "problem_type": "Growth|Cost|Operational|...",
    "main_problem": "string",
    "problem_tree": [
      {"main_cause": "string", "sub_causes": ["string"]}
    ]
  }
```

**Negative Examples:** Yapılmaması gerekenleri gösterme.
```yaml
system: |
  YAPMA:
  - Çözüm önerme (sadece soru sor)
  - Birden fazla soru sorma
  - Kullanıcıyı yönlendirme
```

### Neden YAML?

- **Versiyon kontrolü:** Prompt değişiklikleri git history'de görünür
- **Kod ayrımı:** Prompt mantığı Python'dan bağımsız
- **Kolay test:** Farklı prompt versiyonları A/B test edilebilir
- **Non-technical edit:** Prompt'ları düzenlemek için Python bilmek gerekmiyor

## Kurulum

### Gereksinimler

- Python 3.12+
- Docker & Docker Compose
- Poetry

### Adımlar
```bash
git clone https://github.com/username/business-advisor.git
cd business-advisor

cp .env.example .env
# .env dosyasını düzenle (API key'ler)

docker compose up -d --build
```

### Environment Variables
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...
TAVILY_API_KEY=tvly-...

MONGODB_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379/0
```

### Health Check
```bash
curl http://localhost:8000/health
```

## API Kullanımı

### Endpoint'ler

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/v1/agent/execute` | Task gönder |
| GET | `/v1/tasks/{task_id}` | Sonuç sorgula |
| GET | `/v1/sessions/{session_id}` | Session durumu |
| GET | `/health` | Sağlık kontrolü |

### Rate Limit

| Endpoint | Limit | Gerekçe |
|----------|-------|---------|
| `/v1/agent/execute` | 20/dakika | Her istek LLM API çağrısı |
| `/v1/tasks/{id}` | 60/dakika | Polling için yeterli |
| `/v1/sessions/{id}` | 30/dakika | Debug amaçlı |

## Örnek Senaryo

### Non-Business
```bash
curl -X POST http://localhost:8000/v1/agent/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "Bugün hava nasıl?"}'
```
```json
{
  "intent": "non_business",
  "message": "Bu sistem iş problemleri için tasarlandı...",
  "is_complete": true
}
```

### Business Info
```bash
curl -X POST http://localhost:8000/v1/agent/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "Türkiye e-ticaret sektöründe öne çıkan şirketler hangileri?"}'
```

Tavily Research API ile detaylı rapor döner (20+ kaynak, market share verileri, inline citation'lar).

### Business Problem (Full Cycle)

**1. Başlangıç:**
```json
POST /v1/agent/execute
{"task": "Müşteri şikayetleri son 6 ayda çok arttı"}
```

**2. Discovery (5 tur):**

| Tur | Soru | Cevap |
|-----|------|-------|
| 1 | Şikayetler hangi konularda? | Teslimat ve kalite |
| 2 | Bunlar bağlantılı mı? | Evet, yeni tedarikçiden sonra |
| 3 | Tedarikçi geçişi nasıl oldu? | Hızlı karar, kalite kontrol yok |
| 4 | Kim karar verdi? | Satın alma ve CFO |
| 5 | Ne kaçırıldı? | Kapasite, sertifikalar |

Her turda `session_id` ile devam edilir:
```json
POST /v1/agent/execute
{
  "task": "Teslimat ve kalite konusunda",
  "session_id": "9a4cef44-..."
}
```

**3. Final Çıktı:**

<details>
<summary>Tam Response</summary>
```json
{
  "discovery_output": {
    "customer_stated_problem": "Müşteri şikayetleri arttı",
    "identified_business_problem": "Tedarikçi geçişinde due diligence yapılmadı",
    "hidden_root_risk": "Departmanlar arası iletişim kopukluğu"
  },
  "problem_tree": {
    "problem_type": "hybrid",
    "main_problem": "Müşteri Şikayetlerinde Artış",
    "problem_tree": [
      {"main_cause": "Yetersiz Tedarikçi Yönetimi", "sub_causes": ["..."]},
      {"main_cause": "Hatalı Karar Alma", "sub_causes": ["..."]},
      {"main_cause": "İletişim Eksikliği", "sub_causes": ["..."]}
    ]
  },
  "action_plan": {
    "short_term": ["Acil kalite kontrol", "Haftalık koordinasyon"],
    "mid_term": ["Due diligence süreci", "Alternatif tedarikçi"],
    "long_term": ["ERP entegrasyonu", "Departman hedef uyumu"],
    "quick_wins": ["Şikayet kategorize", "Tedarikçi denetimi"],
    "success_metrics": ["Şikayetlerde %20 düşüş", "Teslimat iyileşmesi"]
  },
  "risk_analysis": {
    "overall_risk_level": "medium",
    "top_priority_risk": "Tedarikçi direnci"
  },
  "business_report": {
    "executive_summary": "Şirket müşteri şikayetleriyle karşı karşıya...",
    "report_markdown": "# Rapor\n\n## Özet\n..."
  }
}
```

</details>

## Test
```bash
# Unit test
poetry run pytest tests/test_unit.py -v

# Integration test
docker compose up -d
poetry run pytest tests/test_integration.py -v
```

**Sonuç:** 19 passed

### Test Kapsamı

| Modül | Test Sayısı |
|-------|-------------|
| DiscoveryOutputStructure | 2 |
| ProblemTreeStructure | 3 |
| ActionPlanStructure | 3 |
| RiskAnalysisStructure | 3 |
| BusinessReportStructure | 2 |
| AgentFlowLogic | 4 |
| SessionStateLogic | 2 |

### Test Kapsamını Artırma Önerileri

Mevcut testler temel yapıları doğruluyor. Production için ek testler:

**Edge Case Testleri:**
- Boş input, çok uzun input (10K+ karakter)
- Özel karakterler, SQL injection denemeleri
- Geçersiz session_id, expire olmuş session

**LLM Mock Testleri:**
- Gerçek API çağrısı yapmadan unit test
- Farklı LLM response senaryoları (timeout, rate limit, malformed JSON)
- Deterministic test için fixture'lar

**Load Testing:**
- Locust ile concurrent request testi
- Rate limiting davranışı doğrulama
- Redis/MongoDB bottleneck tespiti

**E2E Test Otomasyonu:**
- Tam 5 turlu discovery senaryosu
- Farklı problem tipleri (Growth, Cost, Operational)
- Session timeout ve recovery

**Contract Testing:**
- Pydantic model değişikliklerinde API uyumluluğu
- Backward compatibility kontrolü

## Deployment

### Docker
```bash
docker compose up -d
```

### CI/CD

GitHub Actions ile:
- Push'ta unit test
- Main branch'e merge'de deploy

## Geliştirme Notları

### Web Araştırma Stratejisi

Tavily API iki modda çalışabiliyor:

| Mod | Süre | Kaynak | Kullanım |
|-----|------|--------|----------|
| Research | 30-45sn | 20+ | Detaylı rapor, varsayılan |
| Search | 1-3sn | 3-5 | Hızlı cevap, basit sorular |

Sistem şu an Research modunda çalışıyor (daha kapsamlı). İleride query complexity'ye göre otomatik seçim eklenebilir.

### İyileştirme Fikirleri

**Kısa Vadeli:**
- API key authentication
- Request validation detaylandırma
- Search/Research otomatik seçimi

**Orta Vadeli:**
- Response caching (sık sorulan sorular)
- Prometheus + Grafana monitoring
- WebSocket ile streaming response

**Uzun Vadeli:**
- Multi-tenancy (organization bazlı izolasyon)
- Conversation history (geçmiş konuşmalara erişim)
- PDF export

## Proje Yapısı
```
business-advisor/
├── app/
│   ├── agents/
│   │   ├── peer.py
│   │   ├── discovery.py
│   │   ├── structuring.py
│   │   ├── action.py
│   │   ├── risk.py
│   │   ├── report.py
│   │   └── workflow.py
│   ├── models/
│   ├── prompts/
│   ├── main.py
│   ├── worker.py
│   └── ...
├── tests/
├── docs/
│   └── architecture.png
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Lisans

MIT