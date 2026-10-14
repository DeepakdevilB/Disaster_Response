/**
 * Resource Fleet & Emergency Equipment Panel (T-021).
 * Live monitoring and dispatch status management for deployable assets.
 */

import React, { useState } from "react";
import {
  Activity,
  AlertCircle,
  Anchor,
  LifeBuoy,
  MapPin,
  RefreshCw,
  Search,
  Truck,
  Users,
} from "lucide-react";
import type { ResourceItem } from "../api/client";
import { api } from "../api/client";

interface ResourcePanelProps {
  resources: ResourceItem[];
  onResourceUpdated: (updated: ResourceItem) => void;
  onRefresh: () => void;
  onFocusCoordinates?: (lat: number, lon: number) => void;
}

const TYPE_ICONS: Record<string, React.ElementType> = {
  ambulance: Truck,
  boat: Anchor,
  rescue_team: Users,
  medical_kit: Activity,
  food_kit: LifeBuoy,
  other: AlertCircle,
};

export const ResourcePanel: React.FC<ResourcePanelProps> = ({
  resources,
  onResourceUpdated,
  onRefresh,
  onFocusCoordinates,
}) => {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const filteredResources = resources.filter((res) => {
    if (typeFilter !== "all" && res.type !== typeFilter) return false;
    if (statusFilter !== "all" && res.status !== statusFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      if (!res.name.toLowerCase().includes(q) && !res.type.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  const availableCount = resources.filter((r) => r.status === "available").length;
  const assignedCount = resources.filter((r) => r.status === "assigned").length;
  const offlineCount = resources.filter((r) => r.status === "offline").length;

  const handleToggleStatus = async (res: ResourceItem) => {
    const nextStatusMap: Record<string, "available" | "assigned" | "offline"> = {
      available: "assigned",
      assigned: "offline",
      offline: "available",
    };
    const nextStatus = nextStatusMap[res.status] || "available";

    // oxlint-disable-next-line react/purity
    const nowIso = new Date().toISOString();
    const updated: ResourceItem = { ...res, status: nextStatus, updated_at: nowIso };
    onResourceUpdated(updated);

    try {
      await api.updateResource(res.id, { status: nextStatus }).catch(() => {
        // mock fallback
      });
    } catch {
      // ignore
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* 1. Fleet Stat Overview */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "14px" }}>
        <div className="glass-panel" style={{ padding: "16px 20px" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: 600, textTransform: "uppercase" }}>
            Total Deployable Assets
          </span>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, marginTop: "4px", fontFamily: "var(--font-display)" }}>
            {resources.length}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Ambulances, Boats, Teams & Kits</div>
        </div>

        <div className="glass-panel" style={{ padding: "16px 20px", borderLeft: "3px solid var(--accent-cyan)" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", fontWeight: 600, textTransform: "uppercase", display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--accent-cyan)" }}></span> Available for Dispatch
          </span>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, marginTop: "4px", color: "var(--accent-cyan)", fontFamily: "var(--font-display)" }}>
            {availableCount}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Ready for Hungarian allocation</div>
        </div>

        <div className="glass-panel" style={{ padding: "16px 20px", borderLeft: "3px solid var(--sev-high)" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--sev-high)", fontWeight: 600, textTransform: "uppercase" }}>
            In Active Mission
          </span>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, marginTop: "4px", color: "var(--sev-high)", fontFamily: "var(--font-display)" }}>
            {assignedCount}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Currently deployed on incidents</div>
        </div>

        <div className="glass-panel" style={{ padding: "16px 20px" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontWeight: 600, textTransform: "uppercase" }}>
            Maintenance / Offline
          </span>
          <div style={{ fontSize: "1.8rem", fontWeight: 800, marginTop: "4px", fontFamily: "var(--font-display)" }}>
            {offlineCount}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Refueling or repairs</div>
        </div>
      </div>

      {/* 2. Controls Toolbar */}
      <div className="glass-panel" style={{ padding: "14px 20px", display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ position: "relative", flex: "1 1 200px" }}>
          <Search size={16} color="var(--text-muted)" style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)" }} />
          <input
            type="text"
            className="input-field"
            placeholder="Search equipment or teams..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ paddingLeft: "36px" }}
          />
        </div>

        <select className="input-field" style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="all">All Asset Types</option>
          <option value="boat">Rescue Boats</option>
          <option value="ambulance">Ambulances</option>
          <option value="rescue_team">SDRF/NDRF Rescue Teams</option>
          <option value="medical_kit">Trauma Kits</option>
          <option value="other">Fire Tenders & Heavy Assets</option>
        </select>

        <select className="input-field" style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          <option value="available">Available</option>
          <option value="assigned">Assigned</option>
          <option value="offline">Offline</option>
        </select>

        <button type="button" onClick={onRefresh} className="btn-secondary" style={{ padding: "8px 12px", fontSize: "0.85rem" }}>
          <RefreshCw size={15} />
          Refresh
        </button>
      </div>

      {/* 3. Resources Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "16px" }}>
        {filteredResources.map((res) => {
          const Icon = TYPE_ICONS[res.type] || AlertCircle;
          const statusBg =
            res.status === "available"
              ? "rgba(16, 185, 129, 0.15)"
              : res.status === "assigned"
              ? "rgba(249, 115, 22, 0.15)"
              : "rgba(100, 116, 139, 0.2)";
          const statusColor =
            res.status === "available" ? "#34d399" : res.status === "assigned" ? "#fb923c" : "#94a3b8";

          return (
            <div key={res.id} className="glass-panel" style={{ padding: "18px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "10px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <div style={{ padding: "8px", background: "rgba(56, 189, 248, 0.15)", borderRadius: "8px" }}>
                      <Icon size={20} color="var(--accent-cyan)" />
                    </div>
                    <div>
                      <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#fff", lineHeight: "1.3" }}>
                        {res.name}
                      </h4>
                      <span style={{ fontSize: "0.75rem", textTransform: "capitalize", color: "var(--text-secondary)" }}>
                        {res.type.replace("_", " ")}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleToggleStatus(res)}
                    style={{
                      background: statusBg,
                      color: statusColor,
                      border: `1px solid ${statusColor}44`,
                      borderRadius: "6px",
                      padding: "4px 8px",
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                    title="Click to cycle status"
                  >
                    <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: statusColor }}></span>
                    {res.status}
                  </button>
                </div>

                <div style={{ background: "rgba(15, 23, 42, 0.5)", padding: "10px", borderRadius: "6px", marginBottom: "12px", fontSize: "0.8rem", display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Carrying Capacity:</span>
                  <span style={{ color: "#fff", fontWeight: 600 }}>{res.capacity} units</span>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                {res.latitude != null && res.longitude != null ? (
                  <span
                    onClick={() => onFocusCoordinates && onFocusCoordinates(res.latitude!, res.longitude!)}
                    style={{ display: "flex", alignItems: "center", gap: "4px", color: "var(--accent-cyan)", cursor: "pointer" }}
                  >
                    <MapPin size={13} />
                    {res.latitude.toFixed(4)}, {res.longitude.toFixed(4)}
                  </span>
                ) : (
                  <span>Base Depot (GPS Pending)</span>
                )}
                <span>Click badge to cycle status</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
