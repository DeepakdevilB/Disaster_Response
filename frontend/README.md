# DisasterFlow Frontend - Emergency Command & Citizen Portal

A production-quality React 19 + TypeScript + Vite web client for the **Intelligent Disaster Response & Emergency Coordination Platform**.

## Key Highlights & Features
- **INR 0 Budget Stack**: Built using Leaflet + OpenStreetMap (no paid Google Maps API), Vite, and open-source icons.
- **Glassmorphism Design System**: Modern dark emergency theme with high-contrast crisis indicators, pulsating beacons for critical incidents, and responsive layouts.
- **Command Center (`EmergencyMap` + `AuthorityDashboard`)**:
  - Interactive Leaflet map with color-coded severity markers (CRITICAL, HIGH, MEDIUM, LOW) and deployable resource pins.
  - Multi-attribute triage filters (Category, Severity, Status, Keyword search).
  - Detailed AI Model Inference inspection (Confidence percentages, TF-IDF probability spread, Extracted entities).
  - **Human-in-the-Loop Override Form**: Mandatory justification reason, syncing to backend audit trail.
  - **Situation Summarizer**: Trigger on-demand AI executive crisis assessment with safety disclaimers.
  - Status transition workflow (`new` &rarr; `verified` &rarr; `assigned` &rarr; `in_progress` &rarr; `resolved` &rarr; `rejected`).
- **Citizen Distress Portal (`CitizenPortal`)**:
  - High-urgency reporting form with browser GPS geolocation detection.
  - 1-click crisis presets (Flash Flood, Fire/Explosion, Medical Trauma, Structural Collapse, High-Voltage Hazard).
  - Photo / Evidence upload simulator with MinIO presigned URL integration.
- **Resource Fleet Panel (`ResourcePanel`)**:
  - Deployable assets tracking (Boats, Ambulances, Rescue Teams, Kits).
  - 1-click status cycling (`available` &rarr; `assigned` &rarr; `offline`).
- **AI & Model Diagnostics (`ModelDiagnostics`)**:
  - Transparent performance metrics: Macro-F1 0.9380 on category classifier, 1.000 recall on critical emergencies, ethical AI constraints.

## Tech Stack
- React 19, TypeScript 5.8
- Vite 8
- Leaflet 1.9 + OpenStreetMap tiles
- Lucide React icons
- Oxlint for sub-50ms linting

## Development Setup

```bash
cd frontend
npm install
npm run dev
```

App opens at `http://localhost:5173`.

## Production Build & Linting

```bash
npm run lint      # Fast Oxlint verification
npm run build     # Type-check with tsc and bundle with Vite
```
