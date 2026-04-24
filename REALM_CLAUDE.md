# REALM — Astrological Swarm Intelligence Prediction Engine

## CLAUDE.md — Project Blueprint & Development Guide

> **Version:** 0.3.0
> **Created:** 2026-04-22
> **Last Updated:** 2026-04-23
> **Author:** Loth + Claude (Anthropic)
> **License:** Proprietary (commercial flexibility reserved)
> **Status:** Phase 1-6 + LLM integration + butterfly scenario panel complete. 464 tests passing, ruff clean.

---

## 0. CURRENT BUILD STATE (2026-04-24)

**Phases complete:**
- ✅ Phase 1 — core + astro + personality (rule-based) (143 tests)
- ✅ Phase 2 — demographics + culture + agents (65 tests)
- ✅ Phase 3 — simulation + network + transits + platforms + checkpoint (45 tests)
- ✅ Phase 4 — ingestion + KG + news channel + mood contagion (47 tests)
- ✅ Phase 4-LLM — Moonshot+OpenAI+Ollama backends, Mode B/C embedders, spotlight, prompts/ YAML (62 tests)
- ✅ Phase 5 — collective climate (outer planets, moon, eclipse, retrograde) (17 tests)
- ✅ Phase 6 — FastAPI + D3.js dashboard + Q&A predictor + report generator (38 tests)
- ✅ Phase 6b — scenario/what-if panel with baseline vs scenario side-by-side
- ✅ **Trait variance fix (2026-04-24)** — DAMPENING 0.12→0.40, opt-in soft-rescale calibration layer, Phase 1 diagnostic + Phase 4 validation (10K agents). Source σ 0.067 → post-cal 0.160, 23/24 traits at target. Jobs directional invariance preserved (Spearman ρ=0.999). `realm/personality/calibration.py` (7 tests), `scripts/diag_variance.py`, `scripts/validate_trait_distribution.py`.
- ✅ **InputAdapter layer (2026-04-24)** — pluggable trait sources above `IPersonalityEmbedder`. Three adapters: `AstrologicalAdapter` (wraps existing embedder, default), `BigFiveAdapter` (OCEAN scores → 24 traits via literature-sourced `data/personality/big_five_derivation.json` with DOI citations), `DemographicAdapter` (Hofstede+religion+region as primary signal, skips CulturalModifier to avoid double-counting). Config key: `realm.personality.adapter`. `realm/personality/adapters/` package, 37 new tests.
- ⏳ Phase 7 — POLYLIQ/ARGUS stubs (deferred)

**Current test total: 508 passing, ruff clean.**

**Architectural evolutions since the original 25 decisions:**
- **Ephemeris backend**: Kerykeion active (Swiss Ephemeris); Skyfield remains as the MSVC-free fallback.
- **LLM backends**: Moonshot primary, OpenAI fallback (Loth's credential set; no Claude yet). OpenAI-compatible SDK reaches both via `base_url` swap. `LLMRouter` wraps in `FallbackBackend` for runtime resilience. Reasoning-model quirks (`temperature=1`-only, `max_completion_tokens` rename) handled by proactive regex + reactive 400-retry loop.
- **News topic → agent posting coupling** (added during butterfly demo): `decide._topic_for()` now counts news posts in the feed and boosts matching topic weight scaled by agent's `herd_susceptibility - contrarian_tendency`. This was the missing link between injected news and observable agent behaviour — without it news only nudged mood traits.
- **Observer window**: `observe_topic_share(topic, window=None)` defaults to all-ticks observation; was previously last-5 which missed the butterfly effect because news expired from NewsChannel (memory_ticks=5) before the measurement window began.
- **Dampening data-driven**: `RuleBasedEmbedder.dampening` now reads from `config/astrology.yaml:rule_based_embedder.dampening` (default 0.40, up from 0.12). Chosen via 2D `(dampening × weight_floor)` sweep; floor found inert and omitted.
- **Agent.natal_chart is optional**: `NatalChart | None` when non-astrological input adapter produced the traits. Null guards added in `simulation/engine.py` (skip TransitModulator) and `output/dashboard_service.py` (emit null payload).
- **political_spectrum scope boundary**: explicitly excluded from astrological mapping and Big-Five derivation via `_excluded_by_design` blocks in `data/astro/*.json` and `data/personality/big_five_derivation.json`. REALM models temperament, not ideological preference.

**Known limitations (see memory `feedback_realm_honest_concerns.md` + `project_realm_validity_study_prep.md` for the full list):**
- Astrological mapping has no validation benchmark yet. Single anecdote (Steve Jobs via Mode B) supports the direction. Validity study (20-figure benchmark) is the next-priority investment.
- Big Five intercorrelations are near zero in REALM (|r|<0.1) vs literature ~0.20. Mapping treats traits as roughly independent; must be declared honestly, not hidden.
- 3 mapped traits (empathy, persuasion_skill, social_dominance) carry systematic positive bias (mean 0.85+ in raw pipeline) — calibration corrects but mapping rebalance is a future option.
- DemographicAdapter produces NARROWER variance than astrology (country→trait lookup), not wider as originally assumed. Standalone demographic mode is a weak parametric source; use in combination (future BlendedAdapter) or with per-agent variable signal.
- BigFiveAdapter has 5 domain traits with no literature-derived coefficients (fallback 0.5): herd_susceptibility, fomo_susceptibility, individualism, tradition_vs_progress, spirituality. 2 low-confidence derivations: contrarian_tendency, authority_compliance.
- Butterfly coefficients (herd_factor) are tuning knobs, not empirically calibrated.
- Scalability ceiling: ~500 agents × 10 ticks per minute. 10K+ agents need architectural work.
- Experience drift (decision #6, ±10%) is documented but not implemented.
- Checkpoint uses pickle — fragile across Python/dataclass version changes.
- Dashboard is functional but Loth flagged it as "demode" on 2026-04-23; redesign backlog lives in memory.

**How to resume:**
```bash
cd C:\Users\loth\desktop\realm
.venv\Scripts\activate
python -m pytest -q                                         # expect 508 passing
python scripts/serve_dashboard.py 500                       # http://127.0.0.1:8888/
python scripts/demo_butterfly.py                            # offline butterfly proof
python scripts/diag_variance.py 2000                        # variance sweep diagnostic
python scripts/validate_trait_distribution.py 10000         # calibration report (astrological)
python scripts/validate_trait_distribution.py 5000 --adapter=demographic   # demographic variance sanity
python scripts/check_jobs_directional.py                    # Jobs chart invariance check
```

---

## 1. PROJECT VISION

REALM, dünya ölçeğinde çoklu ajan simülasyonu ile tahmin üreten bir sürü zekası (swarm intelligence) motorudur. MiroFish'ten ilham alır ancak sıfırdan yazılmıştır. Temel farkı: **astrolojik natal harita ve transit hesaplamalarını kişilik embedding framework'ü olarak kullanması**, gerçekçi bir dünya nüfusu simüle etmesi ve kelebek etkisini modellemesidir.

### 1.1 Core Thesis
Her şey birbiriyle bağlıdır. Dünyanın bir yerindeki bir olay, başka bir yerde beklenmedik sonuçlar tetikler. REALM bunu, binlerce farklı kişiliğe sahip ajanın etkileşiminden ortaya çıkan kolektif davranışı gözlemleyerek modeller.

### 1.2 What REALM Is NOT
- Geleneksel bir istatistiksel tahmin modeli değildir
- Bir astroloji uygulaması değildir — astrolojiyi iki katmanda kullanır:
  - **Bireysel katman:** Natal harita → kişilik parametrelendirme aracı
  - **Kolektif katman:** Dönemin astrolojik iklimi (era transitleri, retro dönemleri, büyük geçişler) → simülasyon parametresi. Örn: Pluto Kova Burcu'na geçişi toplumsal dönüşüm eğilimini, Mars-Uranüs karesi kolektif volatiliteyi, Merkür retrosu iletişim kazalarını modelleyerek tahmin girdisi olarak kullanılır
- MiroFish fork'u değildir — bağımsız, özgün bir kod tabanıdır

---

## 2. CONVENTIONS

### 2.1 Code Language
- **Tüm kod İngilizce yazılır:** değişken adları, fonksiyon adları, class isimleri, dosya adları
- **Yorumlar Türkçe olabilir:** açıklayıcı comment'ler, docstring'lerin Türkçe versiyonları
- **Commit mesajları İngilizce**

```python
# Örnek:
class PersonalityEmbedder:
    """Natal harita verilerini davranış vektörüne dönüştürür."""

    def compute_risk_appetite(self, natal_chart: NatalChart) -> float:
        # Mars'ın burcu, evi ve aspektlerinden risk iştahı hesapla
        mars_sign = natal_chart.get_planet_sign("Mars")
        mars_house = natal_chart.get_planet_house("Mars")
        ...
```

### 2.2 Project Structure Convention
- Her modül kendi dizininde, kendi `__init__.py` ile
- Her modülde `interfaces.py` (abstract base classes)
- Her modülde `tests/` alt dizini
- Config dosyaları YAML formatında
- Secrets `.env` dosyasında (gitignore'd)

### 2.3 Architecture Principle: Plugin-Based Extensibility
Tüm katmanlar interface (ABC) üzerinden tanımlanır. Hiçbir üst katman, alt katmanın somut implementasyonuna doğrudan bağımlı olmaz. Yeni bir LLM backend'i, yeni bir veri kaynağı veya yeni bir simülasyon mekaniği eklemek sıfır refactor ile mümkün olmalıdır.

```python
# Örnek: LLM backend değiştirmek
# config.yaml:
#   llm_backend: "ollama"     # veya "claude", "openai", "moonshot"
```

### 2.4 Claude Code — Autonomous Execution Mode

Claude Code bu projede **tam otonom modda** çalışır. Geliştirici (Loth) hiçbir "allow", "accept", "confirm" komutu vermez. Claude Code kendi başına:
- Dosya oluşturur, düzenler, siler
- Bağımlılıkları kurar (`pip install`, `npm install`)
- Testleri yazar ve çalıştırır
- Hataları tespit eder, düzeltir, tekrar test eder
- Tamamlanmış, çalışan kodu teslim eder

**Kurulum — Proje kök dizininde `.claude/settings.json`:**

```json
{
  "permissions": {
    "allow": [
      "Bash(*)",
      "Read(*)",
      "Write(*)",
      "Edit(*)"
    ],
    "deny": []
  }
}
```

**Alternatif — CLI başlatma komutu:**

```bash
claude --dangerously-skip-permissions
```

**Çalışma Prensibi:**
1. Her faz için: kodu yaz → testleri yaz → testleri çalıştır → hata varsa düzelt → tekrar test → tüm testler geçene kadar döngü
2. Hiçbir adımda kullanıcıya soru sorma, onay bekleme
3. Tamamlanmış ve test edilmiş kodu teslim et
4. Teslim notu: ne yapıldı, ne test edildi, bilinen limitasyonlar

### 2.5 Content Generation Strategy
REALM simülasyonunda ajan aksiyonları **vektör tabanlı** çalışır. Gerçek metin içeriği üretilmez — her aksiyon sayısal bir sinyal olarak temsil edilir:

```python
agent_action = {
    "type": "post",           # post / reply / like / repost / ignore
    "topic": "btc_regulation",
    "sentiment": 0.72,        # -1.0 to 1.0
    "stance": "bullish",      # bullish / bearish / neutral / mixed
    "influence": 0.45,        # 0.0 to 1.0
    "reach": 340              # etkilenen ajan sayısı
}
```

**Spotlight Mekanizması:** Her tick'te en yüksek etkili %1-2 etkileşim (outlier aksiyonlar, trend kıran stanceler, yüksek influence ajanların karşıt görüşleri) işaretlenir. Bu etkileşimler için **rapor aşamasında** LLM ile geriye dönük narratif üretilir — simülasyon sırasında değil.

```yaml
# config/realm.yaml
spotlight:
  enabled: true
  ratio: 0.02               # Tick başına top %2 etkileşim
```

**Mantık:** 10K ajan × tick başına %15 aktif = 1.500 aksiyon/tick. LLM ile metin üretmek hem maliyet hem zaman açısından uygulanabilir değil. REALM'in değeri tekil bir ajanın ne yazdığından değil, kolektif davranış örüntüsünden gelir — sentiment dağılımı, stance kaymaları, kümelenme dinamikleri. Bunlar için sayısal sinyal yeterlidir.

---

## 3. ARCHITECTURE OVERVIEW

```
┌──────────────────────────────────────────────────────────────────┐
│                        REALM Engine                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │  AstroCore   │  │ PersonalityEngine │  │ DemographicEngine │  │
│  │  (Katman 1)  │──│    (Katman 2)     │──│    (Katman 3)     │  │
│  │  Kerykeion   │  │  Harita→Vektör    │  │  Dünya Nüfusu     │  │
│  └──────┬───────┘  └────────┬─────────┘  └────────┬───────────┘  │
│         │                   │                      │              │
│  ┌──────▼───────────────────▼──────────────────────▼───────────┐  │
│  │              AgentFactory (Katman 4)                         │  │
│  │  Demographic + Natal + Culture + Profession → Agent JSON    │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │              SimulationEngine (Katman 5)                     │  │
│  │  Ajan etkileşim loop'u + Transit modülasyonu                │  │
│  │  SeedIngestion (API feed + manuel) → Simülasyon tetikler    │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │              OutputLayer (Katman 6)                          │  │
│  │  Dashboard + Q&A Prediction + Report + Visualization        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────────────────────┐   │  │
│  │  │ Dashboard │ │  Report  │ │  Neural Synapse Graph     │   │  │
│  │  │ Mood/Sent │ │ PDF/MD   │ │  D3.js + NetworkX         │   │  │
│  │  └──────────┘ └──────────┘ └───────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              SignalInterface (Katman 7 — Future)             │  │
│  │  POLYLIQ / ARGUS entegrasyon sinyalleri                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Infrastructure                                  │  │
│  │  SQLite + JSON │ LLM Backend (pluggable) │ Config (YAML)    │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. DIRECTORY STRUCTURE

```
realm/
├── CLAUDE.md                          # Bu dosya
├── README.md                          # Proje açıklaması
├── pyproject.toml                     # Python proje konfigürasyonu
├── .env.example                       # Ortam değişkenleri şablonu
├── .gitignore
│
├── config/
│   ├── realm.yaml                     # Ana konfigürasyon
│   ├── demographics.yaml              # Nüfus dağılım parametreleri
│   ├── astrology.yaml                 # Astrolojik mapping kuralları
│   ├── cultural_dimensions.yaml       # Hofstede + bölgesel değerler
│   ├── expert_distribution.yaml       # Uzman dağılım modları (3 mod)
│   └── api_sources.yaml              # Seed data API kaynakları
│
├── realm/                             # Ana paket
│   ├── __init__.py
│   │
│   ├── core/                          # Paylaşılan temel bileşenler
│   │   ├── __init__.py
│   │   ├── interfaces.py             # Tüm abstract base class'lar
│   │   ├── config.py                 # YAML config loader
│   │   ├── database.py               # SQLite manager
│   │   ├── exceptions.py             # Özel exception sınıfları
│   │   ├── types.py                  # Type tanımları, dataclass'lar
│   │   ├── logging.py               # Loglama konfigürasyonu
│   │   └── monitoring.py            # Simülasyon sağlığı ve metrikler
│   │
│   ├── astro/                         # Katman 1: AstroCore
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IAstroEngine, ITransitCalculator
│   │   ├── natal_engine.py           # Kerykeion wrapper — natal harita
│   │   ├── transit_engine.py         # Transit hesaplama motoru
│   │   ├── aspect_calculator.py      # Aspekt hesaplama ve orb yönetimi
│   │   ├── dignity_analyzer.py       # Gezegen onur/düşüş/yükselme
│   │   ├── house_system.py           # Ev sistemi hesaplamaları
│   │   └── tests/
│   │       ├── test_natal.py
│   │       ├── test_transit.py
│   │       └── test_aspects.py
│   │
│   ├── personality/                   # Katman 2: PersonalityEngine
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IPersonalityEmbedder
│   │   ├── embedder.py               # Ana orchestrator
│   │   ├── rule_based.py             # Kural tabanlı mapping (Mod A)
│   │   ├── llm_based.py              # LLM destekli mapping (Mod B)
│   │   ├── hybrid.py                 # Hibrit yaklaşım (Mod C)
│   │   ├── trait_vector.py           # TraitVector dataclass & ops
│   │   ├── planet_traits.py          # Gezegen → trait mapping tabloları
│   │   ├── aspect_modifiers.py       # Aspekt etkisi katsayıları
│   │   └── tests/
│   │       ├── test_embedder.py
│   │       ├── test_traits.py
│   │       └── test_consistency.py
│   │
│   ├── demographics/                  # Katman 3: DemographicEngine
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IDemographicGenerator
│   │   ├── world_generator.py        # Dünya nüfusu üretici
│   │   ├── country_data.py           # Ülke nüfus/yaş/cinsiyet verileri
│   │   ├── profession_generator.py   # Meslek dağılımı
│   │   ├── name_generator.py         # Ülkeye uygun isim üretici
│   │   ├── socioeconomic.py          # Gelir/eğitim/marjinal profiller
│   │   └── tests/
│   │       └── test_demographics.py
│   │
│   ├── culture/                       # Katman 4: CulturalModifier
│   │   ├── __init__.py
│   │   ├── interfaces.py             # ICulturalModifier
│   │   ├── hofstede.py               # Hofstede 6 boyut implementasyonu
│   │   ├── regional_values.py        # Bölgesel değer sistemleri
│   │   ├── religion_worldview.py     # Dini/seküler dünya görüşleri
│   │   └── tests/
│   │       └── test_culture.py
│   │
│   ├── agents/                        # AgentFactory + Agent Model
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IAgent, IAgentFactory
│   │   ├── factory.py                # Ajan üretim fabrikası
│   │   ├── agent.py                  # Agent sınıfı (state + behavior)
│   │   ├── memory.py                 # Ajan hafıza sistemi
│   │   ├── decision.py               # Karar mekanizması (kural + LLM)
│   │   └── tests/
│   │       └── test_agents.py
│   │
│   ├── simulation/                    # Katman 5: SimulationEngine
│   │   ├── __init__.py
│   │   ├── interfaces.py             # ISimulationEngine, IPlatform
│   │   ├── engine.py                 # Ana simülasyon loop
│   │   ├── clock.py                  # Simülasyon saati, tick yönetimi
│   │   ├── platforms/                # Etkileşim platformları
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Platform ABC
│   │   │   ├── social_media.py       # Twitter/Reddit benzeri (Faz 1)
│   │   │   ├── news_channel.py       # Haber kanalı (Faz 2+)
│   │   │   ├── market.py             # Piyasa etkileşimi (Faz 2+)
│   │   │   └── parliament.py         # Meclis/forum (Faz 2+)
│   │   ├── transit_modulator.py      # Zaman bazlı davranış shift
│   │   ├── interaction_resolver.py   # Etkileşim çözümleyici
│   │   ├── event_bus.py              # Olay yayılımı (kelebek etkisi)
│   │   ├── network.py               # Ağ topolojisi (Small-world + Scale-free)
│   │   ├── checkpoint.py            # Checkpoint/fork/resume mekanizması
│   │   └── tests/
│   │       ├── test_engine.py
│   │       ├── test_modulator.py
│   │       └── test_network.py
│   │
│   ├── ingestion/                     # SeedIngestion
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IDataSource, ISeedProcessor
│   │   ├── manager.py                # Feed yönetim orchestrator
│   │   ├── sources/                  # Veri kaynağı adaptörleri
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # DataSource ABC
│   │   │   ├── rss_feed.py           # RSS/Atom feed (not: genişleme)
│   │   │   ├── news_api.py           # Haber API'leri
│   │   │   ├── crypto_api.py         # Kripto piyasa verisi
│   │   │   ├── social_trends.py      # Sosyal medya trend verisi
│   │   │   ├── economic_data.py      # Ekonomik göstergeler (FRED vb.)
│   │   │   └── manual_upload.py      # Manuel dosya yükleme
│   │   ├── entity_extractor.py       # Varlık ve ilişki çıkarma
│   │   ├── knowledge_graph.py        # Bilgi grafiği oluşturma
│   │   └── tests/
│   │       └── test_ingestion.py
│   │
│   ├── output/                        # Katman 6: OutputLayer
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IOutputRenderer, IDashboard
│   │   ├── dashboard.py              # Mood/sentiment dashboard
│   │   ├── predictor.py              # Q&A prediction + confidence
│   │   ├── report_generator.py       # Yapılandırılmış rapor (MD/PDF)
│   │   └── tests/
│   │       └── test_output.py
│   │
│   ├── visualization/                 # Nöral Synapse Görselleştirme
│   │   ├── __init__.py
│   │   ├── interfaces.py             # IVisualizer
│   │   ├── graph_builder.py          # NetworkX graf oluşturma
│   │   ├── neural_renderer.py        # D3.js nöral synapse render
│   │   ├── templates/                # HTML/JS şablonları
│   │   │   ├── synapse_view.html     # Ana görselleştirme sayfası
│   │   │   └── dashboard.html        # Dashboard UI
│   │   ├── static/                   # CSS, JS assets
│   │   │   ├── synapse.js            # D3.js synapse animasyonu
│   │   │   ├── dashboard.js          # Dashboard interaktivite
│   │   │   └── styles.css
│   │   └── tests/
│   │       └── test_visualization.py
│   │
│   ├── llm/                           # LLM Backend (Pluggable)
│   │   ├── __init__.py
│   │   ├── interfaces.py             # ILLMBackend
│   │   ├── ollama_backend.py         # Ollama (Qwen, Llama)
│   │   ├── claude_backend.py         # Anthropic Claude API
│   │   ├── openai_backend.py         # OpenAI API
│   │   ├── moonshot_backend.py       # Moonshot/Kimi API
│   │   ├── router.py                 # Hangi task → hangi backend
│   │   └── tests/
│   │       └── test_backends.py
│   │
│   ├── signal/                        # Katman 7: SignalInterface (Future)
│   │   ├── __init__.py
│   │   ├── interfaces.py             # ISignalEmitter
│   │   ├── polyliq_bridge.py         # POLYLIQ sinyal çıktısı (stub)
│   │   └── argus_bridge.py           # ARGUS sinyal çıktısı (stub)
│   │
│   └── utils/                         # Yardımcı araçlar
│       ├── __init__.py
│       ├── time_utils.py             # Zaman dönüşümleri, Julian Day
│       ├── geo_utils.py              # Koordinat, timezone yönetimi
│       ├── cache.py                  # Genel cache mekanizması
│       └── validators.py             # Girdi doğrulama
│
├── prompts/                           # LLM prompt şablonları (versiyonlu YAML)
│   ├── personality/
│   │   ├── system.yaml                # System prompt (kişilik analisti rolü)
│   │   └── user_template.yaml         # Natal harita → trait prompt şablonu
│   ├── report/
│   │   ├── summary.yaml               # Simülasyon özet raporu
│   │   ├── prediction.yaml            # Tahmin açıklama şablonu
│   │   └── prediction_tr.yaml         # Türkçe rapor şablonu
│   ├── spotlight/
│   │   └── narrative.yaml             # Spotlight ajan narratif üretimi
│   └── question_parser/
│       └── parse_question.yaml        # Q&A soru parse prompt'u
│
├── data/                              # Statik veri dosyaları
│   ├── countries.json                 # Ülke listesi + nüfus + koordinat
│   ├── cities.json                    # Ülke bazlı şehir listesi (top 20/ülke)
│   ├── birth_hour_weights.json        # Saat bazlı doğum dağılımı ağırlıkları
│   ├── names/                         # Ülkeye göre isim havuzları (Faker fallback)
│   │   ├── tr.json                    # Türk isimleri (Faker locale varsa gereksiz)
│   │   ├── us.json                    # Amerikan isimleri
│   │   ├── cn.json                    # Çin isimleri
│   │   └── ...                        # Faker kapsamadığı ülkeler için
│   ├── professions.json               # Meslek kategorileri + dağılımları
│   ├── hofstede_scores.json           # Ülke bazlı Hofstede skorları
│   └── astro/
│       ├── planet_trait_map.json      # Gezegen → trait mapping tablosu
│       ├── sign_modifiers.json        # Burç modifikasyon katsayıları
│       ├── house_meanings.json        # Ev anlamları ve etki alanları
│       └── aspect_weights.json        # Aspekt güç katsayıları
│
├── db/                                # SQLite veritabanı dosyaları
│   ├── realm.db                       # Ana veritabanı
│   └── migrations/                    # Şema migration'ları
│       └── 001_initial.sql
│
├── scripts/                           # Yardımcı scriptler
│   ├── generate_population.py         # Nüfus üretim scripti
│   ├── run_simulation.py              # Simülasyon çalıştırma
│   ├── export_report.py               # Rapor dışa aktarma
│   └── benchmark.py                   # Performans benchmark
│
├── notebooks/                         # Jupyter notebook'lar (analiz)
│   └── exploration.ipynb
│
└── tests/                             # Entegrasyon testleri
    ├── test_integration.py
    └── test_end_to_end.py
```

---

## 5. MODULE SPECIFICATIONS

### 5.1 AstroCore (realm/astro/)

**Amaç:** Natal harita ve transit hesaplamalarının tek doğruluk kaynağı.

**Bağımlılık:** `kerykeion` (Swiss Ephemeris tabanlı)

**Temel Sınıflar:**

```python
# interfaces.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

@dataclass
class PlanetPosition:
    """Bir gezegenin ekliptik pozisyonu."""
    name: str               # "Sun", "Moon", "Mars", ...
    longitude: float         # 0-360 derece
    latitude: float
    sign: str                # "Aries", "Taurus", ...
    sign_degree: float       # Burç içindeki derece (0-30)
    house: int               # 1-12
    is_retrograde: bool
    speed: float             # Derece/gün

@dataclass
class Aspect:
    """İki gezegen arası aspekt."""
    planet1: str
    planet2: str
    aspect_type: str         # "conjunction", "opposition", "trine", "square", "sextile"
    angle: float             # Gerçek açı
    orb: float               # Tam aspektten sapma
    is_applying: bool        # Yaklaşan mı, ayrılan mı

@dataclass
class NatalChart:
    """Tam natal harita verisi."""
    birth_datetime: datetime
    latitude: float
    longitude: float
    timezone: str
    planets: List[PlanetPosition]
    houses: List[float]      # 12 ev cusp derecesi
    aspects: List[Aspect]
    ascendant: float
    midheaven: float
    element_balance: Dict[str, float]   # fire, earth, air, water
    modality_balance: Dict[str, float]  # cardinal, fixed, mutable

@dataclass
class TransitSnapshot:
    """Belirli bir andaki transit durumu."""
    timestamp: datetime
    transiting_planets: List[PlanetPosition]
    active_transits: List[Aspect]        # Transit gezegen → natal gezegen
    moon_phase: str                       # "new", "waxing", "full", "waning"
    retrograde_planets: List[str]

class IAstroEngine(ABC):
    """Astroloji hesaplama motoru arayüzü."""

    @abstractmethod
    def calculate_natal_chart(
        self, birth_dt: datetime, lat: float, lon: float, tz: str
    ) -> NatalChart:
        ...

    @abstractmethod
    def calculate_transits(
        self, natal: NatalChart, target_dt: datetime
    ) -> TransitSnapshot:
        ...

    @abstractmethod
    def calculate_transit_range(
        self, natal: NatalChart, start_dt: datetime, end_dt: datetime,
        interval_hours: int = 24
    ) -> List[TransitSnapshot]:
        ...
```

**Kerykeion Entegrasyon Notları:**
- Kerykeion `AstrologicalSubject` nesnesi oluşturulur, sonuçlar bizim `NatalChart` dataclass'ına dönüştürülür
- Ev sistemi: Placidus (default, konfigüre edilebilir)
- Orb ayarları: konfigürasyondan okunur (astrology.yaml)
- Transit hesabında: simülasyon zamanında geçici bir `AstrologicalSubject` oluşturulur ve natal haritaya karşı aspektler hesaplanır

**Gök Cisimleri Konfigürasyonu:**

Varsayılan olarak 13 gök cismi hesaplanır: klasik 10 gezegen (Sun–Pluto) + North Node + South Node + Chiron. Genişleme config ile kontrol edilir:

```yaml
# config/astrology.yaml
celestial_bodies:
  core: true          # Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto
  nodes: true         # North Node (destiny/purpose), South Node (comfort zone/past)
  chiron: true        # Chiron (wound/healing axis)
  lilith: false       # Black Moon Lilith (Faz 2+)
  asteroids: false    # Ceres, Pallas, Juno, Vesta (Faz 2+)
```

Kerykeion tüm bu cisimleri destekler. Hesaplama maliyeti ihmal edilebilir düzeydedir — asıl maliyet trait mapping tablosunun genişlemesidir (YAML'dan okunduğu için yeni cisim eklemek konfigürasyon işidir).

### 5.2 PersonalityEngine (realm/personality/)

**Amaç:** Natal haritayı sayısal bir davranış vektörüne (TraitVector) dönüştürmek.

**TraitVector Tanımı:**

```python
@dataclass
class TraitVector:
    """Bir ajanın davranış parametreleri. Tüm değerler 0.0-1.0 arasında."""

    # --- Temel Kişilik (Big Five Benzeri) ---
    openness: float              # Yeniliğe açıklık
    conscientiousness: float     # Sorumluluk/düzen
    extraversion: float          # Dışa dönüklük
    agreeableness: float         # Uyumluluk
    neuroticism: float           # Duygusal kararsızlık

    # --- Karar Verme ---
    risk_appetite: float         # Risk iştahı (0=aşırı temkinli, 1=pervasız)
    analytical_depth: float      # Analitik derinlik vs sezgisel
    impulsivity: float           # Dürtüsellik
    patience: float              # Sabır, uzun vadeli düşünme

    # --- Sosyal Dinamik ---
    social_dominance: float      # Liderlik/baskınlık
    herd_susceptibility: float   # Sürü davranışına yatkınlık
    authority_compliance: float  # Otoriteye uyum
    contrarian_tendency: float   # Karşıtlık eğilimi
    empathy: float               # Empati kapasitesi

    # --- Finansal Davranış ---
    financial_optimism: float    # Mali iyimserlik
    loss_aversion: float         # Kayıptan kaçınma
    fomo_susceptibility: float   # FOMO (kaçırma korkusu)

    # --- İletişim ---
    communication_assertiveness: float  # İletişim kararlılığı
    persuasion_skill: float             # İkna yeteneği
    information_sharing: float          # Bilgi paylaşma eğilimi

    # --- Dünya Görüşü ---
    political_spectrum: float    # 0=sol, 0.5=merkez, 1=sağ
    tradition_vs_progress: float # 0=gelenekçi, 1=ilerici
    individualism: float         # 0=kolektivist, 1=bireyci
    spirituality: float          # Spiritüel/mistik eğilim

    def apply_modifier(self, modifiers: Dict[str, float]) -> 'TraitVector':
        """Transit veya kültürel modifikasyon uygula."""
        ...

    def to_dict(self) -> Dict[str, float]:
        ...

    def distance(self, other: 'TraitVector') -> float:
        """İki kişilik arası mesafe (benzerlik ölçümü)."""
        ...
```

**Mapping Yaklaşımı (3 Mod):**

| Mod | Açıklama | Kullanım |
|-----|----------|----------|
| A: Rule-based | Sabit tablolar: Mars Koç'ta → risk=0.85 | Default başlangıç |
| B: LLM-based | Natal harita JSON → LLM → trait vektörü | Yüksek kalite, yavaş |
| C: Hybrid | Kural tabanlı temel + LLM nüans katmanı | Önerilen production modu |

**Konfigürasyon:** `config/astrology.yaml` → `personality_mode: "rule_based" | "llm" | "hybrid"`

**Gezegen → Trait Mapping Özeti (Rule-Based Mod):**

| Gezegen | Birincil Trait'ler | İkincil |
|---------|-------------------|---------|
| Güneş | social_dominance, extraversion | individualism |
| Ay | neuroticism, empathy, herd_susceptibility | emotional reactivity |
| Merkür | analytical_depth, communication_assertiveness | information_sharing |
| Venüs | agreeableness, financial_optimism | empathy |
| Mars | risk_appetite, impulsivity | contrarian_tendency |
| Jüpiter | openness, financial_optimism | optimism |
| Satürn | conscientiousness, patience, authority_compliance | loss_aversion |
| Uranüs | contrarian_tendency, openness | tradition_vs_progress |
| Neptün | spirituality, empathy | herd_susceptibility |
| Pluto | social_dominance, risk_appetite | transformation |
| North Node | tradition_vs_progress, openness | life purpose direction |
| South Node | herd_susceptibility (inverse) | comfort zone patterns |
| Chiron | empathy, neuroticism | wound/healing axis |

Her gezegen etki gücü = f(burç, ev, aspektler, onur/düşüş durumu)

### 5.3 DemographicEngine (realm/demographics/)

**Amaç:** Gerçekçi dünya nüfusu üretmek.

**Veri Kaynakları:**
- UN World Population Prospects (ücretsiz, JSON)
- Dünya Bankası API (meslek/eğitim dağılımları)
- Hofstede Insights (kültürel boyutlar, açık veri)

**Nüfus Üretim Mantığı:**

```
1. Ülke havuzu oluştur (195 ülke, nüfusa orantılı ajan sayısı)
2. Her ülke için:
   a. Yaş dağılımı (piramide göre)
   b. Cinsiyet dağılımı
   c. Doğum tarihi + saati + lokasyonu üret
   d. Meslek ata (ülke ekonomisine göre)
   e. Eğitim seviyesi ata
   f. Sosyoekonomik katman ata
   g. Marjinal profil olasılığı (uyuşturucu bağımlısı, evsiz, suç geçmişi...)
3. İsim üret (ülke + cinsiyet + nesil bazlı)
```

**Ölçek Konfigürasyonu:**

```yaml
# config/demographics.yaml
population:
  total_agents: 10000       # Başlangıç (50000, 100000 olarak artırılabilir)
  distribution: "proportional"  # veya "enriched" veya "equal"
  mode: "static"             # "static" | "semi_dynamic" | "dynamic"
  experience_drift: true     # Deneyim birikimi ile hafif trait kayması
  max_drift_ratio: 0.10      # Base trait'ten max sapma: %10
  include_marginal: true
  marginal_ratio: 0.05      # Toplumun %5'i marjinal profil

birth_time:
  distribution: "realistic"  # "uniform" | "realistic"
  # Gerçekçi dağılım: sabah 08-12 pik, gece 02-05 düşük
  # Sezaryen/indüksiyon etkisi ile gündüz ağırlıklı (%60-65)

geography:
  granularity: "city"         # "city" | "country_center"
  cities_per_country: 20      # Ülke başına max şehir (data/cities.json)
  rural_offset_degrees: 1.0   # Kırsal nüfus: en yakın şehir çevresi ±N derece
  timezone_auto: true         # Koordinattan otomatik timezone (timezonefinder)
```

**Doğum Saati Dağılımı:**

Uniform dağılım yerine gerçek doğum istatistiklerine dayalı ağırlıklı dağılım kullanılır. Bu, Ascendant dağılımını gerçek topluma yaklaştırır:

```python
# Saat bazlı ağırlıklar (gerçek doğum istatistiklerinden)
hour_weights = [
    0.6, 0.5, 0.4, 0.4, 0.5, 0.6,   # 00-05 (gece, düşük)
    0.8, 1.0, 1.3, 1.4, 1.3, 1.2,   # 06-11 (sabah, yüksek — indüksiyon/sezaryen)
    1.1, 1.0, 1.0, 1.1, 1.0, 0.9,   # 12-17 (öğleden sonra)
    0.8, 0.7, 0.7, 0.7, 0.7, 0.6    # 18-23 (akşam, azalan)
]
birth_hour = rng.choice(24, p=normalize(hour_weights))
```

**Coğrafi Granülarite:** Her ülke için top 20 şehir (nüfusa orantılı dağılım, `data/cities.json`). Kalan nüfus → en yakın şehir çevresinde ±1 derece offset (kırsal nüfus şehirlerin etrafında yoğunlaşır). Timezone, `timezonefinder` kütüphanesi ile koordinattan otomatik çıkarılır.

**İsim Üretimi:** `Faker` kütüphanesi (50+ locale). Deterministik seed desteği ile reproducibility korunur. Faker'ın kapsamadığı ülkeler için bölgesel fallback:

```python
LOCALE_MAP = {"TR": "tr_TR", "US": "en_US", "CN": "zh_CN", "JP": "ja_JP", ...}
FALLBACK_MAP = {"AF": "fa_IR", "KZ": "ru_RU", ...}  # Locale yoksa bölgesel yakın
# Hiçbiri yoksa → "en_US" default
```

**Uzman Dağılımı (3 Mod):**

```yaml
# config/expert_distribution.yaml
expert_mode: "dynamic"  # "realistic" | "enriched" | "dynamic"

realistic:
  expert_ratio: 0.05        # %5 uzman
  # Kalan %95 genel halk

enriched:
  expert_ratio: 0.30        # %30 uzman (şişirilmiş)

dynamic:
  base_expert_ratio: 0.08   # Temel oran
  topic_boost_factor: 3.0   # Konuyla ilgili uzmanlar öne çıkar
  # Simülasyon konusu "kripto" ise → finans uzmanları 3x ağırlıklı
```

### 5.4 CulturalModifier (realm/culture/)

**Amaç:** Kültürel değer sistemlerini ajan davranışına entegre etmek.

**Hofstede 6 Boyut:**
1. Power Distance Index (PDI) — Güç mesafesi
2. Individualism vs Collectivism (IDV)
3. Masculinity vs Femininity (MAS)
4. Uncertainty Avoidance Index (UAI) — Belirsizlikten kaçınma
5. Long-Term Orientation (LTO)
6. Indulgence vs Restraint (IVR)

**Uygulama:**

```python
class CulturalModifier:
    def apply(self, trait_vector: TraitVector, country: str) -> TraitVector:
        """Ülke kültürel boyutlarını trait vektörüne uygula."""
        scores = self.get_hofstede_scores(country)

        # Örnek mapping:
        # Yüksek PDI → authority_compliance ↑, contrarian_tendency ↓
        # Yüksek IDV → individualism ↑, herd_susceptibility ↓
        # Yüksek UAI → risk_appetite ↓, conscientiousness ↑
        # Yüksek LTO → patience ↑, impulsivity ↓
        ...
```

### 5.5 SimulationEngine (realm/simulation/)

**Amaç:** Ajan etkileşim döngüsünü yönetmek.

**Tick Mekanizması:**

```
Her tick (default: 1 gün):
  1. Simülasyon saatini ilerlet
  2. TransitModulator: aktif transitleri hesapla, ajan trait'lerini modüle et
  3. SeedIngestion: yeni veri var mı kontrol et, varsa inject et
  4. Her platform için:
     a. Aktif ajanları seç (activity probability'e göre)
     b. Her aktif ajan için:
        - Mevcut konuları değerlendir (kişilik + kültür + transit filtresi)
        - Aksiyon seç: post / reply / like / repost / follow / ignore
        - Aksiyon uygula, sonuçları event_bus'a yayınla
  5. Global metrics güncelle (mood, sentiment, engagement)
  6. State snapshot'ı SQLite'a kaydet
```

**Catch-Up Mekanizması:**

```
Son çalıştırma: 2026-04-15
Şu an: 2026-04-22
→ 7 gün catch-up gerekiyor
→ Accelerated mode: normal simülasyonu 10x hızda çalıştır
→ Her tick'te tam transit hesaplanır (astrolojik doğruluk korunur)
→ Ajan etkileşimleri basitleştirilir (yalnız yüksek olasılıklı aksiyonlar)
→ Catch-up bitince normal hıza dön
```

**Kelebek Etkisi — EventBus:**

```python
class EventBus:
    """Olayların zincirleme yayılımını yönetir."""

    def emit(self, event: SimEvent):
        """
        Bir olay tetiklendiğinde:
        1. Doğrudan etkilenen ajanları belirle (aynı platform/konu)
        2. Dolaylı yayılım: ajan ağı üzerinden propagate et
        3. Cross-platform yayılım: haber → sosyal medya → piyasa
        4. İkincil etki: etkilenen ajanlar kendi aksiyonlarını tetikler
        5. Cross-platform yayılım kuralları:
           - social_media viral post → news_channel (threshold: influence > 0.8, reach > 1000)
           - news_channel breaking → social_media (otomatik, tüm ajanlar görebilir)
           - social_media/news sentiment shift → market sentiment (gecikme: 1-3 tick)
           - market büyük hareket → news_channel → social_media (cascade)
           - parliament/forum tartışması → news_channel (threshold: çok taraflı katılım + yüksek sentiment polarizasyonu) [Faz 2+]
        6. Propagation delay: platformlar arası gecikme (config ile ayarlanabilir)
        """
        ...

**Determinizm ve Seed Yönetimi:**

Tüm rastgelelik tek bir `master_seed` ile kontrol edilir. Aynı seed = aynı nüfus = aynı kararlar = aynı sonuç.

```yaml
# config/realm.yaml
simulation:
  master_seed: 42
```

```python
# Kullanım:
rng = np.random.default_rng(master_seed)
# Her alt-sistem kendi seed'ini master'dan türetir
agent_rng = np.random.default_rng(master_seed + agent_id_hash)
```

**Not:** LLM backend kullanıldığında (Mod B/C kişilik üretimi, rapor aşaması) LLM temperature > 0 ise deterministiklik kırılır. Çözüm: LLM ile üretilen sonuçlar cache'lenir — aynı seed = aynı cache = aynı sonuç. Simülasyon loop'u kendisi %100 deterministiktir (vektör tabanlı, LLM call yok).

**Checkpoint & Fork Mekanizması:**

Crash recovery ve simülasyon dallanması (branching) aynı altyapıyı paylaşır:

```python
class SimulationEngine:
    def checkpoint(self) -> str:
        """Tam state snapshot'ı SQLite'a kaydet. Checkpoint dosya yolunu döndür."""
        ...

    def fork(self, checkpoint_path: str, branch_seed_offset: int = 0) -> 'SimulationEngine':
        """Checkpoint'ten yeni bir simülasyon dalı başlat."""
        ...

    def resume(self, checkpoint_path: str):
        """Crash sonrası son checkpoint'ten devam et."""
        ...
```

```yaml
# config/realm.yaml
simulation:
  checkpoint_interval: 10     # Her 10 tick'te otomatik checkpoint
  max_checkpoints: 5          # Disk alanı yönetimi, eski checkpoint'lar silinir
  checkpoint_dir: "db/checkpoints/"
```

**Branching (Faz 3+):** Aynı state'ten farklı senaryoları paralel çalıştırma — "savaş çıkarsa" vs "çıkmazsa" karşılaştırması. Astrolojik kalibrasyon için de kullanılır: gerçek transit takvimi vs hayali transit senaryosu.

**Ajan Karar Algoritması:**

Her tick'te ajan davranışı trait vektörüne dayalı probabilistik kararlarla belirlenir:

```
1. Aktif ajan seçimi:
   activity_probability = f(extraversion, current_mood, transit_boost)
   → Yüksek extraversion + pozitif transit = daha aktif

2. Konu değerlendirme:
   relevance = f(profession, expertise, trait_vector, cultural_modifier)
   → Finans uzmanı kripto haberi = yüksek relevance

3. Aksiyon seçimi (probabilistik):
   - post olasılığı   ∝ extraversion × communication_assertiveness
   - reply olasılığı  ∝ agreeableness × empathy (veya contrarian_tendency)
   - like/repost      ∝ herd_susceptibility × topic_relevance
   - ignore           ∝ (1 - topic_relevance)

4. Sentiment belirleme:
   sentiment = base_trait + transit_modifier + cultural_modifier + recent_events_impact
```
```

### 5.6 TransitModulator (realm/simulation/transit_modulator.py)

**Amaç:** Simülasyon zamanına göre ajan davranışlarını astrolojik transitlerle modüle etmek. İki katmanlı çalışır: bireysel (natal'e transit) ve kolektif (dönemin astrolojik iklimi).

**Çalışma Prensibi:**

```
Simülasyon zamanı: t

=== KATMAN 1: KOLEKTİF ASTROLOJİK İKLİM (tüm ajanları etkiler) ===
  1. Era transitleri: yavaş gezegen burç geçişleri
     - Pluto Kova'da (2024-2044) → toplumsal dönüşüm, teknoloji devrimi,
       otorite yapılarının çözülmesi → tüm ajanlar: contrarian_tendency ↑,
       tradition_vs_progress ↑
     - Neptune Koç'a geçişi (2025-2039) → bireysel spiritüellik,
       kolektif illüzyon riski → spirituality ↑, herd_susceptibility ↑
  2. Orta vadeli geçişler:
     - Saturn burç geçişleri (~2.5 yıl) → sektörel disiplin/kısıtlama
     - Jupiter burç geçişleri (~1 yıl) → sektörel genişleme/iyimserlik
  3. Kısa vadeli kolektif etki:
     - Mars-Uranüs karesi → küresel volatilite spike
     - Venüs-Jüpiter kavuşumu → piyasa iyimserliği dalgası
     - Merkür retrosu → iletişim kazaları, geciken anlaşmalar
  4. Ay fazı: tüm ajanlar üzerinde hafif global modifier
     - Yeni Ay → yeni başlangıçlar, risk alma eğilimi ↑
     - Dolunay → duygusal yoğunluk, çatışma olasılığı ↑
  5. Tutulmalar: yüksek etkili kolektif olaylar, ilgili burç aksında
     amplifikasyon

=== KATMAN 2: BİREYSEL TRANSİTLER (ajan bazlı) ===
  Her ajan için:
  1. Natal haritaya göre aktif transitleri hesapla (AstroCore üzerinden)
  2. Her aktif transit için etki katsayılarını belirle:
     - Transit tipi (conjunction=güçlü, trine=yumuşak, square=gergin)
     - Transit gezegen hızı (yavaş=uzun etki, hızlı=kısa etki)
     - Orb (tam aspekte yakınlık)
  3. Katsayıları ilgili trait'lere uygula:
     - Mars transit natal Moon square → emotional_reactivity *= 1.4
     - Jupiter transit natal Sun conjunction → financial_optimism *= 1.3
     - Saturn transit natal Mars → impulsivity *= 0.7, patience *= 1.3
  4. Retro gezegenler: ilgili alanları yavaşlat/içselleştir

=== SONUÇ: Nihai trait vektörü ===
  final_trait = base_trait × cultural_mod × collective_astro_mod × individual_transit_mod
```

**Performans Optimizasyonu:**

Transit hesaplaması ayrıştırılmış mimaride çalışır — Kerykeion tick başına yalnızca 1 kez çağrılır:

```
Tick başı:
  1. Transit gezegen pozisyonları = calc_transit_once(sim_time)
     → 1 Kerykeion call, ~50ms (tüm ajanlar için aynı)

  Her ajan için:
  2. natal = agent.cached_natal         # İlk üretimde hesaplanmış, SQLite'ta cache
  3. aspects = fast_aspect_check(       # Saf matematik, ~0.1ms/ajan
       transit_positions, natal.planets
     )

  Toplam: ~50ms + 10K × 0.1ms ≈ 1.05 sn/tick
  vs naive (10K × Kerykeion call): ~500 sn/tick → 500x hızlanma
```

Node ve Chiron transit etkileri de bu pipeline'a dahildir. İleride mikro-optimizasyon olarak yavaş gezegen pozisyonları (Pluto ~0.01°/gün) birden fazla tick boyunca cache'lenebilir.

### 5.7 Visualization (realm/visualization/)

**Amaç:** Ajan ağını nöral synapse benzeri interaktif bir grafik olarak görselleştirmek.

**Tasarım:**

```
Nöronlar = Ajanlar
  - Boyut: etki gücü (influence score)
  - Renk: dominant element (ateş=kırmızı, toprak=yeşil, hava=mavi, su=mor)
  - Parlaklık: mevcut aktivite seviyesi
  - İç halka: meslek kategorisi

Synapse'lar = Etkileşimler
  - Kalınlık: etkileşim yoğunluğu
  - Renk: etkileşim türü (agree=yeşil, disagree=kırmızı, neutral=gri)
  - Animasyon: aktif etkileşim pulse efekti

Kümelenmeler:
  - Coğrafi (ülke/bölge bazlı cluster'lar)
  - Fikri (benzer görüşler birbirine yakın)
  - Mesleki (uzman grupları)

Ek Katmanlar (toggle):
  - Transit etkisi: aktif transiti olan ajanlar halo ile
  - Mood heatmap: bölgesel duygu durumu
  - Information flow: bilgi yayılım animasyonu
```

**Teknoloji:**
- NetworkX: graf hesaplama, layout, metrikler
- D3.js: interaktif web görselleştirme
- Force-directed layout: doğal kümelenme
- FastAPI: async web server + WebSocket (dashboard ile birleşik)

### 5.8 OutputLayer (realm/output/)

**Dashboard Bileşenleri:**

```
┌────────────────────────────────────────────────────────┐
│  REALM Dashboard                          [2026-04-22] │
├──────────────┬─────────────────────────────────────────┤
│ Global Mood  │  ████████░░  72% Optimistic             │
│ Fear Index   │  ██░░░░░░░░  18%                        │
│ Activity     │  ██████░░░░  61%                        │
├──────────────┴─────────────────────────────────────────┤
│  Sector Sentiment                                      │
│  Finance ███████░░░ 68%  │  Politics █████░░░░░ 52%   │
│  Tech    ████████░░ 78%  │  Social   ██████░░░░ 63%   │
├────────────────────────────────────────────────────────┤
│  Active Transits                                       │
│  Mars □ Uranus (exact: Apr 24) → Volatility warning   │
│  Mercury Rx (Apr 18 - May 11) → Communication noise   │
├────────────────────────────────────────────────────────┤
│  [Ask a Question]                                      │
│  "Will BTC rise in the next 7 days?"                  │
│  → Prediction: 62% YES │ Confidence: Medium           │
│  → Key drivers: Mars-Uranus square amplifying risk    │
│     appetite, but Mercury Rx creating hesitation       │
│  → Astro factors: Jupiter trine Sun (optimism wave)   │
│  → Cultural signal: Asian markets bullish, EU cautious│
└────────────────────────────────────────────────────────┘
```

**Q&A Prediction Çıktı Formatı:**

```python
@dataclass
class PredictionResult:
    question: str
    answer: str                     # "YES" / "NO" / "UNCERTAIN"
    probability: float              # 0.0 - 1.0
    confidence: str                 # "low" / "medium" / "high"
    key_drivers: List[str]          # Ana tetikleyiciler
    astro_factors: List[str]        # Astrolojik faktörler
    cultural_signals: List[str]     # Kültürel sinyaller
    dissenting_voices: List[str]    # Karşıt görüşler (önemli!)
    time_horizon: str               # "1 day", "7 days", "30 days"
    supporting_agent_ratio: float   # Bu sonucu destekleyen ajan oranı
    expert_consensus: float         # Uzmanlar arası uzlaşma
    simulation_ticks_used: int      # Kaç tick simüle edildi
```

### 5.9 NetworkTopology (realm/simulation/network.py)

**Amaç:** Ajanlar arası sosyal ağ topolojisini oluşturmak ve yönetmek.

**Model:** Hibrit (Small-world + Scale-free)

```
Katman 1 — Small-world temeli (intra-country):
  Watts-Strogatz modeli
  Her ajan k=10 yerel komşuya bağlı (ülke/meslek/sosyoekonomik kümeleme)
  p=0.1 rewiring ile cross-cluster köprüler
  → Yüksek clustering + kısa ortalama yol uzunluğu

Katman 2 — Scale-free hub'lar (inter-country):
  social_dominance + expert_status + influence skoru yüksek ajanlar
  → Preferential attachment ile ekstra bağlantı kazanır
  → Doğal hub/influencer yapısı oluşur (gazeteciler, iş insanları, akademisyenler)

Dinamik büyüme:
  Etkileşim → yeni bağ olasılığı (simülasyon sırasında ağ evrilir)
```

**Konfigürasyon:**

```yaml
# config/realm.yaml
network:
  topology: "hybrid"          # "small_world" | "scale_free" | "hybrid"
  local_k: 10                 # Ortalama yerel komşu sayısı
  rewire_p: 0.1               # Cross-cluster köprü olasılığı
  hub_boost_factor: 2.5       # Yüksek influence ajanların ekstra bağlantı çarpanı
  cross_country_ratio: 0.05   # Ülkeler arası bağlantı oranı
```

**Teknoloji:** NetworkX ile tek seferde kurulum (population generation sırasında). İki adım: `watts_strogatz_graph` → hub adaylarına preferential attachment ekleme.

### 5.10 PredictionEngine (realm/output/predictor.py)

**Amaç:** Q&A tahminlerini çok-branch simülasyonla üretmek.

**Algoritma:**

```python
def predict(question: str, horizon_days: int = 7, n_branches: int = 5) -> PredictionResult:
    """
    1. Soruyu parse et → topic, direction, horizon
    2. Mevcut state'ten N adet branch fork et:
       - Her branch farklı seed: master_seed + branch_seed_offset * branch_id
       - Aynı popülasyon, farklı rastgele etkileşim sırası
    3. Her branch'e topic focus inject et
    4. Her branch'i horizon kadar simüle et
    5. Her branch'ten ajan oylaması topla:
       - İlgili uzmanların stance dağılımı (expert_weight ile ağırlıklı)
       - Genel popülasyon sentiment trendi
       - Astrolojik iklim yönelimi
    6. Cross-branch aggregation:
       probability = branch'ler arası ortalama YES oranı
       confidence  = branch'ler arası varyans
         - Düşük varyans = yüksek confidence
         - 5/5 branch YES → probability≈0.95, confidence="high"
         - 3/5 branch YES → probability≈0.60, confidence="medium"
         - Yüksek varyans → confidence="low"
    7. Dissenting voices: azınlık görüşü neden farklı düşünüyor?
    """
    ...
```

**Trade-off:** `n_branches=1` ile hızlı kaba tahmin, `n_branches=20` ile yüksek güvenilirlikli derin analiz.

**Konfigürasyon:**

```yaml
# config/realm.yaml
prediction:
  default_branches: 5          # Q&A başına branch sayısı
  max_branches: 20             # Detaylı analiz için
  expert_weight: 3.0           # Uzman oylarının ağırlık çarpanı
  min_relevant_agents: 50      # Altında "insufficient data" döndür
  branch_seed_offset: 1000     # branch_seed = master_seed + offset * branch_id
```

### 5.11 Prompt Management (prompts/)

**Amaç:** LLM prompt'larını koddan ayırarak versiyon kontrolü, A/B test ve iterasyon hızı sağlamak.

**Yapı:**

```
prompts/
├── personality/
│   ├── system.yaml            # System prompt (kişilik analisti rolü)
│   └── user_template.yaml     # User prompt şablonu (natal harita → trait)
├── report/
│   ├── summary.yaml           # Simülasyon özet raporu
│   ├── prediction.yaml        # Tahmin açıklama şablonu
│   └── prediction_tr.yaml     # Türkçe rapor şablonu
├── spotlight/
│   └── narrative.yaml         # Spotlight ajan narratif üretimi
└── question_parser/
    └── parse_question.yaml    # Q&A soru parse prompt'u
```

**YAML Formatı:**

```yaml
version: "1.0"
role: "Astrolojik kişilik analisti"
task: "Natal haritadan trait vektörü üret"
output_format: "JSON TraitVector"
variables:
  - natal_chart_json
  - target_traits
template: |
  Aşağıdaki natal harita verisini analiz et:
  {natal_chart_json}
  
  Şu trait'ler için 0.0-1.0 arası değer üret:
  {target_traits}
```

Her prompt'ta `version` field'i zorunludur — hangi prompt versiyonuyla hangi sonucun üretildiği tracking edilebilir.

---

## 6. DATABASE SCHEMA

```sql
-- Ajan tablosu
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country_code TEXT NOT NULL,
    birth_datetime TEXT NOT NULL,      -- ISO 8601
    birth_lat REAL NOT NULL,
    birth_lon REAL NOT NULL,
    birth_tz TEXT NOT NULL,
    gender TEXT,
    profession TEXT,
    education_level TEXT,
    socioeconomic_tier TEXT,           -- "lower", "middle", "upper", "marginal"
    is_expert INTEGER DEFAULT 0,
    expert_domains TEXT,               -- JSON array: ["finance", "tech"]
    natal_chart_json TEXT,             -- Tam natal harita (cache)
    trait_vector_json TEXT,            -- PersonalityEmbedder çıktısı (cache)
    cultural_modifier_json TEXT,       -- CulturalModifier çıktısı (cache)
    created_at TEXT DEFAULT (datetime('now'))
);

-- Simülasyon durumu
CREATE TABLE simulation_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL,
    tick_number INTEGER NOT NULL,
    sim_datetime TEXT NOT NULL,         -- Simülasyon içi zaman
    global_mood REAL,
    global_fear_index REAL,
    global_activity REAL,
    sector_sentiments_json TEXT,        -- {"finance": 0.68, "tech": 0.78, ...}
    active_transits_json TEXT,
    snapshot_json TEXT,                 -- Tam state snapshot
    created_at TEXT DEFAULT (datetime('now'))
);

-- Ajan aksiyonları
CREATE TABLE agent_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL,
    tick_number INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    platform TEXT NOT NULL,            -- "social_media", "market", ...
    action_type TEXT NOT NULL,         -- "post", "reply", "like", "repost"
    content TEXT,
    target_agent_id TEXT,              -- Reply/interaction hedefi
    sentiment REAL,                    -- -1.0 to 1.0
    influence_score REAL,
    transit_modifiers_json TEXT,       -- O anki aktif transit etkileri
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Seed data
CREATE TABLE seed_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- "news_api", "crypto_api", "manual"
    title TEXT NOT NULL,
    content TEXT,
    category TEXT,                     -- "finance", "politics", "social", "tech"
    severity REAL,                     -- 0.0-1.0 etki büyüklüğü
    injected_at_tick INTEGER,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Tahmin sonuçları
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id TEXT NOT NULL,
    question TEXT NOT NULL,
    result_json TEXT NOT NULL,          -- PredictionResult serialized
    actual_outcome TEXT,               -- Gerçekleşen sonuç (doğrulama için)
    accuracy_score REAL,               -- Tahmin doğruluk skoru (post-hoc)
    created_at TEXT DEFAULT (datetime('now'))
);

-- Ajan etkileşim ağı (graf kenarları)
CREATE TABLE agent_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id_1 TEXT NOT NULL,
    agent_id_2 TEXT NOT NULL,
    interaction_count INTEGER DEFAULT 0,
    affinity_score REAL DEFAULT 0.0,   -- -1.0 to 1.0
    last_interaction_tick INTEGER,
    FOREIGN KEY (agent_id_1) REFERENCES agents(id),
    FOREIGN KEY (agent_id_2) REFERENCES agents(id)
);
```

---

## 7. CONFIGURATION FILES

### 7.1 realm.yaml (Ana Konfigürasyon)

```yaml
realm:
  version: "0.1.0"
  name: "REALM"

  simulation:
    master_seed: 42              # Tam determinizm — aynı seed = aynı sonuç
    tick_interval: "1d"          # "1h", "4h", "1d"
    catchup_speed: 10            # Catch-up modunda hız çarpanı
    max_ticks_per_run: 365       # Tek seferde max tick
    seed_check_interval: 6       # Her 6 tick'te yeni seed kontrol
    checkpoint_interval: 10      # Her 10 tick'te otomatik checkpoint
    max_checkpoints: 5           # Disk alanı yönetimi
    checkpoint_dir: "db/checkpoints/"

  population:
    total_agents: 10000
    scale_target: 50000          # Gelecek hedef
    mode: "static"               # "static" | "semi_dynamic" | "dynamic"
    experience_drift: true       # Deneyim birikimi ile hafif trait kayması
    max_drift_ratio: 0.10        # Base trait'ten max sapma: %10

  personality:
    mode: "rule_based"           # "rule_based" | "llm" | "hybrid"
    cache_profiles: true         # Üretilen profilleri cache'le
    llm_batch_size: 50           # LLM modunda batch boyutu

  llm:
    default_backend: "ollama"    # "ollama" | "claude" | "openai" | "moonshot"
    personality_backend: "claude"  # Kişilik üretimi için ayrı backend
    report_backend: "claude"       # Rapor için ayrı backend
    simulation_backend: "ollama"   # Simülasyon etkileşimleri için

  database:
    path: "db/realm.db"
    backup_interval: 24          # Her 24 tick'te backup

  visualization:
    enabled: true
    web_port: 8888
    graph_layout: "force_directed"
    max_visible_nodes: 2000      # Performans için görsel limit
    update_interval: 5           # Her 5 tick'te görselleştirme güncelle

  birth_time:
    distribution: "realistic"   # "uniform" | "realistic"

  geography:
    granularity: "city"          # "city" | "country_center"
    cities_per_country: 20
    rural_offset_degrees: 1.0
    timezone_auto: true

  network:
    topology: "hybrid"           # "small_world" | "scale_free" | "hybrid"
    local_k: 10
    rewire_p: 0.1
    hub_boost_factor: 2.5
    cross_country_ratio: 0.05

  spotlight:
    enabled: true
    ratio: 0.02                  # Tick başına top %2 etkileşim

  prediction:
    default_branches: 5
    max_branches: 20
    expert_weight: 3.0
    min_relevant_agents: 50
    branch_seed_offset: 1000

  signal:                        # Future: entegrasyon
    polyliq_enabled: false
    argus_enabled: false
```

### 7.2 astrology.yaml

```yaml
astrology:
  system: "western_tropical"
  house_system: "placidus"

  celestial_bodies:
    core: true          # Sun–Pluto (10 gezegen)
    nodes: true         # North Node, South Node
    chiron: true        # Chiron
    lilith: false       # Black Moon Lilith (Faz 2+)
    asteroids: false    # Ceres, Pallas, Juno, Vesta (Faz 2+)

  orbs:
    conjunction: 8.0
    opposition: 8.0
    trine: 7.0
    square: 7.0
    sextile: 5.0
    quincunx: 3.0

  transit_orbs:
    # Transitlerde daha dar orb kullanılır
    conjunction: 3.0
    opposition: 3.0
    trine: 2.5
    square: 2.5
    sextile: 2.0

  transit_weights:
    # Yavaş gezegenler daha güçlü etki
    pluto: 1.0
    neptune: 0.95
    uranus: 0.90
    saturn: 0.85
    jupiter: 0.75
    mars: 0.60
    sun: 0.50
    venus: 0.45
    mercury: 0.40
    moon: 0.30      # Hızlı ama evrensel etki

  cultural_modifier:
    enabled: true
    blend_ratio: 0.3  # Kültürel modifier'ın trait vektöründeki ağırlığı
```

---

## 8. SEED DATA — FREE API SOURCES

**Reference:** github.com/public-apis/public-apis

### 8.1 News & Current Events
| API | Kullanım | Ücretsiz Limit |
|-----|----------|----------------|
| NewsAPI.org | Küresel haberler | 100 req/gün |
| GNews.io | Haber arama | 100 req/gün |
| MediaStack | Canlı haberler | 500 req/ay |
| Currents API | Güncel haberler | 600 req/gün |

### 8.2 Financial Data
| API | Kullanım | Ücretsiz Limit |
|-----|----------|----------------|
| CoinGecko | Kripto fiyatlar | 10-30 req/dk |
| Alpha Vantage | Hisse/forex | 25 req/gün |
| FRED API | ABD ekonomik veri | Sınırsız |
| Open Exchange Rates | Döviz kurları | 1000 req/ay |

### 8.3 Social & Demographic
| API | Kullanım | Ücretsiz Limit |
|-----|----------|----------------|
| REST Countries | Ülke verileri | Sınırsız |
| World Bank API | Kalkınma verileri | Sınırsız |
| UN Data API | Nüfus istatistikleri | Sınırsız |
| Random User API | İsim üretimi | Sınırsız |

### 8.4 Future Expansion (Not)
- RSS feed entegrasyonu (öncelikli genişleme)
- Son dakika haberleri (webhook/streaming)
- Sosyal medya trend API'leri
- Doğal afet / acil durum API'leri

---

## 9. IMPLEMENTATION PHASES

### Faz 1: AstroCore + PersonalityEmbedder (Temel Altyapı)
**Hedef:** Bir doğum verisi girişinden kişilik vektörü çıktısı alabilmek.
- [x] Kerykeion entegrasyonu ve NatalEngine
- [x] TraitVector dataclass
- [x] Rule-based PersonalityEmbedder (planet_traits.py)
- [x] Aspekt modifikasyon katsayıları
- [x] Unit test'ler
- [x] Bilinen natal haritalar ile doğrulama (örn: ünlü kişiler)

### Faz 2: DemographicGenerator + CulturalModifier
**Hedef:** 10.000 ajanlık gerçekçi dünya nüfusu üretmek.
- [x] Ülke verileri toplama (countries.json)
- [x] Nüfus dağılım algoritması
- [x] İsim üretici (ülke bazlı)
- [x] Meslek/eğitim/gelir dağılımı
- [x] Hofstede entegrasyonu
- [x] Marjinal profil üretici
- [x] 10K ajan üretimi ve doğrulama

### Faz 3: SimulationEngine
**Hedef:** Ajanların etkileşim kurabildiği bir simülasyon döngüsü.
- [x] Tick mekanizması ve simülasyon saati
- [x] Sosyal medya platformu (Faz 1 etkileşim alanı)
- [x] Ajan karar mekanizması (kural tabanlı)
- [x] EventBus (kelebek etkisi yayılımı)
- [x] State persistence (SQLite)
- [x] Catch-up mekanizması

### Faz 4: SeedIngestion
**Hedef:** Dış dünya verilerinin simülasyona otomatik beslenmesi.
- [x] API source adaptörleri (haber, finans, sosyal)
- [x] Entity extraction (varlık/ilişki çıkarma)
- [x] Knowledge graph oluşturma
- [x] Olay enjeksiyonu (seed → simülasyon olayı)
- [x] Manuel upload desteği

### Faz 5: TransitModulator
**Hedef:** Astrolojik transitlerin ajan davranışını zamana bağlı modüle etmesi. İki katmanlı: kolektif iklim + bireysel transit.
- [x] Kolektif astrolojik iklim hesaplama (era transitleri, yavaş gezegen geçişleri)
- [x] Kolektif modifier → tüm ajanlara global etki
- [x] Bireysel transit hesaplama pipeline (natal'e transit)
- [x] Transit → trait modifier mapping (bireysel)
- [x] Retro gezegen etkileri
- [x] Ay fazı + tutulma global modifier
- [x] Era/dönem bazlı büyük geçişler (Pluto burç değişimi vb.)
- [x] Nihai trait formülü: base × culture × collective × individual

### Faz 6: OutputLayer + Visualization
**Hedef:** Dashboard, tahmin Q&A, nöral synapse görselleştirme.
- [x] Dashboard backend (FastAPI + WebSocket)
- [x] Mood/sentiment metrikleri
- [x] Q&A prediction interface
- [x] Rapor üretici
- [x] NetworkX graf hesaplama
- [x] D3.js nöral synapse render
- [x] Interaktif web arayüzü

### Faz 7: Entegrasyon (Future)
- [ ] POLYLIQ sinyal bridge
- [ ] ARGUS sinyal bridge
- [ ] LLM backend genişlemesi

---

## 10. KEY DESIGN DECISIONS LOG

| # | Karar | Tarih | Gerekçe |
|---|-------|-------|---------|
| 1 | Sıfırdan yazım (fork değil) | 2026-04-22 | AGPL kısıtlamasından kaçınma, ticari esneklik |
| 2 | Kerykeion kütüphanesi | 2026-04-22 | Swiss Ephemeris tabanlı, JSON çıktı, LLM-uyumlu |
| 3 | Western tropical + kültürel modifier | 2026-04-22 | Tutarlı hesaplama + kültürel derinlik dengesi |
| 4 | SQLite + JSON | 2026-04-22 | Hafif, GMKtec uyumlu, POLYLIQ/ARGUS ile tutarlı |
| 5 | Plugin-based LLM backend | 2026-04-22 | Backend esnekliği, maliyet optimizasyonu |
| 6 | 10K başlangıç, ölçeklenebilir mimari | 2026-04-22 | Hızlı iterasyon, sonra büyütme |
| 7 | Hibrit kişilik üretimi (A→C yolu) | 2026-04-22 | Kural tabanlı başla, LLM'e geçiş yolu aç |
| 8 | Dinamik uzman dağılımı (3 mod) | 2026-04-22 | Karşılaştırmalı analiz imkanı |
| 9 | Nöral synapse görselleştirme | 2026-04-22 | Ajan ağının sezgisel görselleştirilmesi |
| 10 | Kelebek etkisi EventBus | 2026-04-22 | Her şey birbiriyle bağlantılı prensibi |
| 11 | Vektör tabanlı content + Spotlight | 2026-04-22 | Maliyet/performans optimizasyonu, kolektif sinyal yeterli |
| 12 | 13 gök cismi (10+Node+Chiron) | 2026-04-22 | Modern Batı astrolojisi standardı, config ile genişletilebilir |
| 13 | Tam deterministik (master_seed) | 2026-04-22 | A/B test, kalibrasyon, bilimsel geçerlilik |
| 14 | Hibrit ağ topolojisi | 2026-04-22 | Gerçek sosyal ağ yapısı: kümeleme + hub'lar |
| 15 | Ayrıştırılmış transit hesaplama | 2026-04-22 | 500x performans kazancı (1 sn vs 500 sn/tick) |
| 16 | Statik popülasyon + deneyim drift | 2026-04-22 | Basitlik + gerçekçilik dengesi |
| 17 | Şehir düzeyinde coğrafya | 2026-04-22 | Natal harita doğruluğu (enlem farkı ev pozisyonlarını etkiler) |
| 18 | Simülasyon branching (Faz 3+) | 2026-04-22 | Senaryo karşılaştırma, astrolojik kalibrasyon |
| 19 | Gerçekçi doğum saati dağılımı | 2026-04-22 | Uniform yapay eşitlik üretir, gerçek toplum yansıması |
| 20 | FastAPI (Flask değil) | 2026-04-22 | Async native, WebSocket, Pydantic entegrasyonu |
| 21 | Checkpoint + resume | 2026-04-22 | Branching ile birleşik mekanizma, crash recovery |
| 22 | Çok-branch prediction (varyans=confidence) | 2026-04-22 | Tek branch confidence ölçemez, Monte Carlo yaklaşımı |
| 23 | Faker isim üretimi | 2026-04-22 | 50+ locale, deterministik, statik JSON gereksiz |
| 24 | Versiyonlu YAML prompt yönetimi | 2026-04-22 | Kod-prompt ayrımı, A/B test, iterasyon hızı |
| 25 | Cross-platform propagation kuralları | 2026-04-22 | Parliament→news dahil, Faz 2+ genişleme |

---

## 11. DEPENDENCIES

### 11.1 Core
```
kerykeion>=5.12          # Astroloji hesaplama (Swiss Ephemeris)
pydantic>=2.0            # Veri doğrulama ve serialization
pyyaml>=6.0              # Konfigürasyon
python-dotenv>=1.0       # Environment variables
```

### 11.2 Database & Data
```
# SQLite built-in (Python stdlib)
requests>=2.31           # API calls
aiohttp>=3.9             # Async API calls
feedparser>=6.0          # RSS feed parsing (Future)
faker>=20.0              # Ülke bazlı isim üretimi (50+ locale)
timezonefinder>=6.0      # Koordinat → timezone dönüşümü
```

### 11.3 Simulation & Analysis
```
networkx>=3.2            # Graf hesaplama
numpy>=1.26              # Sayısal hesaplamalar
pandas>=2.1              # Veri analizi
```

### 11.4 Visualization & Web
```
fastapi>=0.110           # Web server (async, Pydantic entegre)
uvicorn>=0.27            # ASGI server
# D3.js (CDN, Python bağımlılığı yok)
# Chart.js (CDN, dashboard grafikleri)
```

### 11.5 LLM Backends (opsiyonel, kullanılana göre)
```
anthropic>=0.40          # Claude API
openai>=1.40             # OpenAI API
ollama>=0.4              # Ollama local
```

### 11.6 Development
```
pytest>=8.0              # Test
pytest-asyncio           # Async test
black                    # Formatter
ruff                     # Linter
```

---

## 12. HARDWARE & ENVIRONMENT

- **Machine:** GMKtec NucBox K8 Plus (Ryzen 7 8845HS, 32GB DDR5)
- **OS:** Windows + WSL2 (Ubuntu)
- **Python:** 3.11+
- **Concurrent processes:** POLYLIQ ve ARGUS aynı makinede çalışıyor
- **Dikkat:** RAM paylaşımı — 10K ajan in-memory yaklaşık 2-4 GB
- **Ollama:** Zaten kurulu (Hermes deneyiminden), Qwen 2.5 model mevcut

---

## 13. NOTES & FUTURE ROADMAP

### 13.1 Genişleme Alanları (Prioritized)
1. **RSS + Son dakika haberleri:** SeedIngestion'a real-time feed
2. **Çoklu platform etkileşimi:** Meclis, piyasa, akademi, sokak
3. **Vedik / Çin astroloji modülleri:** Region-native astroloji desteği
4. **3D görselleştirme:** Three.js ile immersive dünya modeli
5. **Distributed computing:** Birden fazla makine üzerinde büyük ölçekli simülasyon
6. **POLYLIQ entegrasyonu:** Polymarket trade sinyali olarak Realm prediction

### 13.2 Bilinen Riskler ve Limitasyonlar
- **LLM bias:** OASIS araştırmasında belirtildiği gibi, LLM ajanlar gerçek insanlardan daha hızlı polarize olabiliyor. Rule-based yaklaşımda bu risk daha düşük.
- **Astroloji doğruluğu:** Kişilik mapping'i deneysel — sürekli kalibrasyon gerekiyor. Gerçek dünya sonuçlarıyla karşılaştırılarak refine edilmeli.
- **API limitleri:** Ücretsiz API'lerin rate limit'leri simülasyon hızını kısıtlayabilir. Cache stratejisi kritik.
- **GMKtec kaynakları:** 32GB RAM ile 50K+ ajan zor olabilir. Disk-backed approach veya lazy loading gerekebilir.

### 13.3 MiroFish'ten Öğrenilen Dersler
- GraphRAG ile entity extraction güçlü bir pattern — SeedIngestion'da benzerini kullanacağız
- Dual-platform simülasyonu (Twitter + Reddit) iyi çalışıyor, biz de sosyal medya platformuyla başlıyoruz
- ReportAgent'ın simülasyon sonrası ortamda tool kullanarak analiz yapması güçlü — OutputLayer'da benzer yaklaşım

### 13.4 Kalibrasyon / Validasyon Stratejisi
- **Faz 1:** Bilinen natal haritalar ile trait vector doğrulama (ünlü kişiler: bilinen kişilik → beklenen trait vector)
- **Faz 3:** Geçmiş olaylar ile retrospektif simülasyon (bilinen sonuçla karşılaştırma — "2024 seçimleri" gibi)
- **Faz 5:** Transit etkisi kalibrasyonu (transit modifier katsayılarını gerçek dünya verileriyle tune etme)
- **Faz 6:** Prediction accuracy tracking (`predictions` tablosundaki `accuracy_score` — gerçekleşen sonuçlarla otomatik karşılaştırma)

### 13.5 Monitoring / Observability
Uzun çalışan simülasyonlarda sağlık takibi (`realm/core/monitoring.py`):
- Tick başına metrikler: süre, aktif ajan sayısı, aksiyon sayısı, bellek kullanımı
- Anomali tespiti: sentiment'in beklenmedik kayması, agent clustering bozulması
- Dashboard'a monitoring paneli (Faz 6)

---

## 14. GETTING STARTED (Faz 1 için)

```bash
# 1. Repo oluştur
mkdir realm && cd realm
git init

# 2. Python ortamı
python -m venv .venv
source .venv/bin/activate  # Linux/WSL
# .venv\Scripts\activate   # Windows

# 3. Temel bağımlılıkları kur
pip install kerykeion pydantic pyyaml python-dotenv pytest

# 4. Dizin yapısını oluştur (Faz 1 modülleri)
mkdir -p realm/{core,astro,personality}/{tests,}
mkdir -p config data/astro

# 5. İlk test: Kerykeion çalışıyor mu?
python -c "from kerykeion import AstrologicalSubject; print('OK')"
```

### 14.1 pyproject.toml Şablonu

```toml
[project]
name = "realm"
version = "0.1.0"
description = "Astrological Swarm Intelligence Prediction Engine"
requires-python = ">=3.11"
dependencies = [
    "kerykeion>=5.12",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "networkx>=3.2",
    "numpy>=1.26",
    "pandas>=2.1",
    "requests>=2.31",
    "aiohttp>=3.9",
    "faker>=20.0",
    "timezonefinder>=6.0",
    "fastapi>=0.110",
    "uvicorn>=0.27",
]

[project.optional-dependencies]
llm = ["anthropic>=0.40", "openai>=1.40", "ollama>=0.4"]
dev = ["pytest>=8.0", "pytest-asyncio", "black", "ruff"]

[tool.pytest.ini_options]
testpaths = ["tests", "realm"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"
```

### 14.2 .gitignore

```
# Environment
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/

# Database
db/*.db
db/checkpoints/

# Build
dist/
*.egg-info/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

*Bu doküman, REALM projesinin yaşayan referansıdır. Her önemli karar ve değişiklik buraya kaydedilir.*
