/**
 * Interactive Leaflet + OpenStreetMap Emergency Map Component (T-020).
 * Renders color-coded incident markers and deployable resource locations.
 */

import React, { useEffect, useRef } from "react";
import L from "leaflet";
import type { IncidentSummary, ResourceItem } from "../api/client";

interface EmergencyMapProps {
  incidents: IncidentSummary[];
  resources?: ResourceItem[];
  selectedIncidentId?: string | null;
  onSelectIncident?: (incident: IncidentSummary) => void;
  center?: [number, number];
  zoom?: number;
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#f43f5e",
  HIGH: "#f97316",
  MEDIUM: "#eab308",
  LOW: "#10b981",
};

export const EmergencyMap: React.FC<EmergencyMapProps> = ({
  incidents,
  resources = [],
  selectedIncidentId,
  onSelectIncident,
  center = [28.6139, 77.2090], // Default center (e.g. Delhi / NCR)
  zoom = 12,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center,
      zoom,
      zoomControl: false,
    });

    // Dark-styled OpenStreetMap tile layer (zero cost)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    L.control.zoom({ position: "bottomright" }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;
    markersLayerRef.current = layerGroup;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync center and zoom changes dynamically
  useEffect(() => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.setView(center, zoom);
    }
  }, [center, zoom]);

  // Update Markers when incidents or resources change
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();

    // 1. Render Incident Markers
    incidents.forEach((inc) => {
      if (inc.location_lat == null || inc.location_lon == null) return;

      const color = SEVERITY_COLORS[inc.severity] || "#38bdf8";
      const isSelected = inc.id === selectedIncidentId;
      const size = isSelected ? 24 : 16;
      const pulseHtml =
        inc.severity === "CRITICAL"
          ? `<span style="position:absolute; width:100%; height:100%; border-radius:50%; background:${color}; opacity:0.6; animation:pulse-ring 1.8s infinite;"></span>`
          : "";

      const iconHtml = `
        <div style="position:relative; width:${size}px; height:${size}px; display:flex; align-items:center; justify-content:center;">
          ${pulseHtml}
          <div style="width:${size}px; height:${size}px; border-radius:50%; background:${color}; border:2px solid #ffffff; box-shadow:0 0 10px ${color};"></div>
        </div>
      `;

      const customIcon = L.divIcon({
        className: "custom-incident-pin",
        html: iconHtml,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      });

      const marker = L.marker([inc.location_lat, inc.location_lon], { icon: customIcon });

      const popupContent = document.createElement("div");
      popupContent.style.minWidth = "200px";
      popupContent.innerHTML = `
        <div style="font-family:inherit; padding:4px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="font-size:10px; font-weight:700; text-transform:uppercase; color:${color}; padding:2px 6px; border-radius:4px; background:${color}22;">
              ${inc.severity}
            </span>
            <span style="font-size:11px; text-transform:capitalize; color:#94a3b8;">${inc.category}</span>
          </div>
          <h4 style="font-size:13px; font-weight:700; margin:0 0 6px 0; color:#f8fafc; line-height:1.3;">
            ${inc.title}
          </h4>
          <p style="font-size:11px; color:#cbd5e1; margin:0 0 8px 0; max-height:45px; overflow:hidden;">
            ${inc.location_text || "Coordinates verified"}
          </p>
          <button id="inspect-btn-${inc.id}" style="width:100%; background:#2563eb; color:#fff; border:none; padding:6px 10px; font-size:11px; font-weight:600; border-radius:6px; cursor:pointer;">
            Inspect Triage Details &rarr;
          </button>
        </div>
      `;

      marker.bindPopup(popupContent);
      marker.on("popupopen", () => {
        const btn = document.getElementById(`inspect-btn-${inc.id}`);
        if (btn && onSelectIncident) {
          btn.onclick = () => {
            onSelectIncident(inc);
            marker.closePopup();
          };
        }
      });

      markersLayerRef.current?.addLayer(marker);
    });

    // 2. Render Deployable Resource Markers
    resources.forEach((res) => {
      if (res.latitude == null || res.longitude == null) return;
      if (res.status === "offline") return;

      const resColor = res.status === "available" ? "#38bdf8" : "#94a3b8";
      const iconHtml = `
        <div style="width:14px; height:14px; border-radius:3px; background:${resColor}; border:2px solid #fff; transform:rotate(45deg); box-shadow:0 0 8px ${resColor};"></div>
      `;

      const resourceIcon = L.divIcon({
        className: "custom-resource-pin",
        html: iconHtml,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });

      const marker = L.marker([res.latitude, res.longitude], { icon: resourceIcon });
      marker.bindPopup(`
        <div style="font-family:inherit; padding:4px;">
          <div style="font-size:10px; text-transform:uppercase; color:${resColor}; font-weight:700;">
            ${res.status} ${res.type}
          </div>
          <h4 style="font-size:13px; font-weight:700; color:#fff; margin:2px 0 4px 0;">${res.name}</h4>
          <div style="font-size:11px; color:#94a3b8;">Capacity: ${res.capacity} units</div>
        </div>
      `);

      markersLayerRef.current?.addLayer(marker);
    });
  }, [incidents, resources, selectedIncidentId, onSelectIncident]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: "350px" }}>
      <div ref={mapContainerRef} style={{ width: "100%", height: "100%" }} />
      {/* Map Legend Overlay */}
      <div
        style={{
          position: "absolute",
          top: "14px",
          right: "14px",
          zIndex: 1000,
          background: "rgba(15, 23, 42, 0.85)",
          backdropFilter: "blur(8px)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          padding: "8px 12px",
          borderRadius: "8px",
          fontSize: "11px",
          display: "flex",
          gap: "12px",
          alignItems: "center",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#f43f5e" }}></span> Critical
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#f97316" }}></span> High
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#eab308" }}></span> Medium
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#38bdf8" }}></span> Resource
        </span>
      </div>
    </div>
  );
};
