# Peer Agent Controlled Task Distribution API

Multi-agent sistem: Peer Agent, Business Sense Discovery ve Problem Structuring agent'larından oluşur.

## Mimari Diyagram
```
┌─────────────────────────────────────────────────────┐
│                   KULLANICI                         │
│         POST /api/v1/agent/execute                  │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                 PEER AGENT                          │
│         (Kapı Görevlisi / Router)                   │
│                                                     │
│  DIRECT_ANSWER → Web'den ara, cevapla               │
│  REDIRECT      → Discovery Agent'a yönlendir        │
│  OUT_OF_SCOPE  → Business dışı, yönlendir           │
└──────┬──────────────────────────┬───────────────────┘
       │                          │
       ▼                          ▼
┌──────────────┐        ┌─────────────────────────────┐
│ Direkt Cevap │        │   BUSINESS SENSE DISCOVERY  │
│ + Referanslar│        │         AGENT               │
└──────────────┘        │                             │
                        │  Soru-cevap akışı yürütür   │
                        │  Problem netleştirir        │
                        │  4 çıktı üretir             │
                        └─────────────┬───────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────────┐
                        │  PROBLEM STRUCTURING &      │
                        │  DIAGNOSIS AGENT            │
                        │                             │
                        │  Problem tipini belirler    │
                        │  Problem ağacı oluşturur    │
                        └─────────────┬───────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────────┐
                        │         MONGODB             │
                        │   (Tüm loglar kaydedilir)   │
                        └─────────────────────────────┘
```

## Kurulum ve Çalıştırma

### 1. .env dosyasını düzenle
```bash
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
MONGODB_URL=mongodb://mongodb:27017
DATABASE_NAME=agentic_db
```

### 2. Docker ile çalıştır
```bash
docker-compose up --build
```

### 3. API'yi test et
```bash
curl -X POST http://localhost:8000/api/v1/agent/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "Elektrikli araç sektöründeki trendler nelerdir?"}'
```

## Agent Mimarisi

### Peer Agent
Sistemin kapı görevlisi. Her isteği karşılar ve 3 kategoriye ayırır:
- **DIRECT_ANSWER**: Business bilgi sorusu → Web'den arar, cevaplar
- **REDIRECT**: Business problemi → Discovery Agent'a yönlendirir
- **OUT_OF_SCOPE**: Business dışı → Kullanıcıyı yönlendirir

### Business Sense Discovery Agent
Soru-cevap akışı ile problemi derinlemesine anlar. 4 çıktı üretir:
- Customer Stated Problem
- Identified Business Problem
- Hidden Root Risk
- Customer Chat Summary

### Problem Structuring & Diagnosis Agent
Discovery çıktılarını alır, problem ağacı oluşturur:
- Problem tipi (Growth, Cost, Operational vb.)
- Ana problem
- 3-5 ana neden, her biri için 2-3 alt neden

## API Kullanımı

### Peer Agent
```json
POST /api/v1/agent/execute
{
  "task": "Elektrikli araç sektöründeki trendler nelerdir?",
  "agent_type": "peer_agent"
}
```

### Discovery Agent (Soru-Cevap)
```json
POST /api/v1/agent/execute
{
  "task": "Satışlarım düşüyor",
  "agent_type": "discovery_agent",
  "session_id": "oturum-id-buraya"
}
```

## Teknoloji Seçimleri

| Teknoloji | Neden Seçildi |
|---|---|
| FastAPI | Async destek, otomatik dokümantasyon |
| LangGraph | Agent state yönetimi, modüler yapı |
| Gemini 1.5 Flash | Ücretsiz tier, hızlı yanıt |
| Tavily | LangChain native web search |
| MongoDB | Esnek JSON doküman yapısı |

## LLM ve Prompt Mühendisliği

- **Model**: Gemini 1.5 Flash — ücretsiz tier ile yeterli performans
- **Temperature**: 0.3 — tutarlı ve odaklı cevaplar için düşük tutuldu
- **Prompt yapısı**: Her agent için ayrı, görev odaklı sistem promptu
- **Output parsing**: Structured format ile parse edilebilir çıktılar

## Loglama Tercihi

İki katmanlı loglama kullanıldı:
- **Stdout**: Sistem logları (INFO, ERROR) — basit ve yeterli
- **MongoDB**: Konuşma ve görev logları — kalıcı kayıt, Pydantic şema ile

## Genişletilebilirlik

Yeni agent eklemek için:
1. `app/agents/` altına yeni dosya ekle
2. `app/models/schemas.py` içinde `AgentType` enum'una ekle
3. `app/api/routes.py` içinde yeni agent'ı çağır

## Queue Mimarisi (Planlanan)

Bu versiyonda implement edilmedi. Planlanan yapı:
```
API → Redis Queue → Celery Worker → Agent → MongoDB
```
Yüksek trafikte LLM çağrıları yavaş olduğundan queue kritik önem taşır.

## Test
```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

## Production Önerileri

- Rate limiting: slowapi kütüphanesi ile
- API versiyonlama: /api/v1, /api/v2
- Queue: Celery + Redis
- Monitoring: Prometheus + Grafana
- Auth: JWT token