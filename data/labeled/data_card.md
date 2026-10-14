# Dataset Card: Disaster & Crisis Incident Reports (Multi-lingual)

## 1. Overview
- **Dataset Name**: Crisis Incident Reports v1
- **File**: `crisis_reports.csv`
- **Total Records**: 400
- **Languages**: English (`en`), Hinglish (`hi-Latn`)
- **Task Alignment**: Phase 2 AI Layer (T-025, T-026, T-028, T-029, T-030)

## 2. Taxonomy & Schema

### Fields:
1. `text`: Full raw text of the citizen or emergency responder report.
2. `category`: One of `medical`, `rescue`, `infrastructure`, `fire`, `flood`, `other`.
3. `severity`: One of `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
4. `people_count`: Number of affected or trapped persons (0 if unmentioned).
5. `location`: Landmark or geographical phrase embedded in text.
6. `resource_needed`: Key recommended resource (`ambulance`, `boat`, `rescue_team`, `medical_kit`, `food_kit`, `none`).
7. `language`: Language tag (`en` or `hi-Latn`).

### Class Distribution (approximate):
- **Categories**:
  - `flood`: ~18%
  - `fire`: ~17%
  - `medical`: ~18%
  - `rescue`: ~18%
  - `infrastructure`: ~17%
  - `other`: ~12%
- **Severities**:
  - `CRITICAL`: ~28%
  - `HIGH`: ~32%
  - `MEDIUM`: ~23%
  - `LOW`: ~17%

## 3. Linguistic Diversity
Includes common Indian vernacular and Hinglish phrases:
- Emergency exclamations: *bachao*, *madad*, *jaldi*, *turant*, *urgent*.
- Disaster terminology: *paani*, *baadh*, *aag*, *dhuan*, *malba*, *dhas gaya*, *toota*.
- Romanized numerals: *ek*, *do*, *teen*, *chaar*, *paanch*, *chhe*, *saat*, *aath*, *das*.
- Affected entities: *log*, *bache*, *buzurg*, *mahilayein*, *family*.

## 4. Usage & Ethical Considerations
- Zero personally identifiable information (PII). All simulated addresses use generic landmarks and sectors.
- Strictly for training and benchmarking emergency triage models.
- Human-in-the-loop: predictions are advisory only, and authorities retain manual override authority at all times.
