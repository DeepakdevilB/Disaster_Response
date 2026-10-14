import React, { useEffect, useState } from "react";
import {
  Brain,
  LayoutDashboard,
  Radio,
  RefreshCw,
  Send,
  Shield,
  Truck,
} from "lucide-react";
import type { IncidentSummary, ResourceItem } from "./api/client";
import { api } from "./api/client";
import { AuthorityDashboard } from "./components/AuthorityDashboard";
import { CitizenPortal } from "./components/CitizenPortal";
import { EmergencyMap } from "./components/EmergencyMap";
import { ModelDiagnostics } from "./components/ModelDiagnostics";
import { ResourcePanel } from "./components/ResourcePanel";
import { MOCK_INCIDENTS, MOCK_RESOURCES } from "./data/mockData";
import "./App.css";

type ActiveTab = "command" | "citizen" | "resources" | "ai_diagnostics";
type UserRole = "citizen" | "authority" | "rescue" | "admin";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>("command");
  const [role, setRole] = useState<UserRole>("authority");

  // Emergency Incidents & Resources State
  const [incidents, setIncidents] = useState<IncidentSummary[]>(MOCK_INCIDENTS);
  const [resources, setResources] = useState<ResourceItem[]>(MOCK_RESOURCES);
  const [selectedIncident, setSelectedIncident] = useState<IncidentSummary | null>(MOCK_INCIDENTS[0]);

  // Map state
  const [mapCenter, setMapCenter] = useState<[number, number]>([28.6448, 77.2167]); // Delhi NCR
  const [mapZoom, setMapZoom] = useState<number>(12);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"connected" | "demo_mock">("demo_mock");

  // Fetch live incidents from API if backend is active
  const loadData = async () => {
    setIsRefreshing(true);
    try {
      const liveIncidents = await api.getIncidents();
      if (liveIncidents && liveIncidents.length > 0) {
        setIncidents(liveIncidents);
        setBackendStatus("connected");
      }
    } catch {
      setBackendStatus("demo_mock");
    }

    try {
      const liveResources = await api.getResources();
      if (liveResources && liveResources.length > 0) {
        setResources(liveResources);
      }
    } catch {
      // keep mock resources
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    api.getIncidents()
      .then((liveIncidents) => {
        if (isMounted && liveIncidents && liveIncidents.length > 0) {
          setIncidents(liveIncidents);
          setBackendStatus("connected");
        }
      })
      .catch(() => {
        if (isMounted) setBackendStatus("demo_mock");
      });

    api.getResources()
      .then((liveResources) => {
        if (isMounted && liveResources && liveResources.length > 0) {
          setResources(liveResources);
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  // When an incident is selected, center map on it
  const handleSelectIncident = (inc: IncidentSummary) => {
    setSelectedIncident(inc);
    if (inc.location_lat != null && inc.location_lon != null) {
      setMapCenter([inc.location_lat, inc.location_lon]);
      setMapZoom(14);
    }
  };

  // When an incident is updated (e.g. status change or override)
  const handleIncidentUpdated = (updated: IncidentSummary) => {
    setIncidents((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    if (selectedIncident?.id === updated.id) {
      setSelectedIncident(updated);
    }
  };

  // When a resource is updated
  const handleResourceUpdated = (updated: ResourceItem) => {
    setResources((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
  };

  // When citizen submits report
  const handleCitizenReportSubmitted = () => {
    // Refresh or switch to command center to view ingested report
    loadData();
    setActiveTab("command");
  };

  const criticalCount = incidents.filter((i) => i.severity === "CRITICAL").length;

  return (
    <div className="app-container">
      {/* Top Navigation Bar */}
      <header
        style={{
          borderBottom: "1px solid var(--border-subtle)",
          background: "rgba(7, 10, 18, 0.85)",
          backdropFilter: "blur(20px)",
          position: "sticky",
          top: 0,
          zIndex: 1100,
        }}
      >
        <div
          style={{
            maxWidth: "1440px",
            margin: "0 auto",
            padding: "12px 24px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "14px",
          }}
        >
          {/* Brand */}
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "38px",
                height: "38px",
                borderRadius: "10px",
                background: "linear-gradient(135deg, #e11d48 0%, #f97316 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 15px rgba(225, 29, 72, 0.4)",
              }}
            >
              <Radio size={20} color="#fff" />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h1 className="font-display" style={{ fontSize: "1.25rem", fontWeight: 800, letterSpacing: "-0.02em", color: "#fff" }}>
                  DisasterFlow
                </h1>
                <span
                  style={{
                    fontSize: "0.65rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: "rgba(56, 189, 248, 0.15)",
                    color: "var(--accent-cyan)",
                    border: "1px solid rgba(56, 189, 248, 0.3)",
                  }}
                >
                  AI Command Core
                </span>
              </div>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Autonomous Emergency Ingest &amp; Response Coordinator
              </p>
            </div>
          </div>

          {/* Navigation View Tabs */}
          <nav style={{ display: "flex", gap: "6px", background: "rgba(15, 23, 42, 0.7)", padding: "4px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
            <button
              type="button"
              onClick={() => setActiveTab("command")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 16px",
                borderRadius: "8px",
                fontSize: "0.85rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeTab === "command" ? "rgba(56, 189, 248, 0.2)" : "transparent",
                color: activeTab === "command" ? "#fff" : "var(--text-secondary)",
                boxShadow: activeTab === "command" ? "0 0 10px rgba(56, 189, 248, 0.2)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              <LayoutDashboard size={16} color={activeTab === "command" ? "#38bdf8" : "currentColor"} />
              Command Center
              {criticalCount > 0 && (
                <span
                  style={{
                    fontSize: "0.7rem",
                    padding: "1px 6px",
                    borderRadius: "10px",
                    background: "var(--sev-critical)",
                    color: "#fff",
                    fontWeight: 700,
                  }}
                >
                  {criticalCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("citizen")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 16px",
                borderRadius: "8px",
                fontSize: "0.85rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeTab === "citizen" ? "rgba(244, 63, 94, 0.2)" : "transparent",
                color: activeTab === "citizen" ? "#fff" : "var(--text-secondary)",
                boxShadow: activeTab === "citizen" ? "0 0 10px rgba(244, 63, 94, 0.2)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              <Send size={16} color={activeTab === "citizen" ? "#f43f5e" : "currentColor"} />
              Citizen Distress
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("resources")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 16px",
                borderRadius: "8px",
                fontSize: "0.85rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeTab === "resources" ? "rgba(56, 189, 248, 0.2)" : "transparent",
                color: activeTab === "resources" ? "#fff" : "var(--text-secondary)",
                boxShadow: activeTab === "resources" ? "0 0 10px rgba(56, 189, 248, 0.2)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              <Truck size={16} color={activeTab === "resources" ? "#38bdf8" : "currentColor"} />
              Resource Fleet
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("ai_diagnostics")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 16px",
                borderRadius: "8px",
                fontSize: "0.85rem",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                background: activeTab === "ai_diagnostics" ? "rgba(192, 132, 252, 0.2)" : "transparent",
                color: activeTab === "ai_diagnostics" ? "#fff" : "var(--text-secondary)",
                boxShadow: activeTab === "ai_diagnostics" ? "0 0 10px rgba(192, 132, 252, 0.2)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              <Brain size={16} color={activeTab === "ai_diagnostics" ? "#c084fc" : "currentColor"} />
              AI Diagnostics
            </button>
          </nav>

          {/* Persona Switcher & Live Status */}
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "0.75rem",
                background: "rgba(15, 23, 42, 0.8)",
                padding: "6px 12px",
                borderRadius: "8px",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <Shield size={14} color="var(--accent-cyan)" />
              <span style={{ color: "var(--text-muted)" }}>Role:</span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#fff",
                  fontWeight: 600,
                  fontSize: "0.8rem",
                  cursor: "pointer",
                  outline: "none",
                }}
              >
                <option value="authority" style={{ background: "#0c1220", color: "#fff" }}>Authority Commander</option>
                <option value="citizen" style={{ background: "#0c1220", color: "#fff" }}>Citizen User</option>
                <option value="rescue" style={{ background: "#0c1220", color: "#fff" }}>Rescue Field Team</option>
                <option value="admin" style={{ background: "#0c1220", color: "#fff" }}>System Admin</option>
              </select>
            </div>

            <button
              type="button"
              onClick={loadData}
              disabled={isRefreshing}
              className="btn-secondary"
              style={{ padding: "6px 10px", fontSize: "0.8rem" }}
              title="Sync with FastAPI"
            >
              <RefreshCw size={14} className={isRefreshing ? "spin-animation" : ""} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Tab Content */}
      <main className="main-content">
        {activeTab === "command" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {/* Live Leaflet Map Container */}
            <div
              className="glass-panel"
              style={{
                height: "420px",
                overflow: "hidden",
                position: "relative",
                border: "1px solid rgba(255, 255, 255, 0.12)",
              }}
            >
              <EmergencyMap
                incidents={incidents}
                resources={resources}
                selectedIncidentId={selectedIncident?.id}
                onSelectIncident={handleSelectIncident}
                center={mapCenter}
                zoom={mapZoom}
              />
            </div>

            {/* Authority Triage Dashboard */}
            <AuthorityDashboard
              incidents={incidents}
              selectedIncident={selectedIncident}
              onSelectIncident={handleSelectIncident}
              onRefresh={loadData}
              onIncidentUpdated={handleIncidentUpdated}
            />
          </div>
        )}

        {activeTab === "citizen" && (
          <CitizenPortal onReportSubmitted={handleCitizenReportSubmitted} />
        )}

        {activeTab === "resources" && (
          <ResourcePanel
            resources={resources}
            onResourceUpdated={handleResourceUpdated}
            onRefresh={loadData}
            onFocusCoordinates={(lat, lon) => {
              setMapCenter([lat, lon]);
              setMapZoom(15);
              setActiveTab("command");
            }}
          />
        )}

        {activeTab === "ai_diagnostics" && <ModelDiagnostics />}
      </main>

      {/* Footer */}
      <footer
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "16px 24px",
          textAlign: "center",
          fontSize: "0.8rem",
          color: "var(--text-muted)",
          marginTop: "auto",
        }}
      >
        <div style={{ maxWidth: "1440px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
          <span>
            Intelligent Disaster Response &amp; Emergency Coordination Platform • Final Year Major Project
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
              <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: backendStatus === "connected" ? "#34d399" : "#38bdf8" }}></span>
              {backendStatus === "connected" ? "Backend Synchronized (FastAPI)" : "Edge Mock Simulation Active"}
            </span>
            <span>• INR 0 Budget (FOSS)</span>
          </span>
        </div>
      </footer>
    </div>
  );
};

export default App;
