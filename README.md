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
│  GREETING      → Selamlama/teşekkür, nazikçe karşıla│
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
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
MONGODB_URL=mongodb://mongodb:27017
DATABASE_NAME=agentic_db
```

### 2. Docker ile çalıştır
```bash
docker-compose up --build
```

### 3. Local olarak çalıştır
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 4. API dokümantasyonu
```
http://localhost:8000/docs  (local)
http://localhost:8001/docs  (docker)
```

## Agent Mimarisi

### Peer Agent
Sistemin kapı görevlisi. Her isteği karşılar ve 4 kategoriye ayırır:
- **DIRECT_ANSWER**: Business bilgi sorusu → Web'den arar, cevaplar
- **REDIRECT**: Business problemi → Discovery Agent'a yönlendirir
- **OUT_OF_SCOPE**: Business dışı → Kullanıcıyı yönlendirir
- **GREETING**: Selamlama/teşekkür → Nazikçe karşılık verir

Discovery tamamlandıktan sonra aynı session'da yeni soru gelirse Peer Agent otomatik devreye girer.

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

### Peer Agent — Business Bilgi Sorusu
```json
POST /api/v1/agent/execute
{
  "task": "Elektrikli araç sektöründeki trendler nelerdir?",
  "agent_type": "peer_agent"
}
```

### Peer Agent — Problem Yönlendirme
```json
POST /api/v1/agent/execute
{
  "task": "Satışlarım düşüyor, nedenini anlamak istiyorum",
  "agent_type": "peer_agent"
}
```

### Discovery Agent — Soru Cevap Akışı
```json
POST /api/v1/agent/execute
{
  "task": "3 aydır düşüyor, rakipler fiyat düşürdü",
  "agent_type": "discovery_agent",
  "session_id": "peer-agent-dan-gelen-session-id"
}
```

### Discovery Tamamlandıktan Sonra Yeni Soru
```json
POST /api/v1/agent/execute
{
  "task": "Teşekkürler, başka sorum var",
  "agent_type": "discovery_agent",
  "session_id": "ayni-session-id"
}
```
Discovery tamamlandıktan sonra gelen her istek otomatik olarak Peer Agent'a yönlendirilir.

## Teknoloji Seçimleri

| Teknoloji | Neden Seçildi |
|---|---|
| FastAPI | Async destek, otomatik dokümantasyon |
| LangGraph | Agent state yönetimi, modüler yapı |
| Groq (llama-3.3-70b-versatile) | Ücretsiz tier, çok hızlı yanıt süresi |
| Tavily | LangChain native web search entegrasyonu |
| MongoDB | Esnek JSON doküman yapısı, kolay loglama |

## LLM ve Prompt Mühendisliği

- **Model**: Groq llama-3.3-70b-versatile
  - Gemini 2.0 Flash ücretsiz tier limitleri nedeniyle Groq tercih edildi
  - Groq çok daha cömert ücretsiz limit sunuyor ve yanıt hızı çok yüksek
- **Temperature**: 0.3 — tutarlı ve odaklı cevaplar için düşük tutuldu
- **Prompt yapısı**: Her agent için ayrı, görev odaklı sistem promptu
- **Output parsing**: Structured format ile parse edilebilir çıktılar
- **Follow-up sorular**: Discovery Agent müşteri cevaplarına göre dinamik soru üretiyor

## Loglama Tercihi

İki katmanlı loglama kullanıldı:
- **Stdout**: Sistem logları (INFO, ERROR) — basit, yeterli, Docker loglarıyla uyumlu
- **MongoDB**: Konuşma ve görev logları — kalıcı kayıt, Pydantic şema ile yapılandırılmış

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
Implement edilecek olsaydı:
- `celery` ve `redis` kütüphaneleri eklenirdi
- Her istek direkt işlenmek yerine kuyruğa yazılırdı
- Worker ayrı bir container olarak çalışırdı
- Kullanıcı `task_id` ile sonucu sorgulardı

## CI/CD

GitHub Actions ile otomatik test ve deploy:
- Her `main` push'unda testler otomatik çalışır
- Testler geçince AWS CodeDeploy ile deploy tetiklenir
- `appspec.yml` ile sunucuda stop/install/start adımları yönetilir

## Test

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

## Production Önerileri

- **Rate limiting**: slowapi kütüphanesi ile
- **API versiyonlama**: /api/v1, /api/v2
- **Queue**: Celery + Redis
- **Monitoring**: Prometheus + Grafana
- **Auth**: JWT token
- **Session storage**: Şu an in-memory, production'da Redis'e taşınmalı