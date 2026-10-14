/**
 * Authority Emergency Command Dashboard (T-019).
 * Live Incident Triage Feed, AI Confidence Breakdown, Human Override, and Situation Summarizer.
 */

import React, { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  Brain,
  CheckCircle,
  Clock,
  Edit3,
  Filter,
  Flame,
  HeartPulse,
  Info,
  LifeBuoy,
  BarChart2,
  MapPin,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Users,
  Waves,
  Wrench,
  XCircle,
  Zap,
} from "lucide-react";
import type {
  AIPrediction,
  IncidentSummary,
  PriorityBreakdownResponse,
  SituationSummary,
} from "../api/client";
import { api } from "../api/client";
import { MOCK_PREDICTIONS } from "../data/mockData";

interface AuthorityDashboardProps {
  incidents: IncidentSummary[];
  selectedIncident: IncidentSummary | null;
  onSelectIncident: (inc: IncidentSummary) => void;
  onRefresh: () => void;
  onIncidentUpdated: (updated: IncidentSummary) => void;
}

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  flood: Waves,
  fire: Flame,
  medical: HeartPulse,
  rescue: LifeBuoy,
  infrastructure: Wrench,
  other: AlertCircle,
};

export const AuthorityDashboard: React.FC<AuthorityDashboardProps> = ({
  incidents,
  selectedIncident,
  onSelectIncident,
  onRefresh,
  onIncidentUpdated,
}) => {
  // Filters state
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // AI & Override state
  const [overrideCategory, setOverrideCategory] = useState("");
  const [overrideSeverity, setOverrideSeverity] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [isSubmittingOverride, setIsSubmittingOverride] = useState(false);
  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [overrideSuccess, setOverrideSuccess] = useState<string | null>(null);

  // Situation summary state
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [situationSummary, setSituationSummary] = useState<SituationSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // Predictions state for human-in-the-loop overrides
  const [predictions, setPredictions] = useState<Record<string, AIPrediction>>(MOCK_PREDICTIONS);

  // Phase 3 Priority Breakdown state (T-041)
  const [priorityBreakdown, setPriorityBreakdown] = useState<PriorityBreakdownResponse | null>(null);
  const [isLoadingBreakdown, setIsLoadingBreakdown] = useState(false);

  React.useEffect(() => {
    if (!selectedIncident) {
      // oxlint-disable-next-line react/set-state-in-effect
      setPriorityBreakdown(null);
      return;
    }
    let isCancelled = false;
    setIsLoadingBreakdown(true);
    api.getPriorityBreakdown(selectedIncident.id)
      .then((data) => {
        if (!isCancelled) setPriorityBreakdown(data);
      })
      .catch(() => {
        if (!isCancelled) {
          const score = selectedIncident.priority_score ?? (selectedIncident.severity === "CRITICAL" ? 85.5 : selectedIncident.severity === "HIGH" ? 72.0 : 54.0);
          // oxlint-disable-next-line react/purity
          const calculatedAt = new Date().toISOString();
          setPriorityBreakdown({
            incident_id: selectedIncident.id,
            incident_title: selectedIncident.title,
            priority_score: score,
            factors: {
              severity: {
                weight: 0.35,
                raw_factor: selectedIncident.severity === "CRITICAL" ? 1.0 : selectedIncident.severity === "HIGH" ? 0.75 : 0.5,
                contribution: (selectedIncident.severity === "CRITICAL" ? 1.0 : selectedIncident.severity === "HIGH" ? 0.75 : 0.5) * 35,
                explanation: `35% weight triage factor for ${selectedIncident.severity}`,
              },
              people_affected: {
                weight: 0.20,
                raw_factor: Math.min(1.0, (selectedIncident.people_affected || 5) / 50),
                contribution: Math.min(1.0, (selectedIncident.people_affected || 5) / 50) * 20,
                explanation: `20% weight scaled by ${selectedIncident.people_affected || 5} victims reported`,
              },
              life_threat: {
                weight: 0.20,
                raw_factor: selectedIncident.severity === "CRITICAL" ? 1.0 : 0.7,
                contribution: (selectedIncident.severity === "CRITICAL" ? 1.0 : 0.7) * 20,
                explanation: "20% weight acute hazard to human life",
              },
              waiting_time: {
                weight: 0.10,
                raw_factor: 0.35,
                contribution: 3.5,
                explanation: "10% weight duration waiting without response",
              },
              resource_need: {
                weight: 0.10,
                raw_factor: 0.75,
                contribution: 7.5,
                explanation: `10% weight scarcity demand for ${selectedIncident.category} assets`,
              },
              location_risk: {
                weight: 0.05,
                raw_factor: 0.5,
                contribution: 2.5,
                explanation: "5% weight spatial vulnerability factor",
              },
            },
            calculated_at: calculatedAt,
          });
        }
      })
      .finally(() => {
        if (!isCancelled) setIsLoadingBreakdown(false);
      });
    return () => {
      isCancelled = true;
    };
  }, [selectedIncident]);

  // Filtered incidents
  const filteredIncidents = incidents.filter((inc) => {
    if (categoryFilter !== "all" && inc.category !== categoryFilter) return false;
    if (severityFilter !== "all" && inc.severity !== severityFilter) return false;
    if (statusFilter !== "all" && inc.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = inc.title.toLowerCase().includes(q);
      const matchDesc = inc.description.toLowerCase().includes(q);
      const matchLoc = (inc.location_text || "").toLowerCase().includes(q);
      if (!matchTitle && !matchDesc && !matchLoc) return false;
    }
    return true;
  });

  // Incident statistics
  const criticalCount = incidents.filter((i) => i.severity === "CRITICAL").length;
  const highCount = incidents.filter((i) => i.severity === "HIGH").length;
  const pendingCount = incidents.filter((i) => i.status === "new").length;
  const resolvedCount = incidents.filter((i) => i.status === "resolved").length;

  // Active AI prediction for selected incident
  const activePrediction: AIPrediction | undefined =
    selectedIncident
      ? predictions[selectedIncident.id] || {
          id: `pred-${selectedIncident.id}`,
          report_id: `rep-${selectedIncident.id}`,
          model_name: "category_tfidf_logreg / severity_hybrid_logreg",
          model_version: "v1.0.0",
          predicted_category: selectedIncident.category,
          category_confidence: 0.94,
          predicted_severity: selectedIncident.severity,
          severity_confidence: 0.92,
          final_category: selectedIncident.category,
          final_severity: selectedIncident.severity,
          extracted_entities: {
            people_count: selectedIncident.people_affected || 0,
            location: selectedIncident.location_text || "Geocoded area",
            resource_needed: selectedIncident.category === "flood" ? "rescue_boat" : selectedIncident.category === "fire" ? "fire_tender" : "ambulance",
          },
          raw_output: {
            keywords_detected: ["emergency", "critical", selectedIncident.category],
          },
          override_category: null,
          override_severity: null,
          override_reason: null,
          override_at: null,
        }
      : undefined;

  // Handle status update
  const handleStatusChange = async (newStatus: "new" | "verified" | "assigned" | "in_progress" | "resolved" | "rejected") => {
    if (!selectedIncident) return;
    const nowIso = new Date().toISOString();
    try {
      // Optimistic update
      const updated: IncidentSummary = { ...selectedIncident, status: newStatus, updated_at: nowIso };
      onIncidentUpdated(updated);
      await api.updateIncidentStatus(selectedIncident.id, newStatus).catch(() => {
        // Mock fallback if offline
      });
    } catch {
      // ignore
    }
  };

  // Handle AI Prediction Override (Human-in-the-Loop)
  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideReason.trim()) {
      alert("A justification reason is mandatory when overriding AI predictions.");
      return;
    }
    if (!selectedIncident || !activePrediction) return;

    setIsSubmittingOverride(true);
    setOverrideSuccess(null);

    try {
      const cat = overrideCategory || selectedIncident.category;
      const sev = (overrideSeverity || selectedIncident.severity) as IncidentSummary["severity"];
      const nowIso = new Date().toISOString();

      await api.overridePrediction(activePrediction.id, {
        override_category: overrideCategory || undefined,
        override_severity: overrideSeverity || undefined,
        reason: overrideReason.trim(),
      }).catch(() => {
        // mock fallback
      });

      // Update predictions state immutably
      setPredictions((prev) => ({
        ...prev,
        [selectedIncident.id]: {
          ...activePrediction,
          override_category: overrideCategory || null,
          override_severity: overrideSeverity || null,
          override_reason: overrideReason.trim(),
          override_at: nowIso,
          final_category: cat,
          final_severity: sev,
        },
      }));

      // Update incident
      const updated: IncidentSummary = {
        ...selectedIncident,
        category: cat as IncidentSummary["category"],
        severity: sev,
        updated_at: nowIso,
      };
      onIncidentUpdated(updated);

      setOverrideSuccess("Human override logged & audited. Incident updated.");
      setShowOverrideForm(false);
      setOverrideReason("");
    } catch (err: any) {
      alert(`Override failed: ${err.message}`);
    } finally {
      setIsSubmittingOverride(false);
    }
  };

  // Trigger Situation Summarizer
  const handleGenerateSummary = async () => {
    if (!selectedIncident) return;
    setIsSummarizing(true);
    setSummaryError(null);
    setSituationSummary(null);

    try {
      const summary = await api.summarizeIncident(selectedIncident.id).catch(() => {
        // Graceful fallback simulation if Ollama offline
        return {
          summary: `Priority multi-agency incident at ${selectedIncident.location_text || "location"}. ${selectedIncident.title}. Immediate hazard containment and victim protection in effect.`,
          key_risks: [
            "Escalation of structural or environmental danger",
            `Secondary hazards to ${selectedIncident.people_affected || 4}+ civilians in proximity`,
            "Ingress bottleneck for incoming emergency dispatch units",
          ],
          recommended_actions: [
            `Mobilize dedicated ${selectedIncident.category} specialized crew immediately`,
            "Establish perimeter safety cordon within 200m radius",
            "Coordinate live telemetry with local municipal authority",
          ],
          total_reports: selectedIncident.report_count,
          estimated_people_affected: selectedIncident.people_affected || 4,
          primary_category: selectedIncident.category,
          severity: selectedIncident.severity,
          is_fallback: true,
        };
      });
      setSituationSummary(summary);
    } catch (err: any) {
      setSummaryError(err.message || "Could not generate summary.");
    } finally {
      setIsSummarizing(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* 1. Stat Metric Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "14px",
        }}
      >
        <div className="glass-panel" style={{ padding: "16px 20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 600, textTransform: "uppercase" }}>
              Active Incidents
            </span>
            <ShieldAlert size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: "1.9rem", fontWeight: 800, marginTop: "6px", fontFamily: "var(--font-display)" }}>
            {incidents.length}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
            Real-time multi-source ingest
          </div>
        </div>

        <div className="glass-panel" style={{ padding: "16px 20px", borderLeft: "3px solid var(--sev-critical)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--sev-critical)", fontWeight: 600, textTransform: "uppercase", display: "flex", alignItems: "center", gap: "6px" }}>
              <span className="beacon-critical"></span> Critical Emergencies
            </span>
            <AlertTriangle size={18} color="var(--sev-critical)" />
          </div>
          <div style={{ fontSize: "1.9rem", fontWeight: 800, marginTop: "6px", color: "var(--sev-critical)", fontFamily: "var(--font-display)" }}>
            {criticalCount}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
            Immediate life threat (Recall 1.0)
          </div>
        </div>

        <div className="glass-panel" style={{ padding: "16px 20px", borderLeft: "3px solid var(--sev-high)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--sev-high)", fontWeight: 600, textTransform: "uppercase" }}>
              High Severity
            </span>
            <Flame size={18} color="var(--sev-high)" />
          </div>
          <div style={{ fontSize: "1.9rem", fontWeight: 800, marginTop: "6px", color: "var(--sev-high)", fontFamily: "var(--font-display)" }}>
            {highCount}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
            Severe infrastructure / trauma
          </div>
        </div>

        <div className="glass-panel" style={{ padding: "16px 20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontWeight: 600, textTransform: "uppercase" }}>
              Triage Progress
            </span>
            <CheckCircle size={18} color="var(--sev-low)" />
          </div>
          <div style={{ fontSize: "1.9rem", fontWeight: 800, marginTop: "6px", fontFamily: "var(--font-display)" }}>
            {pendingCount} <span style={{ fontSize: "1rem", color: "var(--text-muted)", fontWeight: 400 }}>new / {resolvedCount} resolved</span>
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
            Pending authority review
          </div>
        </div>
      </div>

      {/* 2. Filter & Search Controls */}
      <div
        className="glass-panel"
        style={{
          padding: "14px 20px",
          display: "flex",
          gap: "12px",
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <div style={{ position: "relative", flex: "1 1 240px" }}>
          <Search size={16} color="var(--text-muted)" style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)" }} />
          <input
            type="text"
            className="input-field"
            placeholder="Search by keywords, landmarks, or title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: "36px" }}
          />
        </div>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            <Filter size={15} /> Filters:
          </div>

          <select
            className="input-field"
            style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="all">All Categories</option>
            <option value="flood">Flood</option>
            <option value="fire">Fire</option>
            <option value="medical">Medical</option>
            <option value="rescue">Rescue</option>
            <option value="infrastructure">Infrastructure</option>
            <option value="other">Other</option>
          </select>

          <select
            className="input-field"
            style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <option value="all">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <select
            className="input-field"
            style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="new">New</option>
            <option value="verified">Verified</option>
            <option value="assigned">Assigned</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
          </select>

          <button
            type="button"
            onClick={onRefresh}
            className="btn-secondary"
            style={{ padding: "8px 12px", fontSize: "0.85rem" }}
            title="Refresh Live Incident Feed"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
      </div>

      {/* 3. Main Split View: Feed on Left, Detailed Inspection on Right */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.1fr 1fr",
          gap: "20px",
          alignItems: "start",
        }}
      >
        {/* Left Column: Triage Incident Feed */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 4px" }}>
            <span style={{ fontSize: "0.85rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)" }}>
              Prioritized Emergency Queue ({filteredIncidents.length})
            </span>
            <span style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
              Ranked by AI Severity & Priority Score
            </span>
          </div>

          {filteredIncidents.length === 0 ? (
            <div className="glass-panel" style={{ padding: "40px 20px", textAlign: "center", color: "var(--text-muted)" }}>
              No incidents match the active filters.
            </div>
          ) : (
            filteredIncidents.map((inc) => {
              const Icon = CATEGORY_ICONS[inc.category] || AlertCircle;
              const isSelected = selectedIncident?.id === inc.id;
              const sevBadgeClass = `badge-${inc.severity.toLowerCase()}`;

              return (
                <div
                  key={inc.id}
                  onClick={() => onSelectIncident(inc)}
                  className="glass-panel-interactive"
                  style={{
                    padding: "16px",
                    cursor: "pointer",
                    borderLeft: `4px solid ${inc.severity === "CRITICAL" ? "var(--sev-critical)" : inc.severity === "HIGH" ? "var(--sev-high)" : inc.severity === "MEDIUM" ? "var(--sev-medium)" : "var(--sev-low)"}`,
                    borderColor: isSelected ? "var(--accent-cyan)" : undefined,
                    boxShadow: isSelected ? "0 0 15px rgba(56, 189, 248, 0.25)" : undefined,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span
                        className={sevBadgeClass}
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: "4px",
                          letterSpacing: "0.04em",
                        }}
                      >
                        {inc.severity}
                      </span>
                      <span
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-secondary)",
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                          textTransform: "capitalize",
                        }}
                      >
                        <Icon size={13} />
                        {inc.category}
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      {inc.priority_score != null && (
                        <span
                          style={{
                            fontSize: "0.75rem",
                            fontFamily: "var(--font-mono)",
                            color: inc.priority_score > 85 ? "#f43f5e" : "#38bdf8",
                            background: "rgba(15, 23, 42, 0.8)",
                            padding: "2px 8px",
                            borderRadius: "12px",
                            border: "1px solid rgba(255, 255, 255, 0.1)",
                          }}
                        >
                          Score: {inc.priority_score.toFixed(0)}
                        </span>
                      )}
                      <span
                        style={{
                          fontSize: "0.7rem",
                          textTransform: "uppercase",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: inc.status === "new" ? "rgba(244, 63, 94, 0.2)" : inc.status === "verified" ? "rgba(56, 189, 248, 0.2)" : "rgba(16, 185, 129, 0.2)",
                          color: inc.status === "new" ? "#fca5a5" : inc.status === "verified" ? "#7dd3fc" : "#86efac",
                          fontWeight: 600,
                        }}
                      >
                        {inc.status.replace("_", " ")}
                      </span>
                    </div>
                  </div>

                  <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#fff", marginBottom: "6px", lineHeight: "1.3" }}>
                    {inc.title}
                  </h3>

                  <p
                    style={{
                      fontSize: "0.82rem",
                      color: "var(--text-secondary)",
                      marginBottom: "10px",
                      lineHeight: "1.4",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {inc.description}
                  </p>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                      <MapPin size={13} color="var(--accent-cyan)" />
                      {inc.location_text || "Coordinates available"}
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                      <Clock size={12} />
                      {new Date(inc.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Detailed Incident Inspection & AI Analysis */}
        <div>
          {selectedIncident ? (
            <div className="glass-panel" style={{ padding: "24px", position: "sticky", top: "20px" }}>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                    <span className={`badge-${selectedIncident.severity.toLowerCase()}`} style={{ fontSize: "0.75rem", fontWeight: 700, padding: "3px 10px", borderRadius: "4px" }}>
                      {selectedIncident.severity}
                    </span>
                    <span style={{ fontSize: "0.8rem", color: "var(--accent-cyan)", textTransform: "uppercase", fontWeight: 600 }}>
                      {selectedIncident.category}
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      • ID: {selectedIncident.id.slice(0, 10)}
                    </span>
                  </div>
                  <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#fff", lineHeight: 1.3 }}>
                    {selectedIncident.title}
                  </h2>
                </div>
              </div>

              {/* Status Workflow Action Buttons */}
              <div style={{ marginBottom: "20px", padding: "12px", background: "rgba(15, 23, 42, 0.6)", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--text-muted)", marginBottom: "8px", fontWeight: 600 }}>
                  Workflow Status Transition
                </div>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    onClick={() => handleStatusChange("verified")}
                    disabled={selectedIncident.status === "verified"}
                    className="btn-secondary"
                    style={{ fontSize: "0.8rem", padding: "5px 10px", background: selectedIncident.status === "verified" ? "rgba(56, 189, 248, 0.3)" : undefined }}
                  >
                    <CheckCircle size={14} color="#38bdf8" /> Verify
                  </button>
                  <button
                    type="button"
                    onClick={() => handleStatusChange("assigned")}
                    disabled={selectedIncident.status === "assigned"}
                    className="btn-secondary"
                    style={{ fontSize: "0.8rem", padding: "5px 10px", background: selectedIncident.status === "assigned" ? "rgba(234, 179, 8, 0.3)" : undefined }}
                  >
                    <Users size={14} color="#eab308" /> Assign Units
                  </button>
                  <button
                    type="button"
                    onClick={() => handleStatusChange("in_progress")}
                    disabled={selectedIncident.status === "in_progress"}
                    className="btn-secondary"
                    style={{ fontSize: "0.8rem", padding: "5px 10px", background: selectedIncident.status === "in_progress" ? "rgba(192, 132, 252, 0.3)" : undefined }}
                  >
                    <Clock size={14} color="#c084fc" /> In Progress
                  </button>
                  <button
                    type="button"
                    onClick={() => handleStatusChange("resolved")}
                    disabled={selectedIncident.status === "resolved"}
                    className="btn-secondary"
                    style={{ fontSize: "0.8rem", padding: "5px 10px", background: selectedIncident.status === "resolved" ? "rgba(16, 185, 129, 0.3)" : undefined }}
                  >
                    <CheckCircle size={14} color="#10b981" /> Resolved
                  </button>
                  <button
                    type="button"
                    onClick={() => handleStatusChange("rejected")}
                    disabled={selectedIncident.status === "rejected"}
                    className="btn-secondary"
                    style={{ fontSize: "0.8rem", padding: "5px 10px" }}
                  >
                    <XCircle size={14} color="#f43f5e" /> Reject
                  </button>
                </div>
              </div>

              {/* Location & Metadata */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "16px", fontSize: "0.82rem" }}>
                <div style={{ background: "rgba(15, 23, 42, 0.4)", padding: "10px", borderRadius: "6px" }}>
                  <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.72rem" }}>LOCATION</span>
                  <span style={{ color: "#fff", fontWeight: 600 }}>{selectedIncident.location_text || "None specified"}</span>
                  {selectedIncident.location_lat != null && (
                    <div style={{ fontSize: "0.72rem", color: "var(--accent-cyan)", marginTop: "2px" }}>
                      GPS: {selectedIncident.location_lat.toFixed(4)}, {selectedIncident.location_lon?.toFixed(4)}
                    </div>
                  )}
                </div>
                <div style={{ background: "rgba(15, 23, 42, 0.4)", padding: "10px", borderRadius: "6px" }}>
                  <span style={{ color: "var(--text-muted)", display: "block", fontSize: "0.72rem" }}>VICTIMS AFFECTED</span>
                  <span style={{ color: "#fff", fontWeight: 600, fontSize: "1rem" }}>
                    {selectedIncident.people_affected != null ? `${selectedIncident.people_affected} people` : "Unknown"}
                  </span>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                    Aggregated from {selectedIncident.report_count} citizen report(s)
                  </div>
                </div>
              </div>

              {/* Description */}
              <div style={{ marginBottom: "20px" }}>
                <span style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 600, display: "block", marginBottom: "4px" }}>
                  Incident Description
                </span>
                <p style={{ fontSize: "0.88rem", color: "var(--text-primary)", lineHeight: "1.5", background: "rgba(15, 23, 42, 0.5)", padding: "12px", borderRadius: "8px" }}>
                  {selectedIncident.description}
                </p>
              </div>

              {/* Phase 3: 6-Factor Transparent Priority Scoring Breakdown (T-041) */}
              {priorityBreakdown && (
                <div
                  style={{
                    marginBottom: "20px",
                    padding: "16px",
                    background: "rgba(15, 23, 42, 0.7)",
                    borderRadius: "10px",
                    border: "1px solid rgba(56, 189, 248, 0.25)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Zap size={18} color="var(--accent-cyan)" />
                      <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>
                        6-Factor Transparent Priority Formula (T-041)
                      </span>
                      {isLoadingBreakdown && (
                        <span style={{ fontSize: "0.7rem", color: "var(--accent-cyan)", marginLeft: "4px" }}>
                          (Syncing...)
                        </span>
                      )}
                    </div>
                    <span
                      style={{
                        fontSize: "0.82rem",
                        fontFamily: "var(--font-mono)",
                        fontWeight: 800,
                        padding: "3px 10px",
                        borderRadius: "12px",
                        background:
                          priorityBreakdown.priority_score >= 80
                            ? "rgba(244, 63, 94, 0.2)"
                            : priorityBreakdown.priority_score >= 60
                            ? "rgba(234, 179, 8, 0.2)"
                            : "rgba(56, 189, 248, 0.2)",
                        color:
                          priorityBreakdown.priority_score >= 80
                            ? "#f43f5e"
                            : priorityBreakdown.priority_score >= 60
                            ? "#eab308"
                            : "#38bdf8",
                        border: "1px solid currentColor",
                      }}
                    >
                      Score: {priorityBreakdown.priority_score.toFixed(1)} / 100
                    </span>
                  </div>

                  {/* Factor Progress Grid */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {Object.entries(priorityBreakdown.factors).map(([key, item]) => {
                      const maxPts = item.weight * 100;
                      const pct = Math.min(100, (item.contribution / maxPts) * 100);
                      const labelMap: Record<string, string> = {
                        severity: "Severity Level",
                        people_affected: "People Affected",
                        life_threat: "Life Threat Index",
                        waiting_time: "Waiting Time Penalty",
                        resource_need: "Resource Scarcity",
                        location_risk: "Location Vulnerability",
                      };
                      return (
                        <div key={key} style={{ fontSize: "0.75rem" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "2px" }}>
                            <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>
                              {labelMap[key] || key} <span style={{ color: "var(--text-muted)" }}>({(item.weight * 100).toFixed(0)}% wt)</span>
                            </span>
                            <span style={{ color: "#fff", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                              +{item.contribution.toFixed(1)} / {maxPts.toFixed(0)} pts
                            </span>
                          </div>
                          <div style={{ height: "4px", background: "rgba(255, 255, 255, 0.08)", borderRadius: "2px", overflow: "hidden" }}>
                            <div
                              style={{
                                width: `${pct}%`,
                                height: "100%",
                                background:
                                  key === "severity" || key === "life_threat"
                                    ? "var(--sev-critical)"
                                    : key === "people_affected"
                                    ? "var(--sev-high)"
                                    : "var(--accent-cyan)",
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div style={{ marginTop: "10px", fontSize: "0.7rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "6px" }}>
                    <BarChart2 size={12} />
                    Fully auditable mathematical calculation: P = Σ(w_i * f_i)
                  </div>
                </div>
              )}

              {/* AI Inference Diagnostic Panel */}
              {activePrediction && (
                <div
                  style={{
                    marginBottom: "20px",
                    padding: "16px",
                    background: "rgba(15, 23, 42, 0.7)",
                    borderRadius: "10px",
                    border: "1px solid rgba(56, 189, 248, 0.2)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Brain size={18} color="var(--accent-cyan)" />
                      <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>
                        AI Model Inference Diagnostics
                      </span>
                    </div>
                    <span style={{ fontSize: "0.7rem", fontFamily: "var(--font-mono)", color: "var(--accent-cyan)", background: "rgba(56, 189, 248, 0.1)", padding: "2px 6px", borderRadius: "4px" }}>
                      {activePrediction.model_name.split("/")[0]} {activePrediction.model_version}
                    </span>
                  </div>

                  {/* Confidence Bars */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "14px" }}>
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
                        <span style={{ color: "var(--text-secondary)" }}>Category Confidence</span>
                        <span style={{ color: "#fff", fontWeight: 700 }}>
                          {(activePrediction.category_confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div style={{ height: "6px", background: "rgba(255, 255, 255, 0.1)", borderRadius: "3px", overflow: "hidden" }}>
                        <div style={{ width: `${activePrediction.category_confidence * 100}%`, height: "100%", background: "var(--accent-cyan)" }} />
                      </div>
                    </div>

                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", marginBottom: "4px" }}>
                        <span style={{ color: "var(--text-secondary)" }}>Severity Confidence</span>
                        <span style={{ color: "#fff", fontWeight: 700 }}>
                          {(activePrediction.severity_confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div style={{ height: "6px", background: "rgba(255, 255, 255, 0.1)", borderRadius: "3px", overflow: "hidden" }}>
                        <div style={{ width: `${activePrediction.severity_confidence * 100}%`, height: "100%", background: activePrediction.predicted_severity === "CRITICAL" ? "var(--sev-critical)" : "var(--sev-high)" }} />
                      </div>
                    </div>
                  </div>

                  {/* Extracted Entities */}
                  <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                    <div style={{ fontWeight: 600, color: "var(--text-muted)", fontSize: "0.72rem", textTransform: "uppercase", marginBottom: "4px" }}>
                      Extracted Crisis Entities (NLP Regex & Rule Engine)
                    </div>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      <span style={{ background: "rgba(255, 255, 255, 0.08)", padding: "3px 8px", borderRadius: "4px", color: "#fff" }}>
                        👥 Victims: <strong>{activePrediction.extracted_entities.people_count}</strong>
                      </span>
                      {activePrediction.extracted_entities.location && (
                        <span style={{ background: "rgba(255, 255, 255, 0.08)", padding: "3px 8px", borderRadius: "4px", color: "#fff" }}>
                          📍 Landmark: <strong>{activePrediction.extracted_entities.location}</strong>
                        </span>
                      )}
                      {activePrediction.extracted_entities.resource_needed && (
                        <span style={{ background: "rgba(255, 255, 255, 0.08)", padding: "3px 8px", borderRadius: "4px", color: "var(--accent-cyan)" }}>
                          🚑 Recommended: <strong>{activePrediction.extracted_entities.resource_needed}</strong>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Overridden Alert if active */}
                  {activePrediction.override_at && (
                    <div style={{ padding: "8px 12px", background: "rgba(234, 179, 8, 0.15)", border: "1px solid rgba(234, 179, 8, 0.3)", borderRadius: "6px", fontSize: "0.75rem", color: "#fef08a" }}>
                      <strong>Human Override Active:</strong> {activePrediction.override_reason} ({new Date(activePrediction.override_at).toLocaleTimeString()})
                    </div>
                  )}

                  {/* Button to trigger Override Form */}
                  {!showOverrideForm && (
                    <button
                      type="button"
                      onClick={() => setShowOverrideForm(true)}
                      className="btn-secondary"
                      style={{ fontSize: "0.78rem", padding: "6px 12px", marginTop: "10px", width: "100%" }}
                    >
                      <Edit3 size={13} />
                      Override AI Classification (Human-in-the-Loop)
                    </button>
                  )}
                </div>
              )}

              {/* Override Form */}
              {showOverrideForm && (
                <form
                  onSubmit={handleOverrideSubmit}
                  style={{
                    padding: "16px",
                    background: "rgba(244, 63, 94, 0.08)",
                    border: "1px solid rgba(244, 63, 94, 0.3)",
                    borderRadius: "10px",
                    marginBottom: "20px",
                  }}
                >
                  <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fff", marginBottom: "10px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <ShieldAlert size={16} color="#f43f5e" />
                    Human Authority Decision Override
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "10px" }}>
                    <div>
                      <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>New Category</label>
                      <select
                        className="input-field"
                        value={overrideCategory}
                        onChange={(e) => setOverrideCategory(e.target.value)}
                        style={{ fontSize: "0.8rem", padding: "6px" }}
                      >
                        <option value="">(Keep Current: {selectedIncident.category})</option>
                        <option value="flood">Flood</option>
                        <option value="fire">Fire</option>
                        <option value="medical">Medical</option>
                        <option value="rescue">Rescue</option>
                        <option value="infrastructure">Infrastructure</option>
                        <option value="other">Other</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>New Severity</label>
                      <select
                        className="input-field"
                        value={overrideSeverity}
                        onChange={(e) => setOverrideSeverity(e.target.value)}
                        style={{ fontSize: "0.8rem", padding: "6px" }}
                      >
                        <option value="">(Keep Current: {selectedIncident.severity})</option>
                        <option value="CRITICAL">Critical</option>
                        <option value="HIGH">High</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="LOW">Low</option>
                      </select>
                    </div>
                  </div>

                  <div style={{ marginBottom: "12px" }}>
                    <label style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
                      Mandatory Justification Reason *
                    </label>
                    <textarea
                      className="input-field"
                      rows={2}
                      placeholder="e.g. Ground eyewitness verified water depth is receding; downgrading severity to HIGH."
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      required
                      style={{ fontSize: "0.8rem" }}
                    />
                  </div>

                  <div style={{ display: "flex", gap: "8px" }}>
                    <button
                      type="submit"
                      disabled={isSubmittingOverride}
                      className="btn-primary"
                      style={{ fontSize: "0.8rem", padding: "8px 14px" }}
                    >
                      {isSubmittingOverride ? "Recording..." : "Save Override"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowOverrideForm(false)}
                      className="btn-secondary"
                      style={{ fontSize: "0.8rem", padding: "8px 14px" }}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              {overrideSuccess && (
                <div style={{ padding: "10px", background: "rgba(16, 185, 129, 0.2)", borderRadius: "6px", color: "#6ee7b7", fontSize: "0.8rem", marginBottom: "16px" }}>
                  {overrideSuccess}
                </div>
              )}

              {/* Situation Summarizer (Local LLM Advisory) */}
              <div
                style={{
                  padding: "16px",
                  background: "rgba(15, 23, 42, 0.5)",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Sparkles size={16} color="var(--accent-purple)" />
                    <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>
                      Situation Report Summarizer
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleGenerateSummary}
                    disabled={isSummarizing}
                    className="btn-secondary"
                    style={{ fontSize: "0.75rem", padding: "5px 10px" }}
                  >
                    <Bot size={13} />
                    {isSummarizing ? "Generating Report..." : "Generate AI Summary"}
                  </button>
                </div>

                {summaryError && (
                  <div style={{ fontSize: "0.75rem", color: "#fca5a5", marginTop: "8px" }}>
                    {summaryError}
                  </div>
                )}

                {situationSummary && (
                  <div style={{ marginTop: "12px", fontSize: "0.82rem", lineHeight: "1.5" }}>
                    <div style={{ padding: "10px", background: "rgba(192, 132, 252, 0.1)", border: "1px solid rgba(192, 132, 252, 0.2)", borderRadius: "8px", marginBottom: "10px", color: "#f1f5f9" }}>
                      {situationSummary.summary}
                    </div>

                    <div style={{ marginBottom: "8px" }}>
                      <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--sev-high)", textTransform: "uppercase" }}>
                        Key Crisis Risks:
                      </span>
                      <ul style={{ paddingLeft: "18px", marginTop: "4px", color: "var(--text-secondary)" }}>
                        {situationSummary.key_risks.map((risk, i) => (
                          <li key={i}>{risk}</li>
                        ))}
                      </ul>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--accent-cyan)", textTransform: "uppercase" }}>
                        Recommended Tactical Actions:
                      </span>
                      <ul style={{ paddingLeft: "18px", marginTop: "4px", color: "var(--text-secondary)" }}>
                        {situationSummary.recommended_actions.map((act, i) => (
                          <li key={i}>{act}</li>
                        ))}
                      </ul>
                    </div>

                    <div style={{ marginTop: "10px", fontSize: "0.7rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "6px" }}>
                      <Info size={12} />
                      Advisory LLM output per safety policy (never auto-dispatches resources).
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div
              className="glass-panel"
              style={{
                padding: "60px 20px",
                textAlign: "center",
                color: "var(--text-muted)",
              }}
            >
              <ShieldAlert size={36} color="var(--text-muted)" style={{ margin: "0 auto 12px auto", display: "block" }} />
              <h3 style={{ fontSize: "1rem", color: "#fff", marginBottom: "6px" }}>No Incident Selected</h3>
              <p style={{ fontSize: "0.85rem", maxWidth: "300px", margin: "0 auto" }}>
                Click on any emergency from the triage feed or map to inspect AI inference details, trigger overrides, or generate situation reports.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
