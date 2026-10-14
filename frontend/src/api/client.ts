/**
 * API Client for DisasterFlow backend.
 * Base URL defaults to http://localhost:8000/api/v1
 */

export const API_BASE = "http://localhost:8000/api/v1";

export interface IncidentSummary {
  id: string;
  title: string;
  description: string;
  category: "medical" | "rescue" | "infrastructure" | "fire" | "flood" | "other";
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: "new" | "verified" | "assigned" | "in_progress" | "resolved" | "rejected";
  priority_score: number | null;
  people_affected: number | null;
  location_text: string | null;
  location_lat: number | null;
  location_lon: number | null;
  report_count: number;
  created_at: string;
  updated_at: string;
}

export interface ExtractedEntities {
  people_count: number;
  location: string | null;
  resource_needed: string | null;
}

export interface AIPrediction {
  id: string;
  report_id: string;
  model_name: string;
  model_version: string;
  predicted_category: string;
  category_confidence: number;
  predicted_severity: string;
  severity_confidence: number;
  final_category: string;
  final_severity: string;
  extracted_entities: ExtractedEntities;
  raw_output: Record<string, any>;
  override_category: string | null;
  override_severity: string | null;
  override_reason: string | null;
  override_at: string | null;
}

export interface SituationSummary {
  summary: string;
  key_risks: string[];
  recommended_actions: string[];
  total_reports: number;
  estimated_people_affected: number;
  primary_category: string;
  severity: string;
  is_fallback: boolean;
}

export interface ResourceItem {
  id: string;
  name: string;
  type: "ambulance" | "boat" | "rescue_team" | "medical_kit" | "food_kit" | "other";
  status: "available" | "assigned" | "offline";
  capacity: number;
  latitude: number | null;
  longitude: number | null;
  created_at: string;
  updated_at: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: "citizen" | "authority" | "rescue" | "admin";
}

export interface PriorityFactorDetail {
  weight: number;
  raw_factor: number;
  contribution: number;
  explanation: string;
}

export interface PriorityBreakdownResponse {
  incident_id: string;
  incident_title: string;
  priority_score: number;
  factors: {
    severity: PriorityFactorDetail;
    people_affected: PriorityFactorDetail;
    life_threat: PriorityFactorDetail;
    waiting_time: PriorityFactorDetail;
    resource_need: PriorityFactorDetail;
    location_risk: PriorityFactorDetail;
  };
  calculated_at: string;
}

export interface AllocationMatch {
  incident_id: string;
  incident_title: string;
  incident_priority: number;
  incident_lat: number | null;
  incident_lon: number | null;
  resource_id: string;
  resource_name: string;
  resource_type: string;
  resource_lat: number | null;
  resource_lon: number | null;
  distance_km: number;
  cost: number;
}

export interface AllocationRecommendation {
  recommended_matches: AllocationMatch[];
  total_matches: number;
  unassigned_incidents: number;
  available_resources: number;
  algorithm: string;
  status: string;
}

export interface AssignmentItem {
  id: string;
  incident_id: string;
  resource_id: string;
  status: string;
  priority: number;
  assigned_at: string;
  notes: string | null;
  incident_title?: string;
  resource_name?: string;
}

let authToken: string | null = localStorage.getItem("disaster_token");

export function setToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem("disaster_token", token);
  } else {
    localStorage.removeItem("disaster_token");
  }
}

export function getToken(): string | null {
  return authToken || localStorage.getItem("disaster_token");
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  const token = getToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) {
        errorDetail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  if (res.status === 204) {
    return {} as T;
  }
  return res.json();
}

export const api = {
  // Auth
  async login(formData: FormData) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      throw new Error("Invalid username or password");
    }
    const data = await res.json();
    setToken(data.access_token);
    return data;
  },

  async register(name: string, email: string, password: string, role = "citizen") {
    return request<{ id: string; name: string; email: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password, role }),
    });
  },

  async getMe(): Promise<UserProfile> {
    return request<UserProfile>("/users/me");
  },

  // Citizen Reporting
  async submitReport(payload: {
    title: string;
    raw_text: string;
    location_lat?: number | null;
    location_lon?: number | null;
    location_text?: string;
  }) {
    return request<{ id: string; status: string; message: string }>("/incidents/reports", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Incidents
  async getIncidents(params?: { category?: string; severity?: string; status?: string }): Promise<IncidentSummary[]> {
    const searchParams = new URLSearchParams();
    if (params?.category) searchParams.append("category", params.category);
    if (params?.severity) searchParams.append("severity", params.severity);
    if (params?.status) searchParams.append("status", params.status);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return request<IncidentSummary[]>(`/incidents${query}`);
  },

  async getIncident(id: string): Promise<any> {
    return request<any>(`/incidents/${id}`);
  },

  async updateIncidentStatus(id: string, status: string) {
    return request<IncidentSummary>(`/incidents/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },

  // AI & Predictions
  async getPredictionForReport(reportId: string): Promise<AIPrediction> {
    return request<AIPrediction>(`/predictions/reports/${reportId}`);
  },

  async overridePrediction(predictionId: string, overrideData: {
    override_category?: string;
    override_severity?: string;
    reason: string;
  }): Promise<AIPrediction> {
    return request<AIPrediction>(`/predictions/${predictionId}/override`, {
      method: "POST",
      body: JSON.stringify(overrideData),
    });
  },

  async summarizeIncident(incidentId: string): Promise<SituationSummary> {
    return request<SituationSummary>(`/predictions/incidents/${incidentId}/summarize`, {
      method: "POST",
    });
  },

  // Resources
  async getResources(params?: { type?: string; status?: string }): Promise<ResourceItem[]> {
    const searchParams = new URLSearchParams();
    if (params?.type) searchParams.append("type", params.type);
    if (params?.status) searchParams.append("status", params.status);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return request<ResourceItem[]>(`/resources${query}`);
  },

  async updateResource(id: string, payload: Partial<ResourceItem>) {
    return request<ResourceItem>(`/resources/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  // Phase 3 Intelligent Engine Endpoints
  async getRankedIncidents(limit = 50): Promise<IncidentSummary[]> {
    return request<IncidentSummary[]>(`/incidents/ranked?limit=${limit}`);
  },

  async getPriorityBreakdown(incidentId: string): Promise<PriorityBreakdownResponse> {
    return request<PriorityBreakdownResponse>(`/incidents/${incidentId}/priority-breakdown`);
  },

  async recommendAllocations(payload?: { max_distance_km?: number }): Promise<AllocationRecommendation> {
    return request<AllocationRecommendation>("/allocations/recommend", {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  async approveAllocation(payload: { incident_id: string; resource_id: string; priority?: number; notes?: string }) {
    return request<{ message: string; assignment_id: string; resource_status: string; incident_status: string }>("/allocations/approve", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getMyAssignments(): Promise<AssignmentItem[]> {
    return request<AssignmentItem[]>("/allocations/assignments/mine");
  },

  async updateAssignmentStatus(assignmentId: string, status: string) {
    return request<{ message: string; assignment_id: string; status: string }>(`/allocations/assignments/${assignmentId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },
};
