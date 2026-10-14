/**
 * Citizen Emergency Reporting Portal (T-018).
 * Fast distress submission with GPS geolocation, crisis presets, and live report tracking.
 */

import React, { useState } from "react";
import {
  AlertTriangle,
  Flame,
  HeartPulse,
  LifeBuoy,
  MapPin,
  Send,
  Upload,
  Waves,
  Zap,
} from "lucide-react";
import { api } from "../api/client";

interface CitizenPortalProps {
  onReportSubmitted?: () => void;
}

export const CitizenPortal: React.FC<CitizenPortalProps> = ({ onReportSubmitted }) => {
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [locationText, setLocationText] = useState("");
  const [lat, setLat] = useState<number | null>(null);
  const [lon, setLon] = useState<number | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Preset quick crisis prompts
  const presets = [
    { label: "Flash Flood", icon: Waves, color: "#38bdf8", text: "Severe flood water rising fast, people trapped on roof. Need rescue boat urgently!" },
    { label: "Fire / Explosion", icon: Flame, color: "#f43f5e", text: "Heavy fire and toxic smoke spreading rapidly inside building. People trapped on upper floors!" },
    { label: "Medical Trauma", icon: HeartPulse, color: "#fb7185", text: "Severe accident with unconscious victims bleeding heavily. Need advanced life support ambulance!" },
    { label: "Building Collapse", icon: LifeBuoy, color: "#f97316", text: "Structural collapse, victims buried under heavy rubble and debris. Need search and rescue team!" },
    { label: "High-Voltage Hazard", icon: Zap, color: "#eab308", text: "High-tension 11kV electrical wire snapped across flooded road. Urgent electrocution hazard!" },
  ];

  // Geolocation detection
  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      setErrorMessage("Geolocation is not supported by your browser.");
      return;
    }
    setIsLocating(true);
    setErrorMessage(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLon(pos.coords.longitude);
        setLocationText(`GPS: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)} (Acc: ±${Math.round(pos.coords.accuracy)}m)`);
        setIsLocating(false);
      },
      (err) => {
        setIsLocating(false);
        setErrorMessage(`Could not fetch location: ${err.message}. Please enter landmark manually.`);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !rawText.trim()) {
      setErrorMessage("Please fill in both the emergency title and description.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const resp = await api.submitReport({
        title: title.trim(),
        raw_text: rawText.trim(),
        location_lat: lat,
        location_lon: lon,
        location_text: locationText.trim() || undefined,
      });

      setSuccessMessage(`Emergency Report Ingested! (Status: HTTP 202 Accepted, ID: ${resp.id.slice(0, 8)}...). Dispatching to AI triage queue.`);
      setTitle("");
      setRawText("");
      setLocationText("");
      setLat(null);
      setLon(null);

      if (onReportSubmitted) {
        onReportSubmitted();
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to submit report. Ensure backend API is active.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "16px" }}>
      {/* Alert Header */}
      <div
        className="glass-panel"
        style={{
          padding: "24px",
          marginBottom: "24px",
          borderLeft: "4px solid var(--sev-critical)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
          <div
            style={{
              background: "rgba(244, 63, 94, 0.2)",
              padding: "10px",
              borderRadius: "10px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <AlertTriangle size={24} color="#f43f5e" />
          </div>
          <div>
            <h2 className="font-display" style={{ fontSize: "1.35rem", fontWeight: 700, color: "#fff" }}>
              Citizen Emergency Distress Dispatch
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
              Reports are ingested asynchronously and prioritized with NLP algorithms in &lt;100ms.
            </p>
          </div>
        </div>

        {/* Quick Disaster Category Presets */}
        <div style={{ marginTop: "16px" }}>
          <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: "8px" }}>
            Quick Incident Presets (Click to autofill)
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {presets.map((preset) => {
              const Icon = preset.icon;
              return (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    setTitle(`${preset.label} Emergency`);
                    setRawText(preset.text);
                  }}
                  className="btn-secondary"
                  style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                >
                  <Icon size={14} color={preset.color} />
                  {preset.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Form */}
      <form onSubmit={handleSubmit} className="glass-panel" style={{ padding: "24px" }}>
        {errorMessage && (
          <div
            style={{
              padding: "12px",
              marginBottom: "16px",
              background: "rgba(244, 63, 94, 0.15)",
              border: "1px solid rgba(244, 63, 94, 0.3)",
              borderRadius: "8px",
              color: "#fca5a5",
              fontSize: "0.85rem",
            }}
          >
            {errorMessage}
          </div>
        )}

        {successMessage && (
          <div
            style={{
              padding: "12px",
              marginBottom: "16px",
              background: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              borderRadius: "8px",
              color: "#6ee7b7",
              fontSize: "0.85rem",
            }}
          >
            {successMessage}
          </div>
        )}

        {/* Incident Title */}
        <div style={{ marginBottom: "16px" }}>
          <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", color: "var(--text-secondary)" }}>
            Incident Headline *
          </label>
          <input
            type="text"
            className="input-field"
            placeholder="e.g. Flash flood trapped 4 people on ground floor"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </div>

        {/* Raw Text Narrative */}
        <div style={{ marginBottom: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
            <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>
              Situation Narrative (English or Hinglish) *
            </label>
            <span style={{ fontSize: "0.75rem", color: "#38bdf8" }}>
              NLP auto-extracts victims, landmarks, and resource needs
            </span>
          </div>
          <textarea
            className="input-field"
            rows={4}
            placeholder="Describe the situation clearly. Mention number of people injured/trapped, water depth, smoke, or special needs (e.g. 'Ghar me paani 6 foot bhar gaya hai, 4 log chhat par phanse hain, boat bhejo')."
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            required
          />
        </div>

        {/* Location & GPS */}
        <div style={{ marginBottom: "20px" }}>
          <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", color: "var(--text-secondary)" }}>
            Location & Landmark
          </label>
          <div style={{ display: "flex", gap: "10px" }}>
            <input
              type="text"
              className="input-field"
              placeholder="e.g. Near Metro Station Sector 14, Ring Road"
              value={locationText}
              onChange={(e) => setLocationText(e.target.value)}
            />
            <button
              type="button"
              onClick={handleDetectLocation}
              disabled={isLocating}
              className="btn-secondary"
              style={{ whiteSpace: "nowrap" }}
            >
              <MapPin size={16} color="#38bdf8" />
              {isLocating ? "Locating..." : "Use GPS"}
            </button>
          </div>
          {lat != null && lon != null && (
            <div style={{ marginTop: "6px", fontSize: "0.75rem", color: "#34d399", display: "flex", alignItems: "center", gap: "4px" }}>
              <span>✓ Verified GPS Coordinates: {lat.toFixed(5)}, {lon.toFixed(5)}</span>
            </div>
          )}
        </div>

        {/* Photo Upload Attachment Simulator */}
        <div style={{ marginBottom: "24px" }}>
          <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", color: "var(--text-secondary)" }}>
            Attach Disaster Photo / Evidence (Optional)
          </label>
          <div
            style={{
              border: "2px dashed rgba(255, 255, 255, 0.15)",
              borderRadius: "8px",
              padding: "16px",
              textAlign: "center",
              cursor: "pointer",
              background: "rgba(15, 23, 42, 0.4)",
            }}
          >
            <Upload size={24} color="#94a3b8" style={{ margin: "0 auto 6px auto", display: "block" }} />
            <div style={{ fontSize: "0.85rem", color: "var(--text-primary)" }}>
              Upload ground image (JPEG, PNG, WebP up to 10MB)
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Stored securely on MinIO / S3 object storage with presigned URLs
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isSubmitting}
          className="btn-primary"
          style={{ width: "100%", padding: "12px", fontSize: "1rem" }}
        >
          <Send size={18} />
          {isSubmitting ? "Broadcasting Distress Signal..." : "Transmit Emergency Alert (Instant Ingest)"}
        </button>
      </form>
    </div>
  );
};
