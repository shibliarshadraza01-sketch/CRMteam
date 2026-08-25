// Thin client for the Django REST backend (/api/v1/*). Handles JWT storage,
// attaching the Authorization header, and retrying once on 401 by refreshing
// the access token — the pattern every module's data-fetching hook builds on.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const ACCESS_TOKEN_KEY = "qualify-learn-crm-access";
const REFRESH_TOKEN_KEY = "qualify-learn-crm-refresh";

export type BackendRole = "SUPER_ADMIN" | "MANAGER" | "EMPLOYEE";

export type BackendUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: BackendRole;
};

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

// ---- DRF error-body → readable message --------------------------------
//
// The backend already returns correct, structured DRF errors. Historically
// this client threw a hardcoded `${method} ${path} failed (${status})` and
// only stashed the real body on `err.body`, which almost no call site read —
// so every validation failure surfaced to the user as a meaningless
// "POST /api/v1/... failed (400)". Everything below exists to turn the three
// shapes DRF actually produces into a sentence a user can act on:
//
//   {"email": ["user with this email address already exists."]}  → field errors
//   {"detail": "Not found."}                                     → single message
//   {"non_field_errors": ["Passwords do not match."]}            → form-level
//
// Anything unrecognised falls back to the generic string, so a non-JSON or
// empty body never produces a blank or "[object Object]" toast.

// "non_field_errors" / "first_name" → "First name". Field keys are only
// prefixed when they name a real field, so form-level errors read cleanly.
function humanizeFieldName(field: string): string {
  const withSpaces = field.replace(/_/g, " ").trim();
  if (!withSpaces) return field;
  return withSpaces.charAt(0).toUpperCase() + withSpaces.slice(1);
}

// DRF nests: a value may be a string, a list of strings, a list of nested
// error objects (writable nested serializers / many=True), or an object.
// Flatten any of those to plain sentences.
function flattenErrorValue(value: unknown): string[] {
  if (value == null) return [];
  if (typeof value === "string") return value.trim() ? [value.trim()] : [];
  if (typeof value === "number" || typeof value === "boolean") return [String(value)];
  if (Array.isArray(value)) return value.flatMap(flattenErrorValue);
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) => {
      const messages = flattenErrorValue(nested);
      if (!messages.length) return [];
      // Numeric keys come from list indexes (e.g. items[0]) — they add noise
      // rather than meaning, so the inner message is used as-is.
      if (/^\d+$/.test(key)) return messages;
      return messages.map((message) => `${humanizeFieldName(key)}: ${message}`);
    });
  }
  return [];
}

// Turn a parsed DRF error body into a single readable string, or null when
// the body carries nothing usable (so the caller can fall back).
export function formatApiErrorBody(body: unknown): string | null {
  if (body == null) return null;

  // Some error responses are a bare string or a bare list of strings.
  if (typeof body === "string") return body.trim() || null;
  if (Array.isArray(body)) {
    const messages = flattenErrorValue(body);
    return messages.length ? messages.join(" ") : null;
  }
  if (typeof body !== "object") return null;

  const record = body as Record<string, unknown>;

  // {"detail": "..."} — DRF's own shape for auth/permission/404 errors.
  // It never coexists meaningfully with field errors, so it wins outright.
  if (typeof record.detail === "string" && record.detail.trim()) {
    return record.detail.trim();
  }

  const parts: string[] = [];

  // Form-level errors first — they describe the submission as a whole.
  for (const key of ["non_field_errors", "detail"]) {
    if (key in record) {
      parts.push(...flattenErrorValue(record[key]));
    }
  }

  // Then per-field errors, prefixed with the humanized field name.
  for (const [field, value] of Object.entries(record)) {
    if (field === "non_field_errors" || field === "detail") continue;
    const messages = flattenErrorValue(value);
    if (!messages.length) continue;
    parts.push(...messages.map((message) => `${humanizeFieldName(field)}: ${message}`));
  }

  if (!parts.length) return null;
  // De-duplicate: the same message can arrive under several keys.
  return Array.from(new Set(parts)).join(" ");
}

// Build the ApiError for a failed response: read the body once, prefer the
// backend's real message, and fall back to the generic request description
// only when the body is empty or unparseable.
async function errorFromResponse(response: Response, fallback: string): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // no JSON body (HTML error page, empty 500, network-level truncation)
  }
  return new ApiError(response.status, body, formatApiErrorBody(body) ?? fallback);
}

export function getTokens(): { access: string | null; refresh: string | null } {
  if (typeof window === "undefined") return { access: null, refresh: null };
  const access = window.localStorage.getItem(ACCESS_TOKEN_KEY) ?? window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
  const refresh = window.localStorage.getItem(REFRESH_TOKEN_KEY) ?? window.sessionStorage.getItem(REFRESH_TOKEN_KEY);
  return { access, refresh };
}

export function setTokens(access: string, refresh: string, remember: boolean) {
  const storage = remember ? window.localStorage : window.sessionStorage;
  const other = remember ? window.sessionStorage : window.localStorage;
  storage.setItem(ACCESS_TOKEN_KEY, access);
  storage.setItem(REFRESH_TOKEN_KEY, refresh);
  other.removeItem(ACCESS_TOKEN_KEY);
  other.removeItem(REFRESH_TOKEN_KEY);
}

export function setAccessToken(access: string) {
  if (window.localStorage.getItem(REFRESH_TOKEN_KEY)) {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, access);
  } else {
    window.sessionStorage.setItem(ACCESS_TOKEN_KEY, access);
  }
}

export function clearTokens() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  window.sessionStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function rawRequest(path: string, options: RequestInit): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers
    }
  });
}

async function refreshAccessToken(): Promise<string | null> {
  const { refresh } = getTokens();
  if (!refresh) return null;

  const response = await rawRequest("/api/v1/auth/refresh/", {
    method: "POST",
    body: JSON.stringify({ refresh })
  });
  if (!response.ok) {
    clearTokens();
    notifySessionExpired();
    return null;
  }
  const data = await response.json();
  setAccessToken(data.access);
  return data.access as string;
}

// Final production operations pass — Part 8 (frontend API security):
// previously, a 401 with a dead/expired refresh token only forced a
// logout at the NEXT full page load (AuthGate's own mount-time check) —
// an in-session request failing mid-use just showed that one request's
// own error toast, leaving the user on a stale, effectively-logged-out
// page indefinitely. This event lets any mounted listener (AuthGate)
// react immediately instead of waiting for a manual refresh.
const SESSION_EXPIRED_EVENT = "qualify-learn-crm:session-expired";

function notifySessionExpired() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
}

export function onSessionExpired(handler: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(SESSION_EXPIRED_EVENT, handler);
  return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
}

// Authenticated request: attaches the access token, and on a 401 tries
// exactly one refresh-and-retry before giving up. Callers that need
// unauthenticated access (login, refresh itself) should call rawRequest
// directly instead.
export async function apiRequest<T = unknown>(
  path: string,
  options: RequestInit = {},
  { retry = true }: { retry?: boolean } = {}
): Promise<T> {
  const { access } = getTokens();
  const response = await rawRequest(path, {
    ...options,
    headers: {
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
      ...options.headers
    }
  });

  if (response.status === 401 && retry) {
    const newAccess = await refreshAccessToken();
    if (newAccess) {
      return apiRequest<T>(path, options, { retry: false });
    }
  }

  if (!response.ok) {
    throw await errorFromResponse(response, `${options.method ?? "GET"} ${path} failed (${response.status})`);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// Multipart file upload: deliberately skips the JSON Content-Type default —
// the browser sets its own multipart boundary when given a FormData body.
export async function apiUpload<T = unknown>(path: string, formData: FormData): Promise<T> {
  const { access } = getTokens();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { ...(access ? { Authorization: `Bearer ${access}` } : {}) },
    body: formData
  });
  if (!response.ok) {
    throw await errorFromResponse(response, `POST ${path} failed (${response.status})`);
  }
  return (await response.json()) as T;
}

// Binary download (CSV/XLSX export): returns the raw blob and the
// server-supplied filename, for a client-side download link.
export async function apiDownload(path: string): Promise<{ blob: Blob; filename: string }> {
  const { access } = getTokens();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { ...(access ? { Authorization: `Bearer ${access}` } : {}) }
  });
  if (!response.ok) {
    // Export endpoints stream a file on success but still return a JSON
    // error body on failure, so the same formatter applies here.
    throw await errorFromResponse(response, `GET ${path} failed (${response.status})`);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "export.csv";
  const blob = await response.blob();
  return { blob, filename };
}

// ---- Auth-specific calls ---------------------------------------------

export type LoginResult =
  | { kind: "tokens"; access: string; refresh: string; user: BackendUser }
  | { kind: "challenge"; challenge: string };

export async function login(email: string, password: string): Promise<LoginResult> {
  const response = await rawRequest("/api/v1/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  const data = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, data, formatApiErrorBody(data) ?? "Invalid email or password.");
  }
  if (data.secondary_verification_required) {
    return { kind: "challenge", challenge: data.challenge };
  }
  return { kind: "tokens", access: data.access, refresh: data.refresh, user: data.user };
}

export async function verifySuperAdmin(challenge: string, accessCode: string): Promise<LoginResult> {
  const response = await rawRequest("/api/v1/auth/super-admin/verify/", {
    method: "POST",
    body: JSON.stringify({ challenge, access_code: accessCode })
  });
  const data = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, data, formatApiErrorBody(data) ?? "Incorrect access code.");
  }
  return { kind: "tokens", access: data.access, refresh: data.refresh, user: data.user };
}

export async function fetchMe(): Promise<BackendUser> {
  return apiRequest<BackendUser>("/api/v1/auth/me/");
}

export async function logout(): Promise<void> {
  const { refresh } = getTokens();
  if (refresh) {
    try {
      await rawRequest("/api/v1/auth/logout/", { method: "POST", body: JSON.stringify({ refresh }) });
    } catch {
      // best-effort — clear local tokens regardless
    }
  }
  clearTokens();
}

// ---- Generic CRUD helpers for DRF's standard paginated list shape ----

export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

// ---- Lead import (CSV + Google Sheets) ---------------------------------

export type LeadImportPreview = {
  stage?: "preview" | "imported";
  source?: string;
  total: number;
  valid: number;
  invalid: number;
  // A COUNT of rows that imported with a fallback applied (e.g. an
  // unrecognised source defaulting to OTHER), not a list of messages —
  // see apps/crm/imports.py's preview_leads()/import_leads(), which both
  // return `warnings` as an int. This was previously typed `string[]`,
  // which would have rendered as garbage the moment anything displayed it.
  warnings: number;
  errors: Array<{ row: number; message?: string; error?: string }>;
  sample: Array<Record<string, unknown>>;
};

export type LeadImportResult = {
  stage?: "preview" | "imported";
  source?: string;
  total: number;
  created: number;
  failed: number;
  // Count, not a message list — see LeadImportPreview.warnings above.
  warnings: number;
  errors: Array<{ row: number; message?: string; error?: string }>;
  lead_ids: number[];
};

// `configured: false` is a real, expected state in an environment with no
// Google credentials — the UI must show it honestly rather than pretending
// a connection succeeded.
export type GoogleSheetStatus = { provider: string; configured: boolean; is_mock: boolean };

export const crm = {
  listLeads: (query = "") => apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/crm/leads/${query}`),
  createLead: (body: Record<string, unknown>) =>
    apiRequest("/api/v1/crm/leads/", { method: "POST", body: JSON.stringify(body) }),
  updateLead: (id: number | string, body: Record<string, unknown>) =>
    apiRequest(`/api/v1/crm/leads/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteLead: (id: number | string) => apiRequest(`/api/v1/crm/leads/${id}/`, { method: "DELETE" }),
  // Contextual, per-lead conversion. ONE endpoint serves all three roles:
  // authorization is entirely server-side (a lead outside the caller's
  // scope is a 404), and converting an already-converted lead is a 400
  // with a real message rather than a second customer. Returns the created
  // Customer row.
  convertLead: (id: number | string, body: Record<string, unknown> = {}) =>
    apiRequest<Record<string, unknown>>(`/api/v1/crm/leads/${id}/convert/`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  findDuplicateLeads: (id: number | string) =>
    apiRequest<Record<string, unknown>[]>(`/api/v1/crm/leads/${id}/duplicates/`),
  mergeLeads: (id: number | string, duplicateId: number | string) =>
    apiRequest(`/api/v1/crm/leads/${id}/merge/`, { method: "POST", body: JSON.stringify({ duplicate_id: duplicateId }) }),
  importLeads: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<{ created: number; failed: number; errors: Array<{ row: number; error: string }> }>(
      "/api/v1/crm/leads/import/",
      formData
    );
  },
  exportLeads: (format: "csv" | "xlsx", query = "") =>
    apiDownload(`/api/v1/crm/leads/export/?export_format=${format}${query ? `&${query.replace(/^\?/, "")}` : ""}`),

  // Staff-management pass. Bulk (re)assignment of leads to a Manager or an
  // Employee. Authorization is entirely server-side (Super Admin may target
  // anyone; a Manager only their own scope; an Employee is always refused),
  // so this client never decides who may be assigned what — it only renders
  // what the server allows and surfaces the error it returns.
  assignLeads: (body: { lead_ids: Array<number | string>; target_type: "manager" | "employee"; target_user_id: number }) =>
    apiRequest<Record<string, unknown>[]>("/api/v1/crm/leads/assign/", { method: "POST", body: JSON.stringify(body) }),

  // Import workflow — "preview then confirm", for both supported sources.
  // The CSV path validates a real uploaded file before anything is written;
  // the Google Sheets path uses the same two-step shape via `confirm`.
  importPreviewLeads: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<LeadImportPreview>("/api/v1/crm/leads/import-preview/", formData);
  },
  googleSheetStatus: () => apiRequest<GoogleSheetStatus>("/api/v1/crm/leads/google-sheet-status/"),
  importGoogleSheet: (body: { spreadsheet_id: string; sheet_range?: string; confirm: boolean }) =>
    apiRequest<LeadImportPreview & LeadImportResult>("/api/v1/crm/leads/import-google-sheet/", {
      method: "POST",
      body: JSON.stringify(body)
    }),

  listCustomers: (query = "") => apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/crm/customers/${query}`),
  createCustomer: (body: Record<string, unknown>) =>
    apiRequest("/api/v1/crm/customers/", { method: "POST", body: JSON.stringify(body) }),
  updateCustomer: (id: number | string, body: Record<string, unknown>) =>
    apiRequest(`/api/v1/crm/customers/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteCustomer: (id: number | string) => apiRequest(`/api/v1/crm/customers/${id}/`, { method: "DELETE" })
};

export const organization = {
  listOrganizations: (query = "") =>
    apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/organization/organizations/${query}`)
};

// ---- Staff profile (Employee Profile / Manager Profile) ----------------
//
// ONE endpoint serves both: the payload is role-aware server-side, adding
// `managed_employees`/`scope_lead_stats` when the profile belongs to a
// Manager. Scoping is also server-side — Super Admin may read anyone,
// a Manager themselves plus their own team, an Employee only themselves;
// anything out of reach is a 404, never a 403.
export type StaffProfile = {
  profile: {
    id: number;
    email: string;
    username: string;
    first_name: string;
    last_name: string;
    full_name: string;
    phone: string;
    // `department` was removed from the User model — a free-text label
    // nothing in the app read. The reporting line that DOES matter (and
    // that RBAC scoping is derived from) is `manager`, resolved from the
    // apps.organization Team/Membership hierarchy.
    manager: { id: number; full_name: string; email: string } | null;
    role: BackendRole;
    date_joined: string;
    is_active: boolean;
  };
  lead_performance: {
    total_assigned: number;
    assigned_this_month: number;
    converted: number;
    conversion_rate: number;
    by_status: Record<string, number>;
  };
  converted_customers: Array<{
    customer_id: number;
    customer_name: string;
    lead_id: number;
    converted_at: string;
    payment_status: string;
  }>;
  interaction_history: Array<{
    id: number;
    channel: string;
    summary: string;
    occurred_at: string;
    related_type: string | null;
    related_id: number | null;
  }>;
  work_activity: {
    task_counts: { total: number; open: number; completed: number; overdue: number };
    upcoming_events: Array<{ id: number; title: string; start_at: string; location: string }>;
    attendance_today: DailyAttendance | null;
  };
  managed_employees: Array<{ id: number; full_name: string; email: string; role: BackendRole; is_active: boolean }>;
  scope_lead_stats: {
    assigned_to_manager: number;
    assigned_to_team: number;
    converted_in_scope: number;
    scope_conversion_rate: number;
  } | null;
};

// The security-settings verification step. GET first to learn WHICH
// verification input to collect (today always `current_password`, but the
// backend is designed to swap in another method later — so the UI reads
// this response rather than hardcoding the field).
export type SecuritySettingsInfo = { method: string; required_fields: string[] };

export const accounts = {
  listUsers: (query = "") => apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/auth/users/${query}`),
  createUser: (body: Record<string, unknown>) =>
    apiRequest("/api/v1/auth/users/", { method: "POST", body: JSON.stringify(body) }),
  updateUser: (id: number | string, body: Record<string, unknown>) =>
    apiRequest(`/api/v1/auth/users/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),

  activateUser: (id: number | string) =>
    apiRequest<Record<string, unknown>>(`/api/v1/auth/users/${id}/activate/`, { method: "POST" }),
  deactivateUser: (id: number | string) =>
    apiRequest<Record<string, unknown>>(`/api/v1/auth/users/${id}/deactivate/`, { method: "POST" }),
  // Deliberately NOT destructive server-side: this returns 200 with the
  // (now deactivated) user rather than 204, and no row is ever removed.
  // Every confirmation dialog around it must say so honestly.
  deleteUser: (id: number | string) =>
    apiRequest<{ detail: string; user: Record<string, unknown> }>(`/api/v1/auth/users/${id}/`, { method: "DELETE" }),

  getStaffProfile: (id: number | string) => apiRequest<StaffProfile>(`/api/v1/auth/users/${id}/profile/`),

  getSecuritySettings: () => apiRequest<SecuritySettingsInfo>("/api/v1/auth/settings/security/"),
  updateSecuritySettings: (body: Record<string, unknown>) =>
    apiRequest<{ updated_fields: string[]; user: Record<string, unknown> }>("/api/v1/auth/settings/security/", {
      method: "POST",
      body: JSON.stringify(body)
    })
};

// Real CRM events for the "Recent Activities" panel — already role-scoped
// server-side (Super Admin org-wide, Manager their team, Employee their
// own), so there is nothing for this client to filter.
export type RecentActivityEntry = {
  kind: string;
  timestamp: string;
  title: string;
  description: string;
  entity_type: string | null;
  entity_id: number | null;
  actor_id: number | null;
  actor_name: string;
};

export const activities = {
  listRecentActivity: (params: { limit?: number; days?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.limit != null) query.set("limit", String(Math.min(Math.max(params.limit, 1), 100)));
    if (params.days != null) query.set("days", String(Math.min(Math.max(params.days, 1), 90)));
    const qs = query.toString();
    return apiRequest<RecentActivityEntry[]>(`/api/v1/activities/recent/${qs ? `?${qs}` : ""}`);
  },
  listTasks: (query = "") => apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/activities/tasks/${query}`),
  createTask: (body: Record<string, unknown>) =>
    apiRequest("/api/v1/activities/tasks/", { method: "POST", body: JSON.stringify(body) }),
  updateTask: (id: number | string, body: Record<string, unknown>) =>
    apiRequest(`/api/v1/activities/tasks/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTask: (id: number | string) => apiRequest(`/api/v1/activities/tasks/${id}/`, { method: "DELETE" })
};

export const communications = {
  // queueEmail's body is entity-addressed: pass { customer } | { lead } |
  // { contact } (plus subject/body or template) and the backend resolves
  // the real address itself — it never returns it. A raw `to_email` is
  // accepted only for self-addressed mail (your own signed-in address).
  listEmailMessages: (query = "") =>
    apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/communications/email-messages/${query}`),
  queueEmail: (body: Record<string, unknown>) =>
    apiRequest("/api/v1/communications/email-messages/", { method: "POST", body: JSON.stringify(body) }),
  sendEmail: (id: number | string) =>
    apiRequest(`/api/v1/communications/email-messages/${id}/send/`, { method: "POST" }),
  deleteEmailMessage: (id: number | string) =>
    apiRequest(`/api/v1/communications/email-messages/${id}/`, { method: "DELETE" }),

  // Read-only communication-history endpoints. These are the SAME
  // endpoints every role already uses — the backend scopes each one to
  // the authenticated user (apps.crm.services.scope_queryset_for_user)
  // and masks contact detail below Manager level
  // (apps.core.serializers.PiiMaskedSerializerMixin), so a Super Admin
  // reading them gets the full audit trail and an Employee reading the
  // same URL gets only their own rows with the PII stripped. Nothing here
  // grants access; the server decides. `query` is a pre-built,
  // URL-encoded query string (e.g. "?channel=CALL&owner=3").
  listCalls: (query = "") => apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/communications/calls/${query}`),

  // Write action for the Calling channel. ENTITY-addressed exactly like
  // queueEmail above: the body names { customer } | { lead } | { contact }
  // (or content_type+object_id) and the backend resolves the real phone
  // number itself (apps.communications.serializers.InitiateCallSerializer
  // deliberately refuses a raw to_number). Returns the created row — a
  // provider failure comes back as a 201 with status=FAILED on the row,
  // not as an HTTP error.
  initiateCall: (body: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/v1/communications/calls/", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  listCommunicationLogs: (query = "") =>
    apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/communications/communication-logs/${query}`),

  // Notifications. GET (list/retrieve) and mark-read/mark-unread are open
  // to every role; every WRITE (create/update/delete) is Super-Admin-only
  // and 403s for a Manager or Employee — so the UI must not offer a
  // create/edit control to those roles, since it could only ever fail.
  listNotifications: (query = "") =>
    apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/communications/notifications/${query}`),
  createNotification: (body: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>("/api/v1/communications/notifications/", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  updateNotification: (id: number | string, body: Record<string, unknown>) =>
    apiRequest<Record<string, unknown>>(`/api/v1/communications/notifications/${id}/`, {
      method: "PATCH",
      body: JSON.stringify(body)
    }),
  deleteNotification: (id: number | string) =>
    apiRequest(`/api/v1/communications/notifications/${id}/`, { method: "DELETE" }),
  markNotificationRead: (id: number | string) =>
    apiRequest<Record<string, unknown>>(`/api/v1/communications/notifications/${id}/mark-read/`, { method: "POST" }),
  markNotificationUnread: (id: number | string) =>
    apiRequest<Record<string, unknown>>(`/api/v1/communications/notifications/${id}/mark-unread/`, { method: "POST" })
};

export const sales = {
  listInvoices: (query = "") => apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/sales/invoices/${query}`),
  getInvoice: (id: number | string) => apiRequest<Record<string, unknown>>(`/api/v1/sales/invoices/${id}/`),
  createInvoice: (body: Record<string, unknown>) =>
    apiRequest("/api/v1/sales/invoices/", { method: "POST", body: JSON.stringify(body) }),
  markInvoicePaid: (id: number | string) => apiRequest(`/api/v1/sales/invoices/${id}/mark-paid/`, { method: "POST" }),
  cancelInvoice: (id: number | string) => apiRequest(`/api/v1/sales/invoices/${id}/cancel/`, { method: "POST" }),
  deleteInvoice: (id: number | string) => apiRequest(`/api/v1/sales/invoices/${id}/`, { method: "DELETE" }),
  addInvoiceItem: (body: Record<string, unknown>) =>
    apiRequest("/api/v1/sales/invoice-items/", { method: "POST", body: JSON.stringify(body) }),
  recordPayment: (invoiceId: number | string, amount: string | number) =>
    apiRequest("/api/v1/sales/payments/", { method: "POST", body: JSON.stringify({ invoice: invoiceId, amount }) })
};

export const reports = {
  listSavedReports: (query = "") =>
    apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/reports/saved-reports/${query}`),
  createSavedReport: (body: Record<string, unknown>) =>
    apiRequest("/api/v1/reports/saved-reports/", { method: "POST", body: JSON.stringify(body) }),
  updateSavedReport: (id: number | string, body: Record<string, unknown>) =>
    apiRequest(`/api/v1/reports/saved-reports/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteSavedReport: (id: number | string) =>
    apiRequest(`/api/v1/reports/saved-reports/${id}/`, { method: "DELETE" }),
  executeSavedReport: (id: number | string) =>
    apiRequest<Record<string, unknown>>(`/api/v1/reports/saved-reports/${id}/execute/`, { method: "POST" }),
  // Spec 6: server-computed "This Month" + "All Time" company-wide figures
  // for the Super Admin Reports/Dashboard — see
  // apps.reports.services.compute_company_dashboard_summary(). Super Admin
  // only; a Manager/Employee calling this gets a 403.
  companySummary: () => apiRequest<CompanyDashboardSummary>(`/api/v1/reports/dashboards/company-summary/`)
};

export type CompanyDashboardPeriodStats = {
  total_leads: number;
  total_converted_leads: number;
  total_revenue: string | number;
  pending_payments: string | number;
  active_employees: number;
  conversion_rate: number;
};

export type CompanyDashboardSummary = {
  this_month: CompanyDashboardPeriodStats;
  all_time: CompanyDashboardPeriodStats;
};

export type AttendanceSession = {
  id: number;
  employee: number;
  login_at: string;
  logout_at: string | null;
  state: "WORKING" | "ON_BREAK" | "OFFLINE";
  last_heartbeat_at: string;
};

export type AttendanceTotals = {
  session_seconds: number;
  active_working_seconds: number;
  break_seconds: number;
  idle_seconds: number;
  break_count: number;
};

export type AttendanceEarnings = {
  regular_minutes: number;
  overtime_minutes: number;
  regular_earnings: number;
  overtime_earnings: number;
  total_earnings: number;
  currency: string;
};

export type ShiftConfig = {
  id: number;
  shift_duration_minutes: number;
  shift_start_time: string | null;
  shift_end_time: string | null;
  allowed_break_minutes: number;
  idle_timeout_minutes: number;
  overtime_threshold_minutes: number;
  is_salary_enabled: boolean;
  hourly_rate: string;
  overtime_multiplier: string;
  currency: string;
};

export type CurrentAttendance = {
  session: AttendanceSession | null;
  display_state: "WORKING" | "ON_BREAK" | "IDLE" | "OFFLINE";
  totals: AttendanceTotals;
  shift: ShiftConfig;
  earnings: AttendanceEarnings;
};

// One clock event through the day, for the Time Logs list. The backend
// derives these from the same session/heartbeat ledger the tracker already
// writes — nothing new is recorded to produce them.
export type AttendanceTimeLog = {
  at: string;
  type: "CHECK_IN" | "WORK_START" | "BREAK_START" | "BREAK_END" | "IDLE_START" | "IDLE_END" | "WORK_END" | "CHECK_OUT";
};

// Every field below the divider was ADDED by the staff-management pass —
// nothing was renamed or removed, so `login_time`/`logout_time`/
// `session_seconds`/`active_working_seconds` remain valid for existing
// call sites while the Check In/Check Out presentation reads the new ones.
export type DailyAttendance = {
  employee_id: number;
  employee_name: string;
  employee_role?: BackendRole | null;
  date: string;
  login_time: string | null;
  logout_time: string | null;
  check_in_time?: string | null;
  check_out_time?: string | null;
  gross_seconds?: number;
  effective_seconds?: number;
  shift_start_time?: string | null;
  shift_end_time?: string | null;
  time_logs?: AttendanceTimeLog[];
  session_seconds: number;
  active_working_seconds: number;
  break_seconds: number;
  idle_seconds: number;
  number_of_breaks: number;
  number_of_sessions: number;
  status: string;
  shift_minutes: number;
  overtime_minutes: number;
  short_minutes: number;
  earnings: AttendanceEarnings;
  is_open: boolean;
};

export const attendance = {
  start: () => apiRequest<CurrentAttendance>("/api/v1/attendance/sessions/start/", { method: "POST" }),
  heartbeat: () => apiRequest<CurrentAttendance>("/api/v1/attendance/sessions/heartbeat/", { method: "POST" }),
  breakStart: () => apiRequest<CurrentAttendance>("/api/v1/attendance/sessions/break-start/", { method: "POST" }),
  breakEnd: () => apiRequest<CurrentAttendance>("/api/v1/attendance/sessions/break-end/", { method: "POST" }),
  end: () => apiRequest<CurrentAttendance>("/api/v1/attendance/sessions/end/", { method: "POST" }),
  current: () => apiRequest<CurrentAttendance>("/api/v1/attendance/sessions/current/"),
  dailySummary: (params: { employeeId?: number | string; date?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.employeeId != null) query.set("employee_id", String(params.employeeId));
    if (params.date) query.set("date", params.date);
    const qs = query.toString();
    return apiRequest<DailyAttendance>(`/api/v1/attendance/sessions/daily-summary/${qs ? `?${qs}` : ""}`);
  },
  teamStatus: (date?: string) =>
    apiRequest<DailyAttendance[]>(`/api/v1/attendance/sessions/team-status/${date ? `?date=${date}` : ""}`),
  companyReport: (dateFrom?: string, dateTo?: string) => {
    const query = new URLSearchParams();
    if (dateFrom) query.set("date_from", dateFrom);
    if (dateTo) query.set("date_to", dateTo);
    const qs = query.toString();
    return apiRequest<DailyAttendance[]>(`/api/v1/attendance/sessions/company-report/${qs ? `?${qs}` : ""}`);
  },
  getShiftConfig: () => apiRequest<ShiftConfig>("/api/v1/attendance/shift-config/current/"),
  updateShiftConfig: (id: number | string, body: Record<string, unknown>) =>
    apiRequest<ShiftConfig>(`/api/v1/attendance/shift-config/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  createShiftConfig: (body: Record<string, unknown>) =>
    apiRequest<ShiftConfig>("/api/v1/attendance/shift-config/", { method: "POST", body: JSON.stringify(body) })
};

export const system = {
  listAuditLogs: (query = "") => apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/system/audit-logs/${query}`),

  listSettings: (query = "") => apiRequest<Paginated<Record<string, unknown>>>(`/api/v1/system/settings/${query}`),
  // No `createSetting`: the "Add Setting" UI action was removed (settings
  // are provisioned by the backend, not authored ad-hoc), so this client
  // deliberately exposes only read/update/delete for them.
  updateSetting: (id: number | string, body: Record<string, unknown>) =>
    apiRequest(`/api/v1/system/settings/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteSetting: (id: number | string) => apiRequest(`/api/v1/system/settings/${id}/`, { method: "DELETE" })
};
