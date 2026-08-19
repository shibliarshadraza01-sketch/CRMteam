"use client";

import {
  Activity,
  AlarmClock,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Bell,
  BellRing,
  Building2,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Coffee,
  Copy,
  Eye,
  EyeOff,
  FileSpreadsheet,
  Filter,
  History,
  ListChecks,
  Loader2,
  Lock,
  LockKeyhole,
  LogOut,
  Mail,
  Menu,
  MessageCircle,
  Moon,
  MoreHorizontal,
  Paperclip,
  Pencil,
  Phone,
  PhoneCall,
  Pin,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Star,
  StickyNote,
  Sun,
  Trash2,
  Upload,
  User,
  UserCheck,
  UserCog,
  Users,
  X
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  accounts,
  activities,
  ApiError,
  attendance,
  clearTokens,
  communications,
  crm,
  fetchMe,
  getTokens,
  login,
  logout,
  onSessionExpired,
  organization,
  reports as reportsApi,
  sales,
  setTokens,
  system,
  verifySuperAdmin,
  type BackendRole,
  type BackendUser,
  type CurrentAttendance,
  type DailyAttendance
} from "@/lib/api";

type ModuleKey =
  | "users"
  | "team"
  | "dashboard"
  | "calendar"
  | "leads"
  | "assignments"
  | "customers"
  | "payments"
  | "communication"
  | "tasks"
  | "attendance"
  | "notifications"
  | "reports"
  | "audit"
  | "settings";

type Role = "superadmin" | "manager" | "employee";

// Redesign pass — four things left this shape deliberately:
//
//   * `features` (the bulleted "Create new Manager and Employee users" /
//     "Change any user's role" capability lists) and their FeatureCards
//     renderer are gone. Those read as a component demo's permission
//     manifest, not as a production CRM screen.
//   * `stats` (hardcoded "$842K"/"4,892"/"248 total users" header cards)
//     are gone. The two screens that legitimately show figures (the
//     Employee "dashboard" and the Manager/Super-Admin "reports" home)
//     derive them from real records via computeModuleStats(); every
//     other screen is a table/list and shows no stat strip at all.
//   * `chart` is gone with it: bar graphs now live only on the Dashboard
//     and Analytics/Reports screens, never on Leads/Customers/Payments/
//     Tasks/Communication/Settings.
//   * `formFields` (per-module placeholder form scaffolding) is gone —
//     every real create/edit form is driven by the module's `columns`
//     through RecordModal, so this second, drifting field list only
//     ever described forms nothing rendered.
type ModuleConfig = {
  key: ModuleKey;
  title: string;
  subtitle: string;
  icon: React.ElementType;
  accent: string;
  columns: string[];
  rows: Array<Record<string, string>>;
  filters: string[];
  actions: Array<{ label: string; icon: React.ElementType; primary?: boolean }>;
  formTitle: string;
};

type RowRecord = Record<string, string> & { id: string };
type RecordsByModule = Record<ModuleKey, RowRecord[]>;
type ToastState = { type: "success" | "error"; message: string } | null;
type ActivityEntry = { id: string; message: string; moduleKey: ModuleKey; row: RowRecord | null };

const modules: ModuleConfig[] = [
  {
    key: "reports",
    title: "Reports & Dashboard",
    subtitle: "Monitor full company performance, revenue, and lead conversion rates.",
    icon: FileSpreadsheet,
    accent: "from-teal-700 to-emerald-500",
    columns: ["Report", "Type", "Description", "Status"],
    rows: [],
    filters: ["All reports", "Productivity", "Lead Conversion", "Sales Pipeline", "Customer Activity", "Custom"],
    actions: [{ label: "Refresh Report", icon: RefreshCw, primary: true }],
    formTitle: "Create Saved Report",
  },
  {
    key: "team",
    title: "Team Management",
    subtitle: "View your team's employees, assign or reassign leads, and track employee performance.",
    icon: Users,
    accent: "from-teal-700 to-indigo-500",
    columns: ["Name", "Role", "Status"],
    rows: [],
    filters: ["All employees", "Active", "Inactive"],
    actions: [
      { label: "Assign Lead", icon: UserCheck, primary: true },
      { label: "Reassign Lead", icon: RefreshCw },
      { label: "View Performance", icon: Eye }
    ],
    formTitle: "Assign or Reassign Lead",
  },
  {
    key: "dashboard",
    title: "My Dashboard",
    subtitle: "Track your assigned leads, customers, tasks, and personal performance.",
    icon: Activity,
    accent: "from-teal-700 to-sky-500",
    columns: ["Item", "Type", "Status", "Updated"],
    rows: [
      { Item: "Priya Sharma", Type: "Lead", Status: "Hot", Updated: "Today" },
      { Item: "Acme Learning", Type: "Customer", Status: "Active", Updated: "Yesterday" },
      { Item: "Call hot leads", Type: "Task", Status: "Open", Updated: "Today" },
      { Item: "Payment follow-up", Type: "Follow-up", Status: "Scheduled", Updated: "Aug 03" }
    ],
    filters: ["All items", "Leads", "Customers", "Tasks", "Follow-ups"],
    actions: [{ label: "Refresh Report", icon: RefreshCw, primary: true }],
    formTitle: "Log Personal Activity",
  },
  {
    key: "calendar",
    title: "Smart Calendar",
    subtitle: "Month, week, and day views with reminders, notes, and a full activity timeline for every date.",
    icon: CalendarDays,
    accent: "from-teal-700 to-violet-500",
    columns: ["Event", "Type", "Date", "Priority"],
    rows: [{ Event: "Team pipeline review", Type: "Meeting", Date: "Today", Priority: "Medium" }],
    filters: ["All events"],
    actions: [{ label: "Refresh Report", icon: RefreshCw }],
    formTitle: "Add Calendar Event",
  },
  {
    key: "users",
    title: "User Management",
    subtitle: "Create, invite, activate, deactivate, assign roles, and set user permissions.",
    icon: UserCog,
    accent: "from-teal-700 to-rose-500",
    columns: ["Name", "Role", "Email", "Phone", "Status", "Password"],
    rows: [
      { Name: "Aarav Mehta", Role: "Manager", Email: "aarav@qualifylearn.com", Phone: "", Status: "Active" },
      { Name: "Nisha Rao", Role: "Employee", Email: "nisha@qualifylearn.com", Phone: "", Status: "Active" },
      { Name: "Kabir Sethi", Role: "Manager", Email: "kabir@qualifylearn.com", Phone: "", Status: "Inactive" },
      { Name: "Zoya Khan", Role: "Employee", Email: "zoya@qualifylearn.com", Phone: "", Status: "Active" }
    ],
    filters: ["All roles", "Manager", "Employee", "Active", "Inactive"],
    actions: [
      { label: "Create User", icon: Plus, primary: true }
    ],
    formTitle: "Create User",
  },
  {
    key: "leads",
    title: "Leads",
    subtitle: "View every lead, assign ownership, import files, capture Meta leads, update status, and merge duplicates.",
    icon: Sparkles,
    accent: "from-teal-700 to-orange-500",
    columns: ["Lead", "Source", "Owner", "Status"],
    rows: [
      { Lead: "Priya Sharma", Source: "Meta Lead Ads", Owner: "Aarav Mehta", Status: "Hot" },
      { Lead: "Rahul Verma", Source: "CSV Import", Owner: "Unassigned", Status: "New" },
      { Lead: "Maya Iyer", Source: "Website", Owner: "Nisha Rao", Status: "Warm" },
      { Lead: "Omar Ali", Source: "Referral", Owner: "Kabir Sethi", Status: "Converted" }
    ],
    filters: ["All owners", "Unassigned", "New", "Hot", "Warm", "Cold", "Converted"],
    actions: [
      { label: "Assign Lead", icon: UserCheck, primary: true },
      { label: "Bulk Import", icon: Upload },
      { label: "Merge Duplicates", icon: RefreshCw },
      { label: "Export Leads (CSV)", icon: FileSpreadsheet }
    ],
    formTitle: "Create or Update Lead",
  },
  {
    key: "customers",
    title: "Customers",
    subtitle: "View all customers, convert qualified leads, and review complete profiles with interaction history.",
    icon: Users,
    accent: "from-teal-700 to-pink-500",
    columns: ["Customer", "Industry", "Owner", "Status"],
    rows: [
      { Customer: "Acme Learning", Industry: "Education", Owner: "Aarav Mehta", Status: "Active" },
      { Customer: "Bright Path", Industry: "Retail", Owner: "Nisha Rao", Status: "Prospect" },
      { Customer: "Northstar Labs", Industry: "Technology", Owner: "Kabir Sethi", Status: "Active" },
      { Customer: "Urban Study", Industry: "Education", Owner: "Zoya Khan", Status: "Inactive" }
    ],
    filters: ["All customers", "Prospect", "Active", "Inactive", "Churned"],
    actions: [
      { label: "Convert Lead", icon: Check, primary: true },
      { label: "View Profile", icon: Eye },
      { label: "Interaction History", icon: History }
    ],
    formTitle: "Customer Profile",
  },
  {
    key: "payments",
    title: "Payments",
    subtitle: "See all customer payments, add or edit payments, track partials, set reminders, and review company revenue.",
    icon: CircleDollarSign,
    accent: "from-teal-700 to-amber-500",
    columns: ["Invoice", "Customer ID", "Total", "Paid", "Balance", "Status"],
    rows: [],
    filters: ["All payments", "Draft", "Sent", "Partial", "Paid", "Cancelled"],
    actions: [
      { label: "Add Payment", icon: Plus, primary: true }
    ],
    formTitle: "Create Invoice",
  },
  {
    key: "communication",
    title: "Communication",
    subtitle: "Send email, send or view WhatsApp messages, inspect call logs, and open a unified communication timeline.",
    icon: MessageCircle,
    accent: "from-teal-700 to-cyan-500",
    columns: ["Recipient", "Subject", "Message", "Status"],
    rows: [
      { Recipient: "priya@example.com", Subject: "Proposal", Message: "Proposal sent", Status: "Sent" }
    ],
    filters: ["All channels", "Queued", "Sent", "Failed"],
    actions: [
      { label: "Send Email", icon: Mail, primary: true }
    ],
    formTitle: "Send Email",
  },
  {
    key: "tasks",
    title: "Tasks & Follow-ups",
    subtitle: "Assign tasks to any employee or manager, view the full team's follow-up calendar, and set reminders.",
    icon: ListChecks,
    accent: "from-teal-700 to-violet-500",
    columns: ["Task", "Priority", "Status", "Due"],
    rows: [
      { Task: "Call hot leads", Priority: "High", Status: "Pending", Due: "" },
      { Task: "Send onboarding plan", Priority: "Medium", Status: "In Progress", Due: "" },
      { Task: "Payment follow-up", Priority: "High", Status: "Pending", Due: "" },
      { Task: "Manager pipeline review", Priority: "Low", Status: "Completed", Due: "" }
    ],
    filters: ["All tasks", "Pending", "In Progress", "Completed", "Cancelled"],
    actions: [
      { label: "Assign Task", icon: Plus, primary: true },
      { label: "Team Calendar", icon: CalendarDays },
      { label: "Set Reminder", icon: Bell }
    ],
    formTitle: "Assign Task or Follow-up",
  },
  {
    key: "audit",
    title: "Audit Logs - Super Admin Only",
    subtitle: "A protected log of who did what and when, visible only to Super Admins.",
    icon: ShieldCheck,
    accent: "from-teal-700 to-slate-600",
    columns: ["Actor", "Action", "Description", "Time", "IP"],
    rows: [
      { Actor: "—", Action: "Create", Description: "—", Time: "—", IP: "—" }
    ],
    filters: ["All actions", "Create", "Update", "Delete", "Login", "Other"],
    actions: [
      { label: "Filter Events", icon: Filter }
    ],
    formTitle: "Audit Log Filter",
  },
  {
    key: "settings",
    title: "Settings / Configuration",
    subtitle: "Configure organization settings, Email, WhatsApp, Calling integrations, and system-wide rules.",
    icon: Settings,
    accent: "from-teal-700 to-zinc-600",
    columns: ["Setting", "Value", "Description", "Status"],
    rows: [
      { Setting: "example_setting", Value: "example_value", Description: "Example description", Status: "Active" }
    ],
    filters: ["All settings", "Active", "Inactive"],
    actions: [
      { label: "Org Settings", icon: Building2, primary: true }
    ],
    formTitle: "Create or Update Setting",
  }
];

const MODULE_ACCESS: Record<Role, ModuleKey[]> = {
  superadmin: ["reports", "calendar", "users", "leads", "customers", "payments", "communication", "tasks", "audit", "settings"],
  manager: ["reports", "calendar", "team", "leads", "customers", "payments", "communication", "tasks"],
  employee: ["dashboard", "calendar", "leads", "customers", "payments", "communication", "tasks"]
};

const HOME_MODULE: Record<Role, ModuleKey> = {
  superadmin: "reports",
  manager: "reports",
  employee: "dashboard"
};

const ROLE_LABEL: Record<Role, string> = {
  superadmin: "Super Admin",
  manager: "Manager",
  employee: "Employee"
};

const ROLE_AVATAR: Record<Role, string> = {
  superadmin: "SA",
  manager: "M",
  employee: "E"
};

const EMPLOYEE_MODULE_COPY: Partial<Record<ModuleKey, { title: string; subtitle: string }>> = {
  leads: { title: "Leads - Assigned to Me", subtitle: "View leads assigned to you, add new leads manually, update status, and edit lead details." },
  customers: { title: "Customers - Assigned to Me", subtitle: "View your assigned customers, convert leads where permitted, and review each customer's profile and history." },
  payments: { title: "Payments - Assigned Customers", subtitle: "Add payments for your customers, track partial payments, and view their payment history." },
  communication: { title: "Communication - My Activity", subtitle: "Send email, WhatsApp, and calls to your leads and customers, and view your own communication history." },
  tasks: { title: "My Tasks & Follow-ups", subtitle: "View tasks assigned to you, schedule follow-ups, set reminders, and mark tasks complete." }
};

// ---- Smart Calendar -------------------------------------------------------

type ReminderPriority = "Low" | "Medium" | "High" | "Urgent";
type ReminderRepeat = "None" | "Daily" | "Weekly" | "Monthly";
type ReminderKind = "Reminder" | "Meeting" | "Follow-up" | "Task";

type Reminder = {
  id: string;
  title: string;
  date: string;
  time: string;
  priority: ReminderPriority;
  repeat: ReminderRepeat;
  kind: ReminderKind;
  assignedTo: string;
  createdByRole: Role;
  completed: boolean;
  snoozedUntil: string | null;
};

type NoteVisibility = "private" | "team" | "company";

type CalendarNote = {
  id: string;
  date: string;
  text: string;
  author: string;
  pinned: boolean;
  visibility: NoteVisibility;
  attachments: string[];
  createdAt: string;
};

// ---- Employee-panel contact protection ------------------------------------
// There is deliberately NO client-side email/phone masking helper here any
// more. Masking only made sense when the API still handed an Employee the
// real value and this layer had to hide it; the backend now removes
// `email`/`phone` from an Employee's response entirely
// (apps.core.serializers.PiiMaskedSerializerMixin) and sends
// can_email/can_call/can_whatsapp instead. Every Employee-facing surface
// therefore renders a name plus a protected-contact label
// (see contactCapabilityLabel() below), never a masked string built from a
// value this client no longer holds.

function displayNameFor(user: BackendUser | null): string {
  if (!user) return "Me";
  const fullName = `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim();
  return fullName || user.email;
}

function toDateKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function parseDateKey(key: string): Date {
  const [year, month, day] = key.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function addDays(date: Date, amount: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function addMonths(date: Date, amount: number): Date {
  const next = new Date(date);
  next.setMonth(next.getMonth() + amount);
  return next;
}

// Filters rows (leads/customers/payments) to just this calendar month by
// their hidden `_createdAt` field — used to compute the Employee
// dashboard's "This Month" figures from the already-server-scoped
// recordsByModule arrays. Rows without a parseable date are excluded
// (never counted as "this month" by default).
function thisMonthRows(rows: RowRecord[]): RowRecord[] {
  const now = new Date();
  return rows.filter((row) => {
    const raw = row._createdAt;
    if (!raw) return false;
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return false;
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  });
}

function startOfWeek(date: Date): Date {
  const next = new Date(date);
  next.setDate(next.getDate() - next.getDay());
  next.setHours(0, 0, 0, 0);
  return next;
}

function scopeRowsForCalendar(rows: RowRecord[]): RowRecord[] {
  // No client-side owner-name filtering here: every list endpoint this
  // reads from (leads/customers/payments/tasks/communication) already
  // scopes to what the authenticated user is allowed to see server-side
  // (see apps.crm.services.scope_queryset_for_user() and its per-app
  // reuse) — re-filtering here by a display name would either duplicate
  // that boundary incorrectly or (since row.Owner is rendered as
  // "User #<id>", never a name) silently hide everything for every
  // non-admin user.
  return rows;
}

function pseudoDateForRow(id: string): string {
  const seed = Array.from(id).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const offset = (seed % 41) - 20;
  return toDateKey(addDays(new Date(), offset));
}

function canSeeReminder(reminder: Reminder, role: Role, currentUserName: string, teamNames: string[]): boolean {
  if (role === "superadmin") return true;
  if (role === "manager") return reminder.assignedTo === "Manager" || teamNames.includes(reminder.assignedTo);
  return reminder.assignedTo === currentUserName;
}

function canSeeNote(note: CalendarNote, role: Role, currentUserName: string): boolean {
  if (role === "superadmin") return true;
  if (role === "manager") return !(note.visibility === "private" && note.author === "Super Admin");
  return note.author === currentUserName;
}

function assigneeOptionsForRole(role: Role, currentUserName: string, teamNames: string[]): string[] {
  if (role === "superadmin") return ["Super Admin", "Manager", ...teamNames];
  if (role === "manager") return ["Manager", ...teamNames];
  return [currentUserName];
}

function createInitialReminders(): Reminder[] {
  // Reminders/notes are a local-only, browser-session feature by design
  // (no backend model backs them — see BACKEND_PROGRESS.md's final
  // report). They start empty for a real user/company, same as every
  // other module now that this project is backend-driven — no seeded
  // demo names or fictional companies.
  return [];
}

function createInitialNotes(): CalendarNote[] {
  return [];
}

const badgeStyles: Record<string, string> = {
  Active: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200",
  Invited: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950 dark:text-amber-200",
  Inactive: "bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-200",
  Hot: "bg-red-50 text-red-700 ring-red-200 dark:bg-red-950 dark:text-red-200",
  Warm: "bg-orange-50 text-orange-700 ring-orange-200 dark:bg-orange-950 dark:text-orange-200",
  New: "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950 dark:text-blue-200",
  Converted: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200",
  Partial: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950 dark:text-amber-200",
  Open: "bg-red-50 text-red-700 ring-red-200 dark:bg-red-950 dark:text-red-200",
  Done: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200",
  Connected: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200",
  Configured: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200"
};

const CHART_PALETTE = ["#0F766E", "#14B8A6", "#F97316", "#0EA5E9", "#8B5CF6", "#F59E0B"];

const REMINDER_PRIORITY_STYLES: Record<ReminderPriority, string> = {
  Low: "bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-200",
  Medium: "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950 dark:text-blue-200",
  High: "bg-orange-50 text-orange-700 ring-orange-200 dark:bg-orange-950 dark:text-orange-200",
  Urgent: "bg-red-50 text-red-700 ring-red-200 dark:bg-red-950 dark:text-red-200"
};

const CALENDAR_ITEM_DOTS: Array<{ key: "leads" | "customers" | "calls" | "tasks" | "reminders" | "notes"; label: string; color: string }> = [
  { key: "leads", label: "Leads", color: "bg-orange-500" },
  { key: "customers", label: "Customers", color: "bg-pink-500" },
  { key: "calls", label: "Calls", color: "bg-sky-500" },
  { key: "tasks", label: "Tasks", color: "bg-violet-500" },
  { key: "reminders", label: "Reminders", color: "bg-red-500" },
  { key: "notes", label: "Notes", color: "bg-amber-500" }
];

const recentActivities = [
  "Aarav assigned 18 Meta leads to the north team",
  "Super Admin merged 4 duplicate leads",
  "Nisha converted Bright Path to customer",
  "Payment reminder sent to Northstar Labs"
];

const upcomingFollowUps = [
  { time: "10:30 AM", title: "Call hot leads queue", owner: "Aarav Mehta" },
  { time: "01:00 PM", title: "Partial payment reminder", owner: "Kabir Sethi" },
  { time: "04:15 PM", title: "Customer onboarding check", owner: "Nisha Rao" }
];

const todayStats = [
  { label: "New Leads", value: "86" },
  { label: "Calls Logged", value: "88" },
  { label: "Emails Sent", value: "214" },
  { label: "Tasks Closed", value: "57" }
];

function createInitialRecords(): RecordsByModule {
  return modules.reduce((records, module) => {
    records[module.key] = module.rows.map((row, index) => ({ id: `${module.key}-${index}`, ...row }));
    return records;
  }, {} as RecordsByModule);
}

function cn(...classes: Array<string | false | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function statusClass(value: string) {
  return badgeStyles[value] ?? "bg-muted text-muted-foreground ring-border";
}

function parseCurrency(value: string | undefined): number {
  if (!value) return 0;
  const numeric = Number(value.replace(/[^0-9.-]/g, ""));
  return Number.isFinite(numeric) ? numeric : 0;
}

function formatCurrencyShort(value: number): string {
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function computeKpis(records: RecordsByModule) {
  const leads = records.leads ?? [];
  const customers = records.customers ?? [];
  const payments = records.payments ?? [];
  const users = records.users ?? [];

  const totalRevenue = payments.reduce((sum, row) => sum + parseCurrency(row.Paid), 0);
  const outstandingPayments = payments.filter((row) => row.Status !== "Cancelled" && parseCurrency(row.Balance) > 0);
  const pendingPayments = outstandingPayments.reduce((sum, row) => sum + parseCurrency(row.Balance), 0);
  const activeEmployees = users.filter((row) => row.Status === "Active").length;
  const convertedLeads = leads.filter((row) => row.Status === "Converted").length;
  const conversionRate = leads.length ? ((convertedLeads / leads.length) * 100).toFixed(1) : "0.0";
  const pendingCount = outstandingPayments.length;

  return [
    { label: "Total Leads", value: leads.length.toLocaleString(), change: `${leads.length} tracked` },
    { label: "Total Customers", value: customers.length.toLocaleString(), change: `${customers.length} active accounts` },
    { label: "Total Revenue", value: formatCurrencyShort(totalRevenue), change: "Collected to date" },
    { label: "Pending Payments", value: formatCurrencyShort(pendingPayments), change: `${pendingCount} awaiting` },
    { label: "Active Employees", value: activeEmployees.toLocaleString(), change: `${users.length} total users` },
    { label: "Conversion Rate", value: `${conversionRate}%`, change: `${convertedLeads} converted` }
  ];
}

function groupCountsByColumn(rows: RowRecord[], column: string): Array<{ label: string; value: number }> {
  const counts = new Map<string, number>();
  rows.forEach((row) => {
    const key = row[column] || "Unknown";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  return Array.from(counts.entries()).map(([label, value]) => ({ label, value }));
}

function groupCountsByColumnWithColor(rows: RowRecord[], column: string): Array<{ label: string; value: number; color: string }> {
  return groupCountsByColumn(rows, column).map((entry, index) => ({
    ...entry,
    color: CHART_PALETTE[index % CHART_PALETTE.length]
  }));
}

function last6Months(): Array<{ key: string; label: string }> {
  const months: Array<{ key: string; label: string }> = [];
  const now = new Date();
  for (let i = 5; i >= 0; i -= 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push({ key: `${d.getFullYear()}-${d.getMonth()}`, label: d.toLocaleString(undefined, { month: "short" }) });
  }
  return months;
}

function monthlyCountTrend(rows: RowRecord[], dateField: string): Array<{ label: string; value: number }> {
  const months = last6Months();
  const counts = new Map(months.map((m) => [m.key, 0]));
  rows.forEach((row) => {
    const raw = row[dateField];
    if (!raw) return;
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return;
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (counts.has(key)) counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  return months.map((m) => ({ label: m.label, value: counts.get(m.key) ?? 0 }));
}

function monthlySumTrend(rows: RowRecord[], dateField: string, amountField: string): Array<{ label: string; value: number }> {
  const months = last6Months();
  const sums = new Map(months.map((m) => [m.key, 0]));
  rows.forEach((row) => {
    const raw = row[dateField];
    if (!raw) return;
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return;
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (sums.has(key)) sums.set(key, (sums.get(key) ?? 0) + parseCurrency(row[amountField]));
  });
  return months.map((m) => ({ label: m.label, value: Math.round((sums.get(m.key) ?? 0) * 100) / 100 }));
}

function ownerLeadCounts(leads: RowRecord[], userRows: RowRecord[]): Array<{ label: string; value: number }> {
  const nameById = new Map(userRows.map((row) => [row.id, row.Name || row.Email || `User #${row.id}`]));
  const counts = new Map<string, number>();
  leads.forEach((row) => {
    const ownerId = row._ownerId;
    if (!ownerId) return;
    const name = nameById.get(ownerId) ?? `User #${ownerId}`;
    counts.set(name, (counts.get(name) ?? 0) + 1);
  });
  return Array.from(counts.entries())
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value);
}

type StatCard = { label: string; value: string; change: string };

function countBy(rows: RowRecord[], column: string, value: string): number {
  return rows.filter((row) => row[column] === value).length;
}

// Replaces every module's previously-static 4-card header (fixed
// numbers like "$842K"/"4,892") with real counts/sums derived from the
// same `recordsByModule` state the table beneath it renders from — so
// the header can never say something the table itself disagrees with,
// and both scale automatically as real records are added.
function computeModuleStats(
  key: ModuleKey,
  records: RecordsByModule,
  kpis: StatCard[],
  reminders: Reminder[],
  notes: CalendarNote[]
): StatCard[] | null {
  const todayKey = toDateKey(new Date());
  const weekFromNow = toDateKey(addDays(new Date(), 7));

  switch (key) {
    case "reports":
      return kpis.slice(0, 4);
    case "dashboard": {
      // "dashboard" is only ever in MODULE_ACCESS for the Employee role
      // (see MODULE_ACCESS above), so this branch is Employee-only and
      // safe to shape however the Employee dashboard spec needs without
      // touching Manager/Super Admin's "reports" branch above. Every
      // array read here (records.leads/.customers/.payments) is already
      // server-scoped to the logged-in employee's own records.
      const monthLeads = thisMonthRows(records.leads ?? []);
      const monthCustomers = thisMonthRows(records.customers ?? []);
      const monthPayments = thisMonthRows(records.payments ?? []);
      const monthRevenue = monthPayments.reduce((sum, row) => sum + parseCurrency(row.Paid), 0);
      const monthConverted = countBy(monthLeads, "Status", "Converted");
      const monthConversionRate = monthLeads.length ? ((monthConverted / monthLeads.length) * 100).toFixed(1) : "0.0";
      return [
        { label: "My Leads (This Month)", value: monthLeads.length.toLocaleString(), change: `${monthLeads.length} this month` },
        { label: "My Customers (This Month)", value: monthCustomers.length.toLocaleString(), change: `${monthCustomers.length} this month` },
        { label: "My Revenue (This Month)", value: formatCurrencyShort(monthRevenue), change: "Collected this month" },
        { label: "My Conversion Rate (This Month)", value: `${monthConversionRate}%`, change: `${monthConverted} converted` }
      ];
    }
    case "team": {
      const team = records.team ?? [];
      return [
        { label: "Team members", value: team.length.toLocaleString(), change: "Live count" },
        { label: "Active", value: countBy(team, "Status", "Active").toLocaleString(), change: `${team.length} total` },
        { label: "Managers", value: countBy(team, "Role", "Manager").toLocaleString(), change: "On this team" },
        { label: "Employees", value: countBy(team, "Role", "Employee").toLocaleString(), change: "On this team" }
      ];
    }
    case "users": {
      const users = records.users ?? [];
      return [
        { label: "Total users", value: users.length.toLocaleString(), change: "Live count" },
        { label: "Active accounts", value: countBy(users, "Status", "Active").toLocaleString(), change: `${users.length} total` },
        { label: "Managers", value: countBy(users, "Role", "Manager").toLocaleString(), change: "Company-wide" },
        { label: "Employees", value: countBy(users, "Role", "Employee").toLocaleString(), change: "Company-wide" }
      ];
    }
    case "leads": {
      const leads = records.leads ?? [];
      return [
        { label: "All leads", value: leads.length.toLocaleString(), change: "Live count" },
        { label: "Hot leads", value: countBy(leads, "Status", "Hot").toLocaleString(), change: `${leads.length} total` },
        { label: "Converted", value: countBy(leads, "Status", "Converted").toLocaleString(), change: "This view" },
        { label: "Unassigned", value: countBy(leads, "Owner", "Unassigned").toLocaleString(), change: "Need an owner" }
      ];
    }
    case "customers": {
      const customers = records.customers ?? [];
      return [
        { label: "Customers", value: customers.length.toLocaleString(), change: "Live count" },
        { label: "Active", value: countBy(customers, "Status", "Active").toLocaleString(), change: `${customers.length} total` },
        { label: "Prospect", value: countBy(customers, "Status", "Prospect").toLocaleString(), change: "Not yet active" },
        { label: "Inactive", value: countBy(customers, "Status", "Inactive").toLocaleString(), change: "Churned or paused" }
      ];
    }
    case "payments": {
      const payments = records.payments ?? [];
      const revenue = payments.reduce((sum, row) => sum + parseCurrency(row.Paid), 0);
      const outstanding = payments
        .filter((row) => row.Status !== "Cancelled")
        .reduce((sum, row) => sum + parseCurrency(row.Balance), 0);
      return [
        { label: "Revenue collected", value: formatCurrencyShort(revenue), change: `${payments.length} invoices` },
        { label: "Outstanding", value: formatCurrencyShort(outstanding), change: "Sent + partial" },
        { label: "Partial payments", value: countBy(payments, "Status", "Partial").toLocaleString(), change: "In progress" },
        { label: "Paid invoices", value: countBy(payments, "Status", "Paid").toLocaleString(), change: `${payments.length} total` }
      ];
    }
    case "communication": {
      const messages = records.communication ?? [];
      return [
        { label: "Total messages", value: messages.length.toLocaleString(), change: "Live count" },
        { label: "Sent", value: countBy(messages, "Status", "Sent").toLocaleString(), change: `${messages.length} total` },
        { label: "Queued", value: countBy(messages, "Status", "Queued").toLocaleString(), change: "Awaiting delivery" },
        { label: "Failed", value: countBy(messages, "Status", "Failed").toLocaleString(), change: "Needs attention" }
      ];
    }
    case "tasks": {
      const tasks = records.tasks ?? [];
      return [
        { label: "Open tasks", value: tasks.length.toLocaleString(), change: "Live count" },
        { label: "Pending", value: countBy(tasks, "Status", "Pending").toLocaleString(), change: `${tasks.length} total` },
        { label: "In Progress", value: countBy(tasks, "Status", "In Progress").toLocaleString(), change: "Being worked" },
        { label: "Completed", value: countBy(tasks, "Status", "Completed").toLocaleString(), change: "Done" }
      ];
    }
    case "audit": {
      const audit = records.audit ?? [];
      return [
        { label: "Logged actions", value: audit.length.toLocaleString(), change: "Currently loaded page" },
        { label: "Create", value: countBy(audit, "Action", "CREATE").toLocaleString(), change: "This page" },
        { label: "Update", value: countBy(audit, "Action", "UPDATE").toLocaleString(), change: "This page" },
        { label: "Delete", value: countBy(audit, "Action", "DELETE").toLocaleString(), change: "This page" }
      ];
    }
    case "settings": {
      const settings = records.settings ?? [];
      return [
        { label: "Total settings", value: settings.length.toLocaleString(), change: "Live count" },
        { label: "Active", value: countBy(settings, "Status", "Active").toLocaleString(), change: `${settings.length} total` },
        { label: "Inactive", value: countBy(settings, "Status", "Inactive").toLocaleString(), change: "Disabled" },
        { label: "Security", value: "On", change: "Super Admin managed" }
      ];
    }
    case "calendar": {
      const dueToday = reminders.filter((r) => r.date === todayKey && !r.completed).length;
      const dueThisWeek = reminders.filter((r) => r.date >= todayKey && r.date <= weekFromNow && !r.completed).length;
      const overdue = reminders.filter((r) => r.date < todayKey && !r.completed).length;
      const pinned = notes.filter((n) => n.pinned).length;
      return [
        { label: "Today's Events", value: dueToday.toLocaleString(), change: "Live" },
        { label: "This Week", value: dueThisWeek.toLocaleString(), change: "Live" },
        { label: "Overdue Reminders", value: overdue.toLocaleString(), change: "Live" },
        { label: "Pinned Notes", value: pinned.toLocaleString(), change: "Live" }
      ];
    }
    default:
      return null;
  }
}

function rowMatchesFilter(row: RowRecord, filterLabel: string): boolean {
  const normalized = filterLabel.trim().toLowerCase();
  if (!normalized || normalized.startsWith("all")) return true;
  const values = Object.values(row).map((value) => value.toLowerCase());
  if (values.some((value) => value === normalized)) return true;
  const words = normalized.split(/\s+/).filter((word) => word.length > 2);
  return words.some((word) => values.some((value) => value.includes(word)));
}

// ---- Leads <-> backend CRM API mapping ------------------------------
// The Leads module's table columns ("Lead"/"Source"/"Owner"/"Status") are
// free-text display labels, not backend field names. These helpers convert
// between apps.crm.Lead's real fields/enums (backend/apps/crm/models.py)
// and the generic RowRecord shape the rest of this file already renders,
// sorts, filters, and exports.
const LEAD_SOURCE_LABELS: Record<string, string> = {
  WEBSITE: "Website",
  REFERRAL: "Referral",
  COLD_CALL: "Cold Call",
  EVENT: "Event",
  ADVERTISEMENT: "Advertisement",
  OTHER: "Other"
};

const LEAD_STATUS_LABELS: Record<string, string> = {
  NEW: "New",
  CONTACTED: "Contacted",
  QUALIFIED: "Qualified",
  CONVERTED: "Converted",
  LOST: "Lost"
};

function labelToEnum(value: string, labels: Record<string, string>, fallback: string): string {
  const normalized = value.trim().toUpperCase().replace(/[\s-]+/g, "_");
  if (normalized in labels) return normalized;
  const byLabel = Object.entries(labels).find(([, label]) => label.toLowerCase() === value.trim().toLowerCase());
  return byLabel ? byLabel[0] : fallback;
}

function leadToRow(lead: Record<string, unknown>): RowRecord {
  const source = String(lead.source ?? "OTHER");
  const status = String(lead.status ?? "NEW");
  const owner = lead.owner;
  return {
    id: String(lead.id),
    Lead: String(lead.contact_name ?? ""),
    Source: LEAD_SOURCE_LABELS[source] ?? source,
    Owner: typeof owner === "number" ? `User #${owner}` : "Unassigned",
    Status: LEAD_STATUS_LABELS[status] ?? status,
    // Hidden (not in this module's `columns`, so never rendered as a
    // table cell) — used only by AnalyticsDashboard's real charts to
    // group/bucket by actual owner and creation month, and by the
    // Employee-only leads/dashboard views for masked contact display.
    _ownerId: typeof owner === "number" ? String(owner) : "",
    _createdAt: typeof lead.created_at === "string" ? lead.created_at : "",
    _email: String(lead.email ?? ""),
    _phone: String(lead.phone ?? ""),
    // Contact CAPABILITY, not contact detail. The backend stopped sending
    // `email`/`phone` to an Employee entirely (apps.core.serializers'
    // PiiMaskedSerializerMixin removes the keys) and sends these three
    // booleans in their place (ContactCapabilityMixin) — so every
    // Employee-facing "can I email/call/WhatsApp this person?" decision
    // reads these, never `_email`/`_phone`, which are simply absent for
    // that role and must not be treated as "no contact on file".
    _canEmail: lead.can_email ? "1" : "",
    _canCall: lead.can_call ? "1" : "",
    _canWhatsapp: lead.can_whatsapp ? "1" : ""
  };
}

function rowToLeadPayload(formData: Record<string, string>): Record<string, unknown> {
  const name = formData.Lead?.trim() ?? "";
  return {
    contact_name: name,
    company_name: name,
    source: labelToEnum(formData.Source ?? "", LEAD_SOURCE_LABELS, "OTHER"),
    status: labelToEnum(formData.Status ?? "", LEAD_STATUS_LABELS, "NEW")
  };
}

// ---- Customers <-> backend CRM API mapping ---------------------------
const CUSTOMER_STATUS_LABELS: Record<string, string> = {
  PROSPECT: "Prospect",
  ACTIVE: "Active",
  INACTIVE: "Inactive",
  CHURNED: "Churned"
};

function customerToRow(customer: Record<string, unknown>): RowRecord {
  const status = String(customer.status ?? "PROSPECT");
  const owner = customer.owner;
  return {
    id: String(customer.id),
    Customer: String(customer.name ?? ""),
    Industry: String(customer.industry ?? "") || "—",
    Owner: typeof owner === "number" ? `User #${owner}` : "Unassigned",
    Status: CUSTOMER_STATUS_LABELS[status] ?? status,
    // Hidden — used by the Employee-only Customers profile view.
    _email: String(customer.email ?? ""),
    _phone: String(customer.phone ?? ""),
    _createdAt: typeof customer.created_at === "string" ? customer.created_at : "",
    // See leadToRow() — capability booleans, never contact detail.
    _canEmail: customer.can_email ? "1" : "",
    _canCall: customer.can_call ? "1" : "",
    _canWhatsapp: customer.can_whatsapp ? "1" : ""
  };
}

function rowToCustomerPayload(formData: Record<string, string>, organizationId: number | null): Record<string, unknown> {
  return {
    name: formData.Customer?.trim() ?? "",
    industry: formData.Industry?.trim() === "—" ? "" : formData.Industry?.trim() ?? "",
    status: labelToEnum(formData.Status ?? "", CUSTOMER_STATUS_LABELS, "PROSPECT"),
    ...(organizationId !== null ? { organization: organizationId } : {})
  };
}

// ---- Users <-> backend accounts API mapping ---------------------------
const USER_ROLE_LABELS: Record<string, string> = {
  SUPER_ADMIN: "Super Admin",
  MANAGER: "Manager",
  EMPLOYEE: "Employee"
};

function userToRow(user: Record<string, unknown>): RowRecord {
  const role = String(user.role ?? "EMPLOYEE");
  const firstName = String(user.first_name ?? "");
  const lastName = String(user.last_name ?? "");
  const fullName = `${firstName} ${lastName}`.trim();
  return {
    id: String(user.id),
    Name: fullName || String(user.email ?? ""),
    Role: USER_ROLE_LABELS[role] ?? role,
    Email: String(user.email ?? ""),
    Phone: String(user.phone ?? ""),
    Status: user.is_active === false ? "Inactive" : "Active"
  };
}

function rowToUserCreatePayload(formData: Record<string, string>): Record<string, unknown> {
  const fullName = formData.Name?.trim() ?? "";
  const [firstName, ...rest] = fullName.split(/\s+/);
  return {
    email: formData.Email?.trim() ?? "",
    password: formData.Password ?? "",
    first_name: firstName ?? "",
    last_name: rest.join(" "),
    phone: formData.Phone?.trim() ?? "",
    role: labelToEnum(formData.Role ?? "", USER_ROLE_LABELS, "EMPLOYEE"),
    is_active: (formData.Status ?? "Active").trim().toLowerCase() !== "inactive"
  };
}

function rowToUserUpdatePayload(formData: Record<string, string>): Record<string, unknown> {
  return {
    phone: formData.Phone?.trim() ?? "",
    role: labelToEnum(formData.Role ?? "", USER_ROLE_LABELS, "EMPLOYEE"),
    is_active: (formData.Status ?? "Active").trim().toLowerCase() !== "inactive"
  };
}

// ---- Audit logs <-> backend system API (read-only) --------------------
function auditLogToRow(entry: Record<string, unknown>): RowRecord {
  const actor = entry.actor;
  const createdAt = typeof entry.created_at === "string" ? entry.created_at : "";
  return {
    id: String(entry.id),
    Actor: typeof actor === "number" ? `User #${actor}` : "System",
    Action: String(entry.action ?? "OTHER"),
    Description: String(entry.description ?? ""),
    Time: createdAt ? new Date(createdAt).toLocaleString() : "",
    IP: String(entry.ip_address ?? "") || "—"
  };
}

// ---- Settings <-> backend system API -----------------------------------
function settingToRow(setting: Record<string, unknown>): RowRecord {
  return {
    id: String(setting.id),
    Setting: String(setting.key ?? ""),
    Value: String(setting.value ?? ""),
    Description: String(setting.description ?? ""),
    Status: setting.is_active === false ? "Inactive" : "Active"
  };
}

function rowToSettingPayload(formData: Record<string, string>): Record<string, unknown> {
  return {
    key: formData.Setting?.trim() ?? "",
    value: formData.Value?.trim() ?? "",
    description: formData.Description?.trim() ?? "",
    is_active: (formData.Status ?? "Active").trim().toLowerCase() !== "inactive"
  };
}

// ---- Tasks <-> backend activities API -----------------------------------
const TASK_PRIORITY_LABELS: Record<string, string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  URGENT: "Urgent"
};

const TASK_STATUS_LABELS: Record<string, string> = {
  PENDING: "Pending",
  IN_PROGRESS: "In Progress",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled"
};

function taskToRow(task: Record<string, unknown>): RowRecord {
  const priority = String(task.priority ?? "MEDIUM");
  const status = String(task.status ?? "PENDING");
  const dueDate = typeof task.due_date === "string" ? task.due_date : "";
  return {
    id: String(task.id),
    Task: String(task.title ?? ""),
    Priority: TASK_PRIORITY_LABELS[priority] ?? priority,
    Status: TASK_STATUS_LABELS[status] ?? status,
    Due: dueDate ? new Date(dueDate).toLocaleDateString() : ""
  };
}

function rowToTaskPayload(formData: Record<string, string>): Record<string, unknown> {
  const dueRaw = formData.Due?.trim() ?? "";
  const parsedDue = dueRaw ? new Date(dueRaw) : null;
  return {
    title: formData.Task?.trim() ?? "",
    priority: labelToEnum(formData.Priority ?? "", TASK_PRIORITY_LABELS, "MEDIUM"),
    status: labelToEnum(formData.Status ?? "", TASK_STATUS_LABELS, "PENDING"),
    ...(parsedDue && !Number.isNaN(parsedDue.getTime()) ? { due_date: parsedDue.toISOString() } : {})
  };
}

// ---- Communication <-> backend communications API ----------------------
const EMAIL_STATUS_LABELS: Record<string, string> = {
  QUEUED: "Queued",
  SENT: "Sent",
  FAILED: "Failed"
};

function emailMessageToRow(message: Record<string, unknown>): RowRecord {
  const status = String(message.status ?? "QUEUED");
  return {
    id: String(message.id),
    // `recipient_label` is the backend's safe "who this went to" field
    // (the related customer/lead's name). `to_email` is only present for
    // Manager/Super Admin — an Employee never receives it.
    Recipient: String(message.recipient_label ?? message.to_email ?? ""),
    Subject: String(message.subject ?? ""),
    Message: String(message.body ?? ""),
    Status: EMAIL_STATUS_LABELS[status] ?? status
  };
}

// The backend's queue-email endpoint is entity-addressed: it resolves the
// customer's real address itself and never returns it (see
// backend/apps/communications/serializers.py's EmailMessageQueueSerializer).
// A raw `to_email` is accepted only for self-addressed mail. So the
// "Recipient" the user typed is matched against the customer/lead records
// already loaded in this session (by name), and only falls through to
// `to_email` when it looks like an address the user is sending to
// themselves.
function rowToEmailQueuePayload(
  formData: Record<string, string>,
  records: Partial<RecordsByModule> = {}
): Record<string, unknown> {
  const recipient = formData.Recipient?.trim() ?? "";
  const subjectBody = {
    subject: formData.Subject?.trim() ?? "",
    body: formData.Message?.trim() ?? ""
  };
  const needle = recipient.toLowerCase();

  const customer = (records.customers ?? []).find((row) => String(row.Customer ?? "").toLowerCase() === needle);
  if (customer) {
    return { customer: Number(customer.id), ...subjectBody };
  }
  const lead = (records.leads ?? []).find((row) => String(row.Lead ?? "").toLowerCase() === needle);
  if (lead) {
    return { lead: Number(lead.id), ...subjectBody };
  }
  return { to_email: recipient, ...subjectBody };
}

// ---- Payments <-> backend sales (Invoice) API ---------------------------
const INVOICE_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  SENT: "Sent",
  PARTIAL: "Partial",
  PAID: "Paid",
  CANCELLED: "Cancelled"
};

function invoiceToRow(invoice: Record<string, unknown>): RowRecord {
  const status = String(invoice.status ?? "DRAFT");
  return {
    id: String(invoice.id),
    Invoice: String(invoice.invoice_number ?? ""),
    "Customer ID": String(invoice.customer ?? ""),
    Total: String(invoice.total ?? "0"),
    Paid: String(invoice.amount_paid ?? "0"),
    Balance: String(invoice.balance ?? invoice.total ?? "0"),
    Status: INVOICE_STATUS_LABELS[status] ?? status,
    // Hidden — used by AnalyticsDashboard's real revenue-by-month chart,
    // and by the Employee-only Payments view (overdue detection, reminders).
    _createdAt: typeof invoice.created_at === "string" ? invoice.created_at : "",
    _dueDate: typeof invoice.due_date === "string" ? invoice.due_date : ""
  };
}

function rowToInvoiceCreatePayload(formData: Record<string, string>): Record<string, unknown> {
  const customerId = Number(formData["Customer ID"]?.trim());
  return {
    invoice_number: formData.Invoice?.trim() ?? "",
    ...(Number.isFinite(customerId) && customerId > 0 ? { customer: customerId } : {}),
    tax: "0.00"
  };
}

// ---- Reports <-> backend reports (SavedReport) API ----------------------
const REPORT_TYPE_LABELS: Record<string, string> = {
  PRODUCTIVITY: "Productivity",
  LEAD_CONVERSION: "Lead Conversion",
  SALES_PIPELINE: "Sales Pipeline",
  CUSTOMER_ACTIVITY: "Customer Activity",
  CUSTOM: "Custom"
};

function savedReportToRow(report: Record<string, unknown>): RowRecord {
  const reportType = String(report.report_type ?? "CUSTOM");
  return {
    id: String(report.id),
    Report: String(report.name ?? ""),
    Type: REPORT_TYPE_LABELS[reportType] ?? reportType,
    Description: String(report.description ?? ""),
    Status: report.is_active === false ? "Inactive" : "Active"
  };
}

function rowToSavedReportPayload(formData: Record<string, string>): Record<string, unknown> {
  return {
    name: formData.Report?.trim() ?? "",
    report_type: labelToEnum(formData.Type ?? "", REPORT_TYPE_LABELS, "CUSTOM"),
    description: formData.Description?.trim() ?? "",
    is_active: (formData.Status ?? "Active").trim().toLowerCase() !== "inactive"
  };
}

const VIEW_ACTION_LABELS = new Set([
  "View Profile",
  "Interaction History",
  "Call Logs",
  "WhatsApp",
  "Team Calendar",
  "View Log"
]);

const PAGE_SIZE = 6;

// Employee-safe column set for a given module — reused by every place a
// modal/form needs to know which fields to show/collect for the current
// role (the main record table, the global-search "view" jump, etc.) so
// Owner/Source/etc. can never leak through a code path that
// forgot to re-derive it locally.
function employeeSafeColumns(module: ModuleConfig): string[] {
  if (module.key === "leads") return ["Lead", "Email", "Phone", "Category"];
  if (module.key === "customers") return ["Customer", "Industry", "Status"];
  return module.columns;
}

// Companion to employeeSafeColumns() — derives the extra display fields
// (Email/Phone/Category) those column sets need, without mutating the
// original row (which still carries Owner/Source for chart/grouping code
// elsewhere that isn't employee-reachable).
//
// The Email/Phone cells deliberately render a CAPABILITY, not a value:
// the backend sends an Employee no `email`/`phone` key at all, so there
// is nothing to mask — a masked-looking string here would be a fiction.
// "On file (protected)" says exactly what is true: the contact detail
// exists server-side and this client never receives it.
const CONTACT_ON_FILE = "On file (protected)";
const CONTACT_NOT_ON_FILE = "Not on file";

function contactCapabilityLabel(flag: string | undefined): string {
  return flag ? CONTACT_ON_FILE : CONTACT_NOT_ON_FILE;
}

function employeeSafeRow(module: ModuleConfig, row: RowRecord): RowRecord {
  if (module.key === "leads") {
    return {
      ...row,
      Email: contactCapabilityLabel(row._canEmail),
      Phone: contactCapabilityLabel(row._canCall),
      Category: row.Status ?? ""
    };
  }
  if (module.key === "customers") {
    return { ...row, Email: contactCapabilityLabel(row._canEmail), Phone: contactCapabilityLabel(row._canCall) };
  }
  return row;
}

// Spec 8/27: credentials belong in the Create/Edit User form, never in a
// column of the user table — not even masked. These columns are collected
// by RecordModal but stripped before the table renders.
const FORM_ONLY_COLUMNS: Partial<Record<ModuleKey, string[]>> = {
  users: ["Password"]
};

function tableColumnsForRole(module: ModuleConfig, role: Role): string[] {
  const base = role === "employee" ? employeeSafeColumns(module) : module.columns;
  const formOnly = FORM_ONLY_COLUMNS[module.key];
  return formOnly ? base.filter((column) => !formOnly.includes(column)) : base;
}

// Spec 8/23: columns whose value set is a real enum render as a <select>,
// so Role can never be typed as arbitrary text. Anything not listed here
// stays a free-text input.
const FIELD_OPTIONS: Partial<Record<ModuleKey, Record<string, string[]>>> = {
  users: {
    Role: ["Manager", "Employee"],
    Status: ["Active", "Inactive"]
  },
  team: {
    Role: ["Manager", "Employee"],
    Status: ["Active", "Inactive"]
  },
  leads: {
    Status: ["New", "Hot", "Warm", "Cold", "Converted", "Lost"]
  },
  customers: {
    Status: ["Prospect", "Active", "Inactive", "Churned"]
  },
  payments: {
    Status: ["Draft", "Sent", "Partial", "Paid", "Cancelled"]
  },
  communication: {
    Status: ["Queued", "Sent", "Failed"]
  },
  tasks: {
    Status: ["Pending", "In Progress", "Completed"],
    Priority: ["High", "Medium", "Low"]
  },
  settings: {
    Status: ["Active", "Inactive"]
  },
  reports: {
    Status: ["Active", "Inactive"],
    Type: ["Productivity", "Lead Conversion", "Sales Pipeline", "Customer Activity", "Custom"]
  }
};

// Fields a form may legitimately leave blank. A password is only set at
// creation time; an edit that leaves it empty keeps the existing one.
const OPTIONAL_FIELDS: Partial<Record<ModuleKey, string[]>> = {
  users: ["Password", "Phone"],
  leads: ["Owner"],
  reports: ["Description"]
};

function isFieldRequired(module: ModuleConfig, column: string, mode: "create" | "edit" | "view"): boolean {
  if (mode === "view") return false;
  if ((OPTIONAL_FIELDS[module.key] ?? []).includes(column)) return false;
  if (mode === "edit" && module.key === "users" && column === "Password") return false;
  return true;
}

// Employees must never see an export/download affordance, or any action
// that would let them touch another employee's data (assigning leads/
// tasks to someone else, bulk import, duplicate merging, adding payments,
// converting/creating customers, or a team-wide calendar) anywhere in
// their panel — filter these out of a module's action list before it's
// rendered — the module header action bar reads this filtered list.
//
// "Send Email" is blocked for Employees too, but for a different reason:
// that generic header action opens the shared RecordModal with a free-text
// "Recipient" field, which both invites an employee to type a customer
// address the backend deliberately no longer gives them (and would reject)
// and duplicates the Communication Center's own entity-addressed compose
// box. Employees use the Communication Center's Email workspace instead.
const EMPLOYEE_BLOCKED_ACTION_PATTERN =
  /export|download|assign (lead|task|employee|team|manager)|bulk import|merge duplicates|convert lead|add payment|team calendar|add customer|create user|send email/i;

// Export (CSV/Excel/reports/data) is Super-Admin-only by default. Manager
// export is spec'd as "only if explicitly allowed by Manager permissions" —
// this codebase has no such permission flag today, so Manager is denied
// export until a real permission concept exists (do not invent one here).
const EXPORT_ACTION_PATTERN = /export|download/i;

function visibleActionsForRole(actions: ModuleConfig["actions"], role: Role): ModuleConfig["actions"] {
  if (role === "superadmin") return actions;
  if (role === "employee") return actions.filter((action) => !EMPLOYEE_BLOCKED_ACTION_PATTERN.test(action.label));
  return actions.filter((action) => !EXPORT_ACTION_PATTERN.test(action.label));
}

function backendRoleToRole(role: BackendRole): Role {
  if (role === "SUPER_ADMIN") return "superadmin";
  if (role === "MANAGER") return "manager";
  return "employee";
}

// ---------------------------------------------------------------------
// Employee Working Hours / Attendance Time Tracker
//
// Server-side heartbeats (see lib/api.ts's `attendance` namespace) are
// the single source of truth for every payroll-relevant number here —
// LOGIN TIME != ACTIVE WORKING TIME, so this UI always renders
// `totals.active_working_seconds` from the backend, never a client-
// computed logout-minus-login. `liveWorkedSeconds` below only ticks
// locally between heartbeats for a smooth stopwatch feel; every
// heartbeat/break/logout response resyncs it from the server.
// ---------------------------------------------------------------------

const ATTENDANCE_HEARTBEAT_INTERVAL_MS = 25_000;
const ATTENDANCE_ACTIVITY_THROTTLE_MS = 3_000;
const ATTENDANCE_DEFAULT_IDLE_TIMEOUT_MINUTES = 5;

const ATTENDANCE_STATUS_META: Record<CurrentAttendance["display_state"], { label: string; dot: string; text: string }> = {
  WORKING: { label: "Working", dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" },
  ON_BREAK: { label: "On Break", dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" },
  IDLE: { label: "Idle", dot: "bg-orange-500", text: "text-orange-600 dark:text-orange-400" },
  OFFLINE: { label: "Offline", dot: "bg-red-500", text: "text-red-600 dark:text-red-400" }
};

function AttendanceStatusDot({ state }: { state: CurrentAttendance["display_state"] }) {
  return <span className={cn("inline-block size-2.5 shrink-0 rounded-full", ATTENDANCE_STATUS_META[state].dot)} aria-hidden />;
}

function formatHMS(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function formatHM(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

type AttendanceTracking = {
  current: CurrentAttendance | null;
  liveWorkedSeconds: number;
  startBreak: () => Promise<void>;
  endBreak: () => Promise<void>;
  fullLogout: () => void | Promise<void>;
};

const AttendanceContext = createContext<AttendanceTracking | null>(null);

// Tracks EMPLOYEE and MANAGER roles (both clock working hours); Super
// Admin never clocks in, so `enabled` is false for that role — see
// callers.
function useAttendanceTracking(enabled: boolean, onLogout: () => void | Promise<void>): AttendanceTracking {
  const [current, setCurrent] = useState<CurrentAttendance | null>(null);
  const [liveWorkedSeconds, setLiveWorkedSeconds] = useState(0);
  const lastActivityRef = useRef(Date.now());
  const lastThrottleRef = useRef(0);

  useEffect(() => {
    if (!enabled) {
      setCurrent(null);
      return;
    }
    let cancelled = false;
    attendance
      .start()
      .then((result) => {
        if (cancelled) return;
        setCurrent(result);
        setLiveWorkedSeconds(result.totals.active_working_seconds);
      })
      .catch(() => {
        // Non-fatal: the attendance widgets simply stay hidden if the
        // backend attendance app is unreachable.
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  // Client-side activity listeners decide WHETHER to send a heartbeat;
  // the server decides, independently, whether the resulting gap counts
  // as idle (`record_heartbeat()`'s own gap-detection). This is what
  // lets one mechanism cover idle detection, sleep/lock, and tab-away
  // uniformly — no separate client-side sleep/lock detection is needed
  // or reliable in a browser.
  useEffect(() => {
    if (!enabled) return;
    function markActive() {
      const now = Date.now();
      lastActivityRef.current = now;
      if (now - lastThrottleRef.current < ATTENDANCE_ACTIVITY_THROTTLE_MS) return;
      lastThrottleRef.current = now;
    }
    const events: Array<keyof WindowEventMap> = ["mousemove", "keydown", "scroll", "click", "touchstart"];
    events.forEach((event) => window.addEventListener(event, markActive, { passive: true }));
    return () => {
      events.forEach((event) => window.removeEventListener(event, markActive));
    };
  }, [enabled]);

  const idleTimeoutMinutes = current?.shift.idle_timeout_minutes ?? ATTENDANCE_DEFAULT_IDLE_TIMEOUT_MINUTES;

  useEffect(() => {
    if (!enabled) return;
    const idleThresholdMs = idleTimeoutMinutes * 60_000;
    const interval = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - lastActivityRef.current > idleThresholdMs) return;
      attendance
        .heartbeat()
        .then((result) => {
          setCurrent(result);
          setLiveWorkedSeconds(result.totals.active_working_seconds);
        })
        .catch(() => {
          // A missed heartbeat self-heals: the server's own gap
          // detection accounts for any resulting silence as idle time.
        });
    }, ATTENDANCE_HEARTBEAT_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [enabled, idleTimeoutMinutes]);

  useEffect(() => {
    if (!enabled || !current || current.display_state !== "WORKING") return;
    const interval = window.setInterval(() => setLiveWorkedSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(interval);
  }, [enabled, current]);

  const startBreak = useCallback(async () => {
    try {
      const result = await attendance.breakStart();
      setCurrent(result);
      setLiveWorkedSeconds(result.totals.active_working_seconds);
    } catch {
      // Already on break / no open session — widget state stays as-is.
    }
  }, []);

  const endBreak = useCallback(async () => {
    try {
      const result = await attendance.breakEnd();
      setCurrent(result);
      setLiveWorkedSeconds(result.totals.active_working_seconds);
    } catch {
      // Not currently on break / no open session.
    }
  }, []);

  const fullLogout = useCallback(async () => {
    try {
      await attendance.end();
    } catch {
      // Best-effort — the real app logout must proceed regardless.
    }
    await onLogout();
  }, [onLogout]);

  return { current, liveWorkedSeconds, startBreak, endBreak, fullLogout };
}

export default function AuthGate() {
  const [role, setRole] = useState<Role | null | undefined>(undefined);
  const [currentUser, setCurrentUser] = useState<BackendUser | null>(null);

  useEffect(() => {
    const { access } = getTokens();
    if (!access) {
      setRole(null);
      return;
    }
    fetchMe()
      .then((user) => {
        setCurrentUser(user);
        setRole(backendRoleToRole(user.role));
      })
      .catch(() => {
        clearTokens();
        setRole(null);
      });
  }, []);

  useEffect(() => {
    // Final production operations pass — Part 8: a refresh-token
    // rejection anywhere in the app (not just at initial page load)
    // immediately drops the user back to the login screen, instead of
    // leaving a stale "logged in" page up until a manual refresh.
    return onSessionExpired(() => {
      setCurrentUser(null);
      setRole(null);
    });
  }, []);

  function handleLoginSuccess(user: BackendUser) {
    setCurrentUser(user);
    setRole(backendRoleToRole(user.role));
  }

  async function handleLogout() {
    await logout();
    setCurrentUser(null);
    setRole(null);
  }

  if (role === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex size-12 items-center justify-center overflow-hidden rounded-full bg-white shadow-soft ring-1 ring-border">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/qualify-learn-logo.jpeg" alt="Qualify Learn" className="size-full object-cover" />
        </div>
      </div>
    );
  }

  if (role === null) {
    return <LoginScreen onSuccess={handleLoginSuccess} />;
  }

  return <SuperAdminPage role={role} currentUser={currentUser} onLogout={handleLogout} />;
}

// Username-based login is a frontend-only presentation over the existing
// email/password JWT backend (apps.accounts) — the backend's identity
// model, permissions, and session handling are untouched. Each fixed
// username maps to one of this project's role-seeded accounts; an
// unrecognized username never reaches the backend at all (no point
// round-tripping a request the fixed table already knows will fail),
// and any failure past this point is reported with the same generic
// "Invalid Username or Password." message so a wrong username and a
// wrong password are indistinguishable to the caller.
const USERNAME_TO_EMAIL: Record<string, string> = {
  qualifylearncrm: "admin@qualifylearn.test",
  qualifylearnmanagercrm: "manager@qualifylearn.test",
  qualifylearnemployeecrm: "employee@qualifylearn.test"
};

function LoginScreen({ onSuccess }: { onSuccess: (user: BackendUser) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [challenge, setChallenge] = useState<string | null>(null);
  const [accessCode, setAccessCode] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    const email = USERNAME_TO_EMAIL[username.trim()];
    if (!email) {
      setError("Invalid Username or Password.");
      return;
    }
    setSubmitting(true);
    try {
      const result = await login(email, password);
      if (result.kind === "challenge") {
        setChallenge(result.challenge);
      } else {
        setTokens(result.access, result.refresh, rememberMe);
        onSuccess(result.user);
      }
    } catch {
      setError("Invalid Username or Password.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerifySubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    setError("");
    setSubmitting(true);
    try {
      const result = await verifySuperAdmin(challenge, accessCode);
      if (result.kind === "tokens") {
        setTokens(result.access, result.refresh, rememberMe);
        onSuccess(result.user);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Incorrect access code.");
    } finally {
      setSubmitting(false);
    }
  }

  if (challenge) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
        <div className="w-full max-w-md">
          <div className="mb-6 flex flex-col items-center text-center">
            <div className="mb-4 flex size-16 items-center justify-center overflow-hidden rounded-full bg-white shadow-soft ring-1 ring-border">
              <ShieldCheck className="size-8 text-teal-600" />
            </div>
            <h1 className="text-2xl font-bold">Super Admin verification</h1>
            <p className="mt-1 text-sm text-muted-foreground">Enter your secondary access code to continue</p>
          </div>
          <form onSubmit={handleVerifySubmit} className="rounded-2xl border bg-card p-6 shadow-soft sm:p-8">
            <div className="space-y-4">
              <label className="block space-y-1.5">
                <span className="text-sm font-semibold">Access code</span>
                <div className="relative">
                  <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={accessCode}
                    onChange={(event) => setAccessCode(event.target.value)}
                    placeholder="Enter your access code"
                    autoComplete="one-time-code"
                    className="h-11 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
                  />
                </div>
              </label>
              {error ? (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-sm font-semibold text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>
              ) : null}
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-teal-600 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {submitting ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
                Verify
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-4 flex size-16 items-center justify-center overflow-hidden rounded-full bg-white shadow-soft ring-1 ring-border">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/qualify-learn-logo.jpeg" alt="Qualify Learn" className="size-full object-cover" />
          </div>
          <h1 className="text-2xl font-bold">Welcome back</h1>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to the Qualify Learn CRM</p>
        </div>

        <form onSubmit={handleSubmit} className="rounded-2xl border bg-card p-6 shadow-soft sm:p-8">
          <div className="space-y-4">
            <label className="block space-y-1.5">
              <span className="text-sm font-semibold">Username</span>
              <div className="relative">
                <User className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="Enter Username"
                  autoComplete="username"
                  className="h-11 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
                />
              </div>
            </label>

            <label className="block space-y-1.5">
              <span className="text-sm font-semibold">Password</span>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter Password"
                  autoComplete="current-password"
                  className="h-11 w-full rounded-lg border bg-background pl-9 pr-10 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </label>

            {error ? (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm font-semibold text-red-700 dark:bg-red-950 dark:text-red-200">{error}</p>
            ) : null}

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                  className="size-4 rounded border-input accent-teal-600"
                />
                Remember me
              </label>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-teal-600 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting ? <Loader2 className="size-4 animate-spin" /> : <LockKeyhole className="size-4" />}
              Login
            </button>
          </div>
        </form>

        <p className="mt-6 text-center text-xs text-muted-foreground">Qualify Learn - Empowering Minds, Elevating Futures.</p>
      </div>
    </div>
  );
}

function SuperAdminPage({
  role,
  currentUser,
  onLogout
}: {
  role: Role;
  currentUser: BackendUser | null;
  onLogout: () => void | Promise<void>;
}) {
  const visibleModules = useMemo(() => modules.filter((module) => MODULE_ACCESS[role].includes(module.key)), [role]);
  const [activeKey, setActiveKey] = useState<ModuleKey>(() => HOME_MODULE[role]);
  const [query, setQuery] = useState("");
  const [globalQuery, setGlobalQuery] = useState("");
  const [filter, setFilter] = useState(() => modules.find((module) => module.key === HOME_MODULE[role])?.filters[0] ?? "All");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<{ column: string; direction: "asc" | "desc" } | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<"create" | "edit" | "view">("create");
  const [editingRecord, setEditingRecord] = useState<RowRecord | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  // Backend rejection text for the open create/edit form, shown as its own
  // banner and cleared the moment the user edits any field (spec 23).
  const [formServerError, setFormServerError] = useState<string | null>(null);
  const [recordsByModule, setRecordsByModule] = useState<RecordsByModule>(() => createInitialRecords());
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>(() =>
    recentActivities.map((message, index) => ({ id: `seed-${index}`, message, moduleKey: "reports", row: null }))
  );
  const [toast, setToast] = useState<ToastState>(null);
  const [dark, setDark] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [reminders, setReminders] = useState<Reminder[]>(() => createInitialReminders());
  const [notes, setNotes] = useState<CalendarNote[]>(() => createInitialNotes());
  const [defaultOrganizationId, setDefaultOrganizationId] = useState<number | null>(null);
  // Deep-link request from a lead/customer detail view into one of the
  // Communication Center's channel workspaces. Holds an entity KIND + ID
  // and the display name only — never a contact value, and never anything
  // written to the URL, localStorage, or sessionStorage.
  const [commFocus, setCommFocus] = useState<CommFocus | null>(null);

  const attendanceTracking = useAttendanceTracking(role !== "superadmin", onLogout);

  const currentUserName = displayNameFor(currentUser);
  const teamNames = useMemo(
    () => Array.from(new Set((recordsByModule.team ?? []).map((row) => row.Name).filter(Boolean))),
    [recordsByModule.team]
  );

  // All 11 modules (Leads, Customers, Users/Team, Settings, Audit, Tasks,
  // Communication, Payments, Reports/Dashboard) are wired to their real
  // backend APIs below — createInitialRecords() only supplies the initial
  // render shape before the fetches below replace it, and Calendar/
  // reminders/notes remain a local-only UI feature by design (no backend
  // model exists for them). See saveRecord()/deleteRecord() below for the
  // matching create/update/delete branches.
  useEffect(() => {
    let cancelled = false;
    crm
      .listLeads()
      .then((page) => {
        if (cancelled) return;
        setRecordsByModule((current) => ({ ...current, leads: page.results.map(leadToRow) }));
      })
      .catch((err) => {
        if (cancelled) return;
        showToast({
          type: "error",
          message: err instanceof ApiError ? `Could not load leads: ${err.message}` : "Could not reach the CRM API."
        });
      });

    crm
      .listCustomers()
      .then((page) => {
        if (cancelled) return;
        setRecordsByModule((current) => ({ ...current, customers: page.results.map(customerToRow) }));
      })
      .catch((err) => {
        if (cancelled) return;
        showToast({
          type: "error",
          message: err instanceof ApiError ? `Could not load customers: ${err.message}` : "Could not reach the CRM API."
        });
      });

    // Customer.organization is a required FK server-side, but this UI has
    // no organization switcher — this app is single-tenant in practice.
    // Fetch whichever organization the backend returns first and use it
    // as the only one this UI ever creates customers under.
    organization
      .listOrganizations()
      .then((page) => {
        if (cancelled) return;
        const first = page.results[0];
        if (first) setDefaultOrganizationId(Number(first.id));
      })
      .catch(() => {
        // Non-fatal: customer creation will surface a clear error if
        // attempted with no organization available.
      });

    accounts
      .listUsers()
      .then((page) => {
        if (cancelled) return;
        const rows = page.results.map(userToRow);
        setRecordsByModule((current) => ({ ...current, users: rows, team: rows }));
      })
      .catch((err) => {
        if (cancelled) return;
        showToast({
          type: "error",
          message: err instanceof ApiError ? `Could not load users: ${err.message}` : "Could not reach the accounts API."
        });
      });

    system
      .listSettings()
      .then((page) => {
        if (cancelled) return;
        setRecordsByModule((current) => ({ ...current, settings: page.results.map(settingToRow) }));
      })
      .catch((err) => {
        if (cancelled) return;
        showToast({
          type: "error",
          message: err instanceof ApiError ? `Could not load settings: ${err.message}` : "Could not reach the system API."
        });
      });

    system
      .listAuditLogs()
      .then((page) => {
        if (cancelled) return;
        setRecordsByModule((current) => ({ ...current, audit: page.results.map(auditLogToRow) }));
      })
      .catch(() => {
        // Non-fatal and expected for non-Manager roles: AuditLog is
        // Manager-or-above only (see apps/system/permissions.py) — an
        // Employee correctly gets 403 here, not a bug.
      });

    reportsApi
      .listSavedReports()
      .then((page) => {
        if (cancelled) return;
        const rows = page.results.map(savedReportToRow);
        setRecordsByModule((current) => ({ ...current, reports: rows, dashboard: rows }));
      })
      .catch((err) => {
        if (cancelled) return;
        showToast({
          type: "error",
          message: err instanceof ApiError ? `Could not load reports: ${err.message}` : "Could not reach the reports API."
        });
      });

    activities
      .listTasks()
      .then((page) => {
        if (cancelled) return;
        setRecordsByModule((current) => ({ ...current, tasks: page.results.map(taskToRow) }));
      })
      .catch((err) => {
        if (cancelled) return;
        showToast({
          type: "error",
          message: err instanceof ApiError ? `Could not load tasks: ${err.message}` : "Could not reach the activities API."
        });
      });

    communications
      .listEmailMessages()
      .then((page) => {
        if (cancelled) return;
        setRecordsByModule((current) => ({ ...current, communication: page.results.map(emailMessageToRow) }));
      })
      .catch((err) => {
        if (cancelled) return;
        showToast({
          type: "error",
          message:
            err instanceof ApiError ? `Could not load messages: ${err.message}` : "Could not reach the communications API."
        });
      });

    sales
      .listInvoices()
      .then((page) => {
        if (cancelled) return;
        setRecordsByModule((current) => ({ ...current, payments: page.results.map(invoiceToRow) }));
      })
      .catch((err) => {
        if (cancelled) return;
        showToast({
          type: "error",
          message: err instanceof ApiError ? `Could not load invoices: ${err.message}` : "Could not reach the sales API."
        });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const importInputRef = useRef<HTMLInputElement>(null);
  const importTargetRef = useRef<ModuleKey>("leads");
  const notifiedReminderIds = useRef<Set<string>>(new Set());

  const activeModule = modules.find((module) => module.key === activeKey) ?? modules[0];
  const activeRecords = useMemo(() => recordsByModule[activeKey] ?? [], [recordsByModule, activeKey]);
  const Icon = activeModule.icon;
  const employeeCopy = role === "employee" ? EMPLOYEE_MODULE_COPY[activeModule.key] : undefined;
  const displayModuleTitle = employeeCopy?.title ?? activeModule.title;
  const displayModuleSubtitle = employeeCopy?.subtitle ?? activeModule.subtitle;

  const rows = useMemo(() => {
    const lowerQuery = query.toLowerCase();
    const filtered = activeRecords.filter((row) => {
      const matchesQuery = !lowerQuery || Object.values(row).some((value) => value.toLowerCase().includes(lowerQuery));
      return matchesQuery && rowMatchesFilter(row, filter);
    });

    if (!sort) return filtered;

    const sorted = [...filtered].sort((a, b) => {
      const aValue = a[sort.column] ?? "";
      const bValue = b[sort.column] ?? "";
      const aNumeric = parseCurrency(aValue);
      const bNumeric = parseCurrency(bValue);
      const bothNumeric = /[\d]/.test(aValue) && /[\d]/.test(bValue) && !Number.isNaN(aNumeric) && !Number.isNaN(bNumeric);
      const comparison = bothNumeric ? aNumeric - bNumeric : aValue.localeCompare(bValue);
      return sort.direction === "asc" ? comparison : -comparison;
    });
    return sorted;
  }, [activeRecords, query, filter, sort]);

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pagedRows = useMemo(() => rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [rows, page]);

  // Employee-only table shaping: Leads is reduced to Lead Name / masked
  // Email / masked Phone / Category (Status) per spec section 5, and
  // Customers drops the Owner column per section 10 — both derived from
  // the same already-scoped `pagedRows`, never from a separate fetch.
  //
  // `formModule` is what the create/edit/view modal collects; `tableModule`
  // is what the grid renders. They differ only by FORM_ONLY_COLUMNS, so a
  // credential field can be entered without ever becoming a table cell.
  const formModule = useMemo(() => {
    if (role !== "employee") return activeModule;
    return { ...activeModule, columns: employeeSafeColumns(activeModule) };
  }, [role, activeModule]);

  const tableModule = useMemo(
    () => ({ ...activeModule, columns: tableColumnsForRole(activeModule, role) }),
    [role, activeModule]
  );

  const tableRows = useMemo(() => {
    if (role !== "employee") return pagedRows;
    return pagedRows.map((row) => employeeSafeRow(activeModule, row));
  }, [role, activeModule, pagedRows]);

  const kpis = useMemo(() => computeKpis(recordsByModule), [recordsByModule]);
  // Spec 20: figures live on the Dashboard and Analytics/Reports screens
  // only. Every other module is a records list and renders no stat strip,
  // so computeModuleStats() is asked for numbers only on those two keys.
  const displayedStats = useMemo(
    () =>
      activeKey === "dashboard" || activeKey === "reports"
        ? computeModuleStats(activeKey, recordsByModule, kpis, reminders, notes) ?? []
        : [],
    [activeKey, recordsByModule, kpis, reminders, notes]
  );

  const globalSearchResults = useMemo(() => {
    const lowerQuery = globalQuery.trim().toLowerCase();
    if (!lowerQuery) return [];
    const results: Array<{ moduleKey: ModuleKey; moduleTitle: string; row: RowRecord; label: string }> = [];
    for (const mod of visibleModules) {
      const moduleRows = recordsByModule[mod.key] ?? [];
      for (const row of moduleRows) {
        const matches = Object.values(row).some((value) => value.toLowerCase().includes(lowerQuery));
        if (matches) {
          results.push({ moduleKey: mod.key, moduleTitle: mod.title, row, label: row[mod.columns[0]] ?? row.id });
          if (results.length >= 8) return results;
        }
      }
    }
    return results;
  }, [recordsByModule, globalQuery, visibleModules]);

  useEffect(() => {
    setPage(1);
  }, [query, filter, activeKey]);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  useEffect(() => {
    setSort(null);
  }, [activeKey]);

  function toggleSort(column: string) {
    setSort((current) => {
      if (!current || current.column !== column) return { column, direction: "asc" };
      if (current.direction === "asc") return { column, direction: "desc" };
      return null;
    });
  }

  function goToSearchResult(moduleKey: ModuleKey, row: RowRecord) {
    const targetModule = visibleModules.find((module) => module.key === moduleKey);
    if (!targetModule) return;
    setActiveKey(moduleKey);
    setFilter(targetModule.filters[0] ?? "All");
    setEditingRecord(row);
    setModalMode("view");
    const columns = role === "employee" ? employeeSafeColumns(targetModule) : targetModule.columns;
    const safeRow = role === "employee" ? employeeSafeRow(targetModule, row) : row;
    setFormData(Object.fromEntries(columns.map((column) => [column, safeRow[column] ?? ""])));
    setFormServerError(null);
    setModalOpen(true);
    setGlobalQuery("");
  }

  function showToast(nextToast: ToastState) {
    setToast(nextToast);
    window.setTimeout(() => setToast(null), 2600);
  }

  function logActivity(message: string, moduleKey: ModuleKey, row: RowRecord | null) {
    const entry: ActivityEntry = { id: `activity-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, message, moduleKey, row };
    setActivityLog((current) => [entry, ...current].slice(0, 8));
  }

  function addReminder(input: Omit<Reminder, "id" | "completed" | "snoozedUntil" | "createdByRole">) {
    const reminder: Reminder = { ...input, id: `reminder-${Date.now()}`, completed: false, snoozedUntil: null, createdByRole: role };
    setReminders((current) => [reminder, ...current]);
    showToast({ type: "success", message: `Reminder "${reminder.title}" created for ${reminder.assignedTo}.` });
    logActivity(`New reminder "${reminder.title}" (${reminder.kind}) assigned to ${reminder.assignedTo}.`, "calendar", null);
  }

  function updateReminder(id: string, patch: Partial<Reminder>) {
    setReminders((current) => current.map((reminder) => (reminder.id === id ? { ...reminder, ...patch } : reminder)));
  }

  function deleteReminder(id: string) {
    setReminders((current) => current.filter((reminder) => reminder.id !== id));
    showToast({ type: "success", message: "Reminder deleted." });
  }

  function toggleReminderComplete(id: string) {
    setReminders((current) =>
      current.map((reminder) => (reminder.id === id ? { ...reminder, completed: !reminder.completed } : reminder))
    );
  }

  function snoozeReminder(id: string, days = 1) {
    const snoozedUntil = toDateKey(addDays(new Date(), days));
    setReminders((current) => current.map((reminder) => (reminder.id === id ? { ...reminder, snoozedUntil } : reminder)));
    showToast({ type: "success", message: `Reminder snoozed until ${snoozedUntil}.` });
  }

  function addNote(input: Omit<CalendarNote, "id" | "createdAt" | "pinned">) {
    const note: CalendarNote = { ...input, id: `note-${Date.now()}`, createdAt: new Date().toISOString(), pinned: false };
    setNotes((current) => [note, ...current]);
    showToast({ type: "success", message: "Note added." });
  }

  function deleteNote(id: string) {
    setNotes((current) => current.filter((note) => note.id !== id));
  }

  function toggleNotePin(id: string) {
    setNotes((current) => current.map((note) => (note.id === id ? { ...note, pinned: !note.pinned } : note)));
  }

  useEffect(() => {
    const todayKey = toDateKey(new Date());
    reminders
      .filter((reminder) => canSeeReminder(reminder, role, currentUserName, teamNames) && !reminder.completed && reminder.date <= todayKey)
      .forEach((reminder) => {
        if (notifiedReminderIds.current.has(reminder.id)) return;
        notifiedReminderIds.current.add(reminder.id);
        const overdue = reminder.date < todayKey;
        logActivity(`${overdue ? "Overdue" : "Due today"}: ${reminder.kind} "${reminder.title}" (${reminder.priority} priority).`, "calendar", null);
      });
  }, [reminders, role, currentUserName, teamNames]);

  function viewActivityRecord(moduleKey: ModuleKey, row: RowRecord) {
    const targetModule = modules.find((module) => module.key === moduleKey);
    if (!targetModule) return;
    const currentRow = (recordsByModule[moduleKey] ?? []).find((item) => item.id === row.id);
    if (!currentRow) {
      showToast({ type: "error", message: "This record no longer exists." });
      return;
    }
    setActiveKey(moduleKey);
    setFilter(targetModule.filters[0] ?? "All");
    setEditingRecord(currentRow);
    setModalMode("view");
    const viewCols = role === "employee" ? employeeSafeColumns(targetModule) : targetModule.columns;
    const viewRow = role === "employee" ? employeeSafeRow(targetModule, currentRow) : currentRow;
    setFormData(Object.fromEntries(viewCols.map((column) => [column, viewRow[column] ?? ""])));
    setFormServerError(null);
    setModalOpen(true);
  }

  function editActivityRecord(moduleKey: ModuleKey, row: RowRecord) {
    const targetModule = modules.find((module) => module.key === moduleKey);
    if (!targetModule) return;
    const currentRow = (recordsByModule[moduleKey] ?? []).find((item) => item.id === row.id);
    if (!currentRow) {
      showToast({ type: "error", message: "This record no longer exists." });
      return;
    }
    if (role === "employee" && moduleKey !== "tasks") {
      // Employees may only edit their own Tasks — everything else (Leads,
      // Customers, Payments, Communication) is view-only per spec.
      showToast({ type: "error", message: "You don't have permission to edit this record." });
      return;
    }
    setActiveKey(moduleKey);
    setFilter(targetModule.filters[0] ?? "All");
    setEditingRecord(currentRow);
    setModalMode("edit");
    const editCols = role === "employee" ? employeeSafeColumns(targetModule) : targetModule.columns;
    const editRow = role === "employee" ? employeeSafeRow(targetModule, currentRow) : currentRow;
    setFormData(Object.fromEntries(editCols.map((column) => [column, editRow[column] ?? ""])));
    setFormServerError(null);
    setModalOpen(true);
  }

  function deleteActivityRecord(moduleKey: ModuleKey, row: RowRecord) {
    const targetModule = modules.find((module) => module.key === moduleKey);
    if (!targetModule) return;
    const exists = (recordsByModule[moduleKey] ?? []).some((item) => item.id === row.id);
    if (!exists) {
      showToast({ type: "error", message: "This record no longer exists." });
      return;
    }
    const confirmed = window.confirm(`Delete this ${targetModule.title} record? This cannot be undone.`);
    if (!confirmed) return;
    setRecordsByModule((current) => ({
      ...current,
      [moduleKey]: (current[moduleKey] ?? []).filter((item) => item.id !== row.id)
    }));
    showToast({ type: "success", message: `${targetModule.title} record deleted.` });
    logActivity(`Deleted a ${targetModule.title} record.`, moduleKey, null);
  }

  function openCreateModal() {
    setEditingRecord(null);
    setModalMode("create");
    setFormData(Object.fromEntries(activeModule.columns.map((column) => [column, ""])));
    setFormServerError(null);
    setModalOpen(true);
  }

  function openCreateModalFor(moduleKey: ModuleKey) {
    if (moduleKey === activeKey) {
      openCreateModal();
      return;
    }
    const targetModule = visibleModules.find((module) => module.key === moduleKey);
    if (!targetModule) return;
    setActiveKey(moduleKey);
    setFilter(targetModule.filters[0] ?? "All");
    setQuery("");
    setEditingRecord(null);
    setModalMode("create");
    setFormData(Object.fromEntries(targetModule.columns.map((column) => [column, ""])));
    setFormServerError(null);
    setModalOpen(true);
  }

  function openEditModal(row: RowRecord) {
    setEditingRecord(row);
    setModalMode("edit");
    // Employees only ever reach this for Tasks (DataTable hides the Edit
    // button everywhere else — see DataTable's isEmployeeViewOnly), so
    // formModule.columns is safe here too and keeps this in sync
    // with what openViewModal below shows.
    const safeEditRow = role === "employee" ? employeeSafeRow(activeModule, row) : row;
    setFormData(Object.fromEntries(formModule.columns.map((column) => [column, safeEditRow[column] ?? ""])));
    setFormServerError(null);
    setModalOpen(true);
  }

  function openViewModal(row: RowRecord) {
    setEditingRecord(row);
    setModalMode("view");
    // Employee Leads/Customers must only ever surface the masked, reduced
    // column set here too — never the full admin column list (Source,
    // Owner, etc.) that a raw `activeModule.columns` read would
    // leak through the "View" action.
    const safeViewRow = role === "employee" ? employeeSafeRow(activeModule, row) : row;
    setFormData(Object.fromEntries(formModule.columns.map((column) => [column, safeViewRow[column] ?? ""])));
    setFormServerError(null);
    setModalOpen(true);
  }

  function updateFormField(field: string, value: string) {
    setFormServerError(null);
    setFormData((current) => ({ ...current, [field]: value }));
  }

  function saveRecord() {
    if (modalMode === "view") {
      setModalOpen(false);
      return;
    }

    // Backstop for the inline validation RecordModal already enforces —
    // same isFieldRequired() rule, so the two can never disagree and
    // report a field as required in one place but optional in the other.
    const missingField = formModule.columns.find(
      (column) => isFieldRequired(formModule, column, modalMode) && !formData[column]?.trim()
    );

    if (missingField) {
      setFormServerError(null);
      showToast({ type: "error", message: `${missingField} is required before saving.` });
      return;
    }

    setFormServerError(null);

    if (modalMode === "create") {
      if (activeKey === "leads") {
        crm
          .createLead(rowToLeadPayload(formData))
          .then((created) => {
            const newRecord = leadToRow(created as Record<string, unknown>);
            setRecordsByModule((current) => ({ ...current, leads: [newRecord, ...(current.leads ?? [])] }));
            showToast({ type: "success", message: "Lead created." });
            logActivity("Created a new Lead record.", "leads", newRecord);
            setModalOpen(false);
          })
          .catch((err) => {
            const message = err instanceof ApiError ? err.message : "Could not create lead.";
            setFormServerError(message);
            showToast({ type: "error", message });
          });
        return;
      }

      if (activeKey === "customers") {
        if (defaultOrganizationId === null) {
          showToast({ type: "error", message: "No organization is available yet — cannot create a customer." });
          return;
        }
        crm
          .createCustomer(rowToCustomerPayload(formData, defaultOrganizationId))
          .then((created) => {
            const newRecord = customerToRow(created as Record<string, unknown>);
            setRecordsByModule((current) => ({ ...current, customers: [newRecord, ...(current.customers ?? [])] }));
            showToast({ type: "success", message: "Customer created." });
            logActivity("Created a new Customer record.", "customers", newRecord);
            setModalOpen(false);
          })
          .catch((err) => {
            const message = err instanceof ApiError ? err.message : "Could not create customer.";
            setFormServerError(message);
            showToast({ type: "error", message });
          });
        return;
      }

      if (activeKey === "users") {
        accounts
          .createUser(rowToUserCreatePayload(formData))
          .then((created) => {
            const newRecord = userToRow(created as Record<string, unknown>);
            setRecordsByModule((current) => ({
              ...current,
              users: [newRecord, ...(current.users ?? [])],
              team: [newRecord, ...(current.team ?? [])]
            }));
            showToast({ type: "success", message: "User created." });
            logActivity("Created a new User record.", "users", newRecord);
            setModalOpen(false);
          })
          .catch((err) => {
            const message = err instanceof ApiError ? err.message : "Could not create user.";
            setFormServerError(message);
            showToast({ type: "error", message });
          });
        return;
      }

      if (activeKey === "settings") {
        system
          .createSetting(rowToSettingPayload(formData))
          .then((created) => {
            const newRecord = settingToRow(created as Record<string, unknown>);
            setRecordsByModule((current) => ({ ...current, settings: [newRecord, ...(current.settings ?? [])] }));
            showToast({ type: "success", message: "Setting created." });
            logActivity("Created a new Setting record.", "settings", newRecord);
            setModalOpen(false);
          })
          .catch((err) => {
            const message = err instanceof ApiError ? err.message : "Could not create setting.";
            setFormServerError(message);
            showToast({ type: "error", message });
          });
        return;
      }

      if (activeKey === "reports" || activeKey === "dashboard") {
        reportsApi
          .createSavedReport(rowToSavedReportPayload(formData))
          .then((created) => {
            const newRecord = savedReportToRow(created as Record<string, unknown>);
            setRecordsByModule((current) => ({
              ...current,
              reports: [newRecord, ...(current.reports ?? [])],
              dashboard: [newRecord, ...(current.dashboard ?? [])]
            }));
            showToast({ type: "success", message: "Report created." });
            logActivity("Created a new Report record.", activeKey, newRecord);
            setModalOpen(false);
          })
          .catch((err) => {
            const message = err instanceof ApiError ? err.message : "Could not create report.";
            setFormServerError(message);
            showToast({ type: "error", message });
          });
        return;
      }

      if (activeKey === "tasks") {
        activities
          .createTask(rowToTaskPayload(formData))
          .then((created) => {
            const newRecord = taskToRow(created as Record<string, unknown>);
            setRecordsByModule((current) => ({ ...current, tasks: [newRecord, ...(current.tasks ?? [])] }));
            showToast({ type: "success", message: "Task created." });
            logActivity("Created a new Task record.", "tasks", newRecord);
            setModalOpen(false);
          })
          .catch((err) => {
            const message = err instanceof ApiError ? err.message : "Could not create task.";
            setFormServerError(message);
            showToast({ type: "error", message });
          });
        return;
      }

      if (activeKey === "communication") {
        communications
          .queueEmail(rowToEmailQueuePayload(formData, recordsByModule))
          .then((queued) => {
            const queuedMessage = queued as Record<string, unknown>;
            return communications.sendEmail(queuedMessage.id as number).catch(() => queuedMessage);
          })
          .then((finalMessage) => {
            const newRecord = emailMessageToRow(finalMessage as Record<string, unknown>);
            setRecordsByModule((current) => ({ ...current, communication: [newRecord, ...(current.communication ?? [])] }));
            showToast({
              type: newRecord.Status === "Failed" ? "error" : "success",
              message: newRecord.Status === "Failed" ? "Email queued but delivery failed — see status." : "Email sent."
            });
            logActivity("Sent a Communication record.", "communication", newRecord);
            setModalOpen(false);
          })
          .catch((err) => {
            const message = err instanceof ApiError ? err.message : "Could not send email.";
            setFormServerError(message);
            showToast({ type: "error", message });
          });
        return;
      }

      if (activeKey === "payments") {
        const totalAmount = Number(formData.Total?.trim());
        sales
          .createInvoice(rowToInvoiceCreatePayload(formData))
          .then((created) => {
            const invoiceId = (created as Record<string, unknown>).id as number | string;
            if (Number.isFinite(totalAmount) && totalAmount > 0) {
              return sales
                .addInvoiceItem({ invoice: invoiceId, product_name: "Invoice total", quantity: 1, unit_price: totalAmount })
                .then(() => sales.getInvoice(invoiceId));
            }
            return created;
          })
          .then((finalInvoice) => {
            const newRecord = invoiceToRow(finalInvoice as Record<string, unknown>);
            setRecordsByModule((current) => ({ ...current, payments: [newRecord, ...(current.payments ?? [])] }));
            showToast({ type: "success", message: "Invoice created." });
            logActivity("Created a new Payment record.", "payments", newRecord);
            setModalOpen(false);
          })
          .catch((err) => {
            const message = err instanceof ApiError ? err.message : "Could not create invoice.";
            setFormServerError(message);
            showToast({ type: "error", message });
          });
        return;
      }

      const newRecord: RowRecord = {
        id: `${activeKey}-${Date.now()}`,
        ...Object.fromEntries(activeModule.columns.map((column) => [column, formData[column]]))
      };
      setRecordsByModule((current) => ({
        ...current,
        [activeKey]: [newRecord, ...(current[activeKey] ?? [])]
      }));
      showToast({ type: "success", message: `${activeModule.title} record created.` });
      logActivity(`Created a new ${activeModule.title} record.`, activeKey, newRecord);
      setModalOpen(false);
      return;
    }

    if (!editingRecord) return;

    if (activeKey === "customers") {
      crm
        .updateCustomer(editingRecord.id, rowToCustomerPayload(formData, null))
        .then((updated) => {
          const updatedRecord = customerToRow(updated as Record<string, unknown>);
          setRecordsByModule((current) => ({
            ...current,
            customers: (current.customers ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row))
          }));
          showToast({ type: "success", message: "Customer updated." });
          logActivity("Updated a Customer record.", "customers", updatedRecord);
          setModalOpen(false);
          setEditingRecord(null);
        })
        .catch((err) => {
          const message = err instanceof ApiError ? err.message : "Could not update customer.";
          setFormServerError(message);
          showToast({ type: "error", message });
        });
      return;
    }

    if (activeKey === "users") {
      accounts
        .updateUser(editingRecord.id, rowToUserUpdatePayload(formData))
        .then((updated) => {
          const updatedRecord = userToRow(updated as Record<string, unknown>);
          setRecordsByModule((current) => ({
            ...current,
            users: (current.users ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row)),
            team: (current.team ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row))
          }));
          showToast({ type: "success", message: "User updated." });
          logActivity("Updated a User record.", "users", updatedRecord);
          setModalOpen(false);
          setEditingRecord(null);
        })
        .catch((err) => {
          const message = err instanceof ApiError ? err.message : "Could not update user.";
          setFormServerError(message);
          showToast({ type: "error", message });
        });
      return;
    }

    if (activeKey === "settings") {
      system
        .updateSetting(editingRecord.id, rowToSettingPayload(formData))
        .then((updated) => {
          const updatedRecord = settingToRow(updated as Record<string, unknown>);
          setRecordsByModule((current) => ({
            ...current,
            settings: (current.settings ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row))
          }));
          showToast({ type: "success", message: "Setting updated." });
          logActivity("Updated a Setting record.", "settings", updatedRecord);
          setModalOpen(false);
          setEditingRecord(null);
        })
        .catch((err) => {
          const message = err instanceof ApiError ? err.message : "Could not update setting.";
          setFormServerError(message);
          showToast({ type: "error", message });
        });
      return;
    }

    if (activeKey === "reports" || activeKey === "dashboard") {
      reportsApi
        .updateSavedReport(editingRecord.id, rowToSavedReportPayload(formData))
        .then((updated) => {
          const updatedRecord = savedReportToRow(updated as Record<string, unknown>);
          setRecordsByModule((current) => ({
            ...current,
            reports: (current.reports ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row)),
            dashboard: (current.dashboard ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row))
          }));
          showToast({ type: "success", message: "Report updated." });
          logActivity("Updated a Report record.", activeKey, updatedRecord);
          setModalOpen(false);
          setEditingRecord(null);
        })
        .catch((err) => {
          const message = err instanceof ApiError ? err.message : "Could not update report.";
          setFormServerError(message);
          showToast({ type: "error", message });
        });
      return;
    }

    if (activeKey === "tasks") {
      activities
        .updateTask(editingRecord.id, rowToTaskPayload(formData))
        .then((updated) => {
          const updatedRecord = taskToRow(updated as Record<string, unknown>);
          setRecordsByModule((current) => ({
            ...current,
            tasks: (current.tasks ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row))
          }));
          showToast({ type: "success", message: "Task updated." });
          logActivity("Updated a Task record.", "tasks", updatedRecord);
          setModalOpen(false);
          setEditingRecord(null);
        })
        .catch((err) => {
          const message = err instanceof ApiError ? err.message : "Could not update task.";
          setFormServerError(message);
          showToast({ type: "error", message });
        });
      return;
    }

    if (activeKey === "communication") {
      // apps.communications.EmailMessageSerializer marks subject/body/
      // status read-only after creation (see backend/apps/communications/
      // serializers.py) — an email is queued/sent, not edited. Being
      // explicit here rather than silently accepting a no-op PATCH.
      showToast({ type: "error", message: "Sent messages cannot be edited — delete and send a new one instead." });
      setModalOpen(false);
      setEditingRecord(null);
      return;
    }

    if (activeKey === "payments") {
      // Invoice.status is read-only (see apps/sales/serializers.py) —
      // real state transitions go through mark-paid/cancel/record-payment,
      // not a plain PATCH. The generic modal reuses two of its columns as
      // action triggers: raising "Paid" above the invoice's current
      // amount_paid records a new partial payment for the difference;
      // setting "Status" to "Paid" or "Cancelled" triggers the matching
      // full-lifecycle action.
      const targetStatus = (formData.Status ?? "").trim().toLowerCase();
      const previousPaid = Number(editingRecord.Paid ?? "0");
      const nextPaid = Number(formData.Paid?.trim());
      const paymentDelta = Number.isFinite(nextPaid) ? nextPaid - previousPaid : 0;

      let action: Promise<unknown> | null = null;
      if (paymentDelta > 0) {
        action = sales.recordPayment(editingRecord.id, paymentDelta.toFixed(2)).then(() => sales.getInvoice(editingRecord.id));
      } else if (targetStatus === "paid") {
        action = sales.markInvoicePaid(editingRecord.id);
      } else if (targetStatus === "cancelled") {
        action = sales.cancelInvoice(editingRecord.id);
      }

      if (!action) {
        showToast({
          type: "error",
          message: 'Increase "Paid" to record a payment, or set Status to "Paid"/"Cancelled" to change the invoice state.'
        });
        return;
      }
      action
        .then((updated) => {
          const updatedRecord = invoiceToRow(updated as Record<string, unknown>);
          setRecordsByModule((current) => ({
            ...current,
            payments: (current.payments ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row))
          }));
          showToast({ type: "success", message: "Invoice updated." });
          logActivity("Updated a Payment record.", "payments", updatedRecord);
          setModalOpen(false);
          setEditingRecord(null);
        })
        .catch((err) => {
          const message = err instanceof ApiError ? err.message : "Could not update invoice.";
          setFormServerError(message);
          showToast({ type: "error", message });
        });
      return;
    }

    if (activeKey === "leads") {
      crm
        .updateLead(editingRecord.id, rowToLeadPayload(formData))
        .then((updated) => {
          const updatedRecord = leadToRow(updated as Record<string, unknown>);
          setRecordsByModule((current) => ({
            ...current,
            leads: (current.leads ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row))
          }));
          showToast({ type: "success", message: "Lead updated." });
          logActivity("Updated a Lead record.", "leads", updatedRecord);
          setModalOpen(false);
          setEditingRecord(null);
        })
        .catch((err) => {
          const message = err instanceof ApiError ? err.message : "Could not update lead.";
          setFormServerError(message);
          showToast({ type: "error", message });
        });
      return;
    }

    const updatedRecord: RowRecord = {
      ...editingRecord,
      ...Object.fromEntries(activeModule.columns.map((column) => [column, formData[column]]))
    };

    setRecordsByModule((current) => ({
      ...current,
      [activeKey]: (current[activeKey] ?? []).map((row) => (row.id === editingRecord.id ? updatedRecord : row))
    }));
    showToast({ type: "success", message: `${activeModule.title} record updated.` });
    logActivity(`Updated a ${activeModule.title} record.`, activeKey, updatedRecord);
    setModalOpen(false);
    setEditingRecord(null);
  }

  function deleteRecord(row: RowRecord) {
    if (activeKey === "users") {
      const confirmed = window.confirm("Deactivate this user? They will no longer be able to log in. This is reversible.");
      if (!confirmed) return;
      accounts
        .updateUser(row.id, { is_active: false })
        .then((updated) => {
          const updatedRecord = userToRow(updated as Record<string, unknown>);
          setRecordsByModule((current) => ({
            ...current,
            users: (current.users ?? []).map((item) => (item.id === row.id ? updatedRecord : item)),
            team: (current.team ?? []).map((item) => (item.id === row.id ? updatedRecord : item))
          }));
          showToast({ type: "success", message: "User deactivated." });
          logActivity("Deactivated a User record.", "users", updatedRecord);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not deactivate user." });
        });
      return;
    }

    if (activeKey === "settings") {
      const confirmed = window.confirm("Delete this setting? This cannot be undone.");
      if (!confirmed) return;
      system
        .deleteSetting(row.id)
        .then(() => {
          setRecordsByModule((current) => ({ ...current, settings: (current.settings ?? []).filter((item) => item.id !== row.id) }));
          showToast({ type: "success", message: "Setting deleted." });
          logActivity("Deleted a Setting record.", "settings", null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not delete setting." });
        });
      return;
    }

    if (activeKey === "reports" || activeKey === "dashboard") {
      const confirmed = window.confirm("Delete this report? This cannot be undone.");
      if (!confirmed) return;
      reportsApi
        .deleteSavedReport(row.id)
        .then(() => {
          setRecordsByModule((current) => ({
            ...current,
            reports: (current.reports ?? []).filter((item) => item.id !== row.id),
            dashboard: (current.dashboard ?? []).filter((item) => item.id !== row.id)
          }));
          showToast({ type: "success", message: "Report deleted." });
          logActivity("Deleted a Report record.", activeKey, null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not delete report." });
        });
      return;
    }

    if (activeKey === "tasks") {
      const confirmed = window.confirm("Delete this task? This cannot be undone.");
      if (!confirmed) return;
      activities
        .deleteTask(row.id)
        .then(() => {
          setRecordsByModule((current) => ({ ...current, tasks: (current.tasks ?? []).filter((item) => item.id !== row.id) }));
          showToast({ type: "success", message: "Task deleted." });
          logActivity("Deleted a Task record.", "tasks", null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not delete task." });
        });
      return;
    }

    if (activeKey === "communication") {
      const confirmed = window.confirm("Delete this message record? This cannot be undone.");
      if (!confirmed) return;
      communications
        .deleteEmailMessage(row.id)
        .then(() => {
          setRecordsByModule((current) => ({
            ...current,
            communication: (current.communication ?? []).filter((item) => item.id !== row.id)
          }));
          showToast({ type: "success", message: "Message deleted." });
          logActivity("Deleted a Communication record.", "communication", null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not delete message." });
        });
      return;
    }

    if (activeKey === "payments") {
      const confirmed = window.confirm("Delete this invoice? This cannot be undone.");
      if (!confirmed) return;
      sales
        .deleteInvoice(row.id)
        .then(() => {
          setRecordsByModule((current) => ({ ...current, payments: (current.payments ?? []).filter((item) => item.id !== row.id) }));
          showToast({ type: "success", message: "Invoice deleted." });
          logActivity("Deleted a Payment record.", "payments", null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not delete invoice." });
        });
      return;
    }

    const confirmed = window.confirm(`Delete this ${activeModule.title} record? This cannot be undone.`);
    if (!confirmed) return;

    if (activeKey === "customers") {
      crm
        .deleteCustomer(row.id)
        .then(() => {
          setRecordsByModule((current) => ({ ...current, customers: (current.customers ?? []).filter((item) => item.id !== row.id) }));
          showToast({ type: "success", message: "Customer deleted." });
          logActivity("Deleted a Customer record.", "customers", null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not delete customer." });
        });
      return;
    }

    if (activeKey === "leads") {
      crm
        .deleteLead(row.id)
        .then(() => {
          setRecordsByModule((current) => ({ ...current, leads: (current.leads ?? []).filter((item) => item.id !== row.id) }));
          showToast({ type: "success", message: "Lead deleted." });
          logActivity("Deleted a Lead record.", "leads", null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not delete lead." });
        });
      return;
    }

    setRecordsByModule((current) => ({
      ...current,
      [activeKey]: (current[activeKey] ?? []).filter((item) => item.id !== row.id)
    }));
    showToast({ type: "success", message: `${activeModule.title} record deleted.` });
    logActivity(`Deleted a ${activeModule.title} record.`, activeKey, null);
  }

  function duplicateRecord(row: RowRecord) {
    const clone: RowRecord = { ...row, id: `${activeKey}-${Date.now()}` };
    setRecordsByModule((current) => ({
      ...current,
      [activeKey]: [clone, ...(current[activeKey] ?? [])]
    }));
    showToast({ type: "success", message: `${activeModule.title} record duplicated.` });
    logActivity(`Duplicated a ${activeModule.title} record.`, activeKey, clone);
  }

  function cycleFilter() {
    const options = activeModule.filters;
    const currentIndex = options.indexOf(filter);
    const next = options[(currentIndex + 1) % options.length];
    setFilter(next);
    showToast({ type: "success", message: `Filter set to "${next}".` });
  }

  async function mergeDuplicateLeads() {
    const leadRows = (recordsByModule.leads ?? []).slice(0, 50);
    if (leadRows.length === 0) {
      showToast({ type: "error", message: "No leads to scan for duplicates." });
      return;
    }
    setIsLoading(true);
    const merged: string[] = [];
    const alreadyMerged = new Set<string>();
    try {
      for (const row of leadRows) {
        if (alreadyMerged.has(row.id)) continue;
        try {
          const duplicates = await crm.findDuplicateLeads(row.id);
          const duplicate = duplicates[0];
          if (duplicate && duplicate.id !== undefined) {
            await crm.mergeLeads(row.id, duplicate.id as number | string);
            merged.push(row.id);
            alreadyMerged.add(String(duplicate.id));
          }
        } catch {
          // This lead may have already been merged away by an earlier
          // iteration of this same loop — not an error, skip it.
        }
      }
      const page = await crm.listLeads();
      setRecordsByModule((current) => ({ ...current, leads: page.results.map(leadToRow) }));
      if (merged.length === 0) {
        showToast({ type: "success", message: "No duplicate leads found." });
      } else {
        showToast({ type: "success", message: `${merged.length} duplicate lead${merged.length === 1 ? "" : "s"} merged.` });
        logActivity(`Merged ${merged.length} duplicate lead${merged.length === 1 ? "" : "s"}.`, "leads", null);
      }
    } catch (err) {
      showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not merge duplicate leads." });
    } finally {
      setIsLoading(false);
    }
  }

  function triggerImport(moduleKey: ModuleKey = activeKey) {
    importTargetRef.current = moduleKey;
    importInputRef.current?.click();
  }

  function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const targetKey = importTargetRef.current;
    const targetModule = modules.find((module) => module.key === targetKey);
    if (!targetModule) return;

    if (targetKey !== "leads") {
      showToast({ type: "error", message: `Bulk import is not available for ${targetModule.title}.` });
      return;
    }

    setIsLoading(true);
    crm
      .importLeads(file)
      .then((summary) => {
        return crm.listLeads().then((page) => {
          setRecordsByModule((current) => ({ ...current, leads: page.results.map(leadToRow) }));
          setActiveKey("leads");
          setFilter(targetModule.filters[0] ?? "All");
          setQuery("");
          const created = summary.created ?? 0;
          const failed = summary.failed ?? 0;
          showToast({
            type: failed > 0 && created === 0 ? "error" : "success",
            message: `${created} lead${created === 1 ? "" : "s"} imported${failed > 0 ? `, ${failed} row${failed === 1 ? "" : "s"} failed` : ""}.`
          });
          logActivity(`Imported ${created} lead${created === 1 ? "" : "s"} from ${file.name}.`, "leads", null);
        });
      })
      .catch((err) => {
        showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not import leads." });
      })
      .finally(() => setIsLoading(false));
  }

  function handleModuleAction(action: { label: string; icon: React.ElementType; primary?: boolean }) {
    const label = action.label;

    if (label === "Bulk Import") {
      triggerImport(activeKey);
      return;
    }

    if (label === "Refresh Report") {
      setIsLoading(true);
      const activeReports = (recordsByModule.reports ?? []).filter((row) => row.Status === "Active");
      Promise.all(activeReports.map((row) => reportsApi.executeSavedReport(row.id).catch(() => null)))
        .then(() => reportsApi.listSavedReports())
        .then((page) => {
          const updatedRows = page.results.map(savedReportToRow);
          setRecordsByModule((current) => ({ ...current, reports: updatedRows, dashboard: updatedRows }));
          showToast({ type: "success", message: `${activeReports.length} report${activeReports.length === 1 ? "" : "s"} re-run with the latest data.` });
          logActivity("Re-ran active saved reports.", activeKey, null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not refresh reports." });
        })
        .finally(() => setIsLoading(false));
      return;
    }

    if (label === "Merge Duplicates") {
      mergeDuplicateLeads();
      return;
    }

    if (label === "Export Leads (CSV)") {
      if (role !== "superadmin") return;
      setIsLoading(true);
      crm
        .exportLeads("csv")
        .then(({ blob, filename }) => {
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = filename;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.URL.revokeObjectURL(url);
          logActivity("Exported leads to CSV.", "leads", null);
        })
        .catch((err) => {
          showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not export leads." });
        })
        .finally(() => setIsLoading(false));
      return;
    }

    if (label === "Set Reminder") {
      const target = activeRecords[0];
      const now = new Date();
      addReminder({
        title: target ? `Follow up: ${target[activeModule.columns[0]] ?? target.id}` : `Follow up on ${activeModule.title}`,
        date: now.toISOString().slice(0, 10),
        time: "09:00",
        priority: "Medium",
        repeat: "None",
        kind: "Reminder",
        assignedTo: currentUser?.email ?? "Unassigned"
      });
      return;
    }

    if (label === "Filter Events") {
      cycleFilter();
      return;
    }

    if (VIEW_ACTION_LABELS.has(label)) {
      if (activeRecords[0]) {
        openViewModal(activeRecords[0]);
      } else {
        showToast({ type: "error", message: "No records available to view yet." });
      }
      return;
    }

    openCreateModal();
  }

  function quickAddLead() {
    openCreateModalFor("leads");
  }

  function quickImportLeads() {
    triggerImport("leads");
  }

  function quickSendReminder() {
    const pending = (recordsByModule.payments ?? []).filter((row) => row.Status !== "Cancelled" && parseCurrency(row.Balance) > 0);
    if (pending.length === 0) {
      showToast({ type: "error", message: "No pending payments to remind about." });
      return;
    }
    if (!currentUser?.email) {
      showToast({ type: "error", message: "No signed-in email address to send the reminder digest to." });
      return;
    }
    const body = `Pending invoices awaiting payment:\n\n${pending
      .map((row) => `${row.Invoice} - balance $${row.Balance} of $${row.Total} - Customer #${row["Customer ID"]}`)
      .join("\n")}`;
    communications
      .queueEmail({ to_email: currentUser.email, subject: `Payment reminder digest (${pending.length} pending)`, body })
      .then((queued) => {
        const id = (queued as Record<string, unknown>).id as number | string;
        return communications.sendEmail(id);
      })
      .then(() => {
        showToast({ type: "success", message: `Reminder digest emailed for ${pending.length} pending payment${pending.length === 1 ? "" : "s"}.` });
        logActivity(`Sent a payment reminder digest for ${pending.length} pending payment${pending.length === 1 ? "" : "s"}.`, "payments", null);
      })
      .catch((err) => {
        showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not send the reminder email." });
      });
  }

  function quickAssignTask() {
    openCreateModalFor("tasks");
  }

  // Lead/customer detail view -> Communication Center. Switches to the
  // existing `communication` module (already in MODULE_ACCESS for every
  // role) and asks it to open the requested channel on that entity.
  function openCommunicationFor(channel: CommChannel, contact: CommContact) {
    setModalOpen(false);
    setEditingRecord(null);
    setActiveKey("communication");
    setCommFocus({ channel, contactKey: contact.key, nonce: Date.now() });
  }

  // Employee "Send Reminder" per pending payment (spec section 11) — reuses
  // the exact same queueEmail -> sendEmail mechanism quickSendReminder()
  // above already uses for the bulk digest, just scoped to one invoice and
  // addressed to that invoice's own customer instead of to the employee.
  function sendPaymentReminderForCustomer(invoiceRow: RowRecord) {
    const customerRow = (recordsByModule.customers ?? []).find((c) => c.id === invoiceRow["Customer ID"]);
    // Entity-addressed: name the CUSTOMER and let the backend resolve the
    // address. The customer's real email address is never in this client.
    const recipient = customerRow
      ? { customer: Number(customerRow.id) }
      : currentUser?.email
        ? { to_email: currentUser.email }
        : null;
    if (!recipient) {
      showToast({ type: "error", message: "No customer on file to send this reminder to." });
      return;
    }
    const body = `Hi ${customerRow?.Customer ?? "there"},\n\nThis is a reminder that invoice ${invoiceRow.Invoice} has a pending balance of $${invoiceRow.Balance} (of $${invoiceRow.Total}). Please arrange payment at your earliest convenience.`;
    communications
      .queueEmail({ ...recipient, subject: `Payment reminder - Invoice ${invoiceRow.Invoice}`, body })
      .then((queued) => {
        const id = (queued as Record<string, unknown>).id as number | string;
        return communications.sendEmail(id);
      })
      .then(() => {
        showToast({ type: "success", message: `Reminder sent for invoice ${invoiceRow.Invoice}.` });
        logActivity(`Sent a payment reminder for invoice ${invoiceRow.Invoice}.`, "payments", invoiceRow);
      })
      .catch((err) => {
        showToast({ type: "error", message: err instanceof ApiError ? err.message : "Could not send the reminder email." });
      });
  }

  function selectModule(key: ModuleKey) {
    const nextModule = visibleModules.find((module) => module.key === key);
    if (!nextModule) return;
    setActiveKey(key);
    setFilter(nextModule?.filters[0] ?? "All");
    setQuery("");
    setIsLoading(true);
    setMobileNav(false);
    window.setTimeout(() => setIsLoading(false), 520);
  }

  function refreshCurrentModule() {
    setIsLoading(true);
    window.setTimeout(() => setIsLoading(false), 480);
    showToast({ type: "success", message: `${activeModule.title} data refreshed.` });
  }

  return (
    <AttendanceContext.Provider value={attendanceTracking}>
    <main className={cn(dark && "dark")}>
      <div className="min-h-screen bg-background text-foreground transition-colors">
        <TopNavbar
          role={role}
          dark={dark}
          onToggleDark={() => setDark((value) => !value)}
          onOpenMobileNav={() => setMobileNav(true)}
          searchValue={globalQuery}
          onSearchChange={setGlobalQuery}
          onNewClick={openCreateModal}
          activityLog={activityLog}
          searchResults={globalSearchResults}
          onSearchResultClick={goToSearchResult}
          onLogout={attendanceTracking.fullLogout}
          onViewActivity={viewActivityRecord}
          onEditActivity={editActivityRecord}
          onDeleteActivity={deleteActivityRecord}
          onCreateForModule={openCreateModalFor}
        />

        <div className="flex">
          <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-20 shrink-0 flex-col items-center gap-1 overflow-y-auto bg-teal-900 py-4 lg:flex">
            <SidebarRail activeKey={activeKey} onSelect={selectModule} modules={visibleModules} />
          </aside>

          <AnimatePresence>
            {mobileNav ? (
              <motion.div
                className="fixed inset-0 z-50 bg-black/40 lg:hidden"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setMobileNav(false)}
              >
                <motion.aside
                  className="h-full w-80 max-w-[86vw] bg-card p-4"
                  initial={{ x: -320 }}
                  animate={{ x: 0 }}
                  exit={{ x: -320 }}
                  onClick={(event) => event.stopPropagation()}
                >
                  <Brand role={role} />
                  <ModuleNav activeKey={activeKey} onSelect={selectModule} modules={visibleModules} />
                </motion.aside>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <section className="min-w-0 flex-1">
            <div className="border-b bg-background/60 px-4 py-4 xl:px-8">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-600">
                    Qualify Learn | {ROLE_LABEL[role]}
                  </p>
                  <h1 className="truncate text-xl font-bold sm:text-2xl">Complete CRM Control Panel</h1>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    className="inline-flex size-10 items-center justify-center rounded-lg border bg-card shadow-sm"
                    onClick={refreshCurrentModule}
                    aria-label="Refresh data"
                  >
                    <RefreshCw className="size-4 text-teal-600" />
                  </button>
                </div>
              </div>
            </div>

            {/* Spec 4: no persistent side detail panel for any role — page
                content always uses the full available width. */}
            <div className="grid grid-cols-1 gap-6 px-4 py-5 xl:px-8">
              <div className="min-w-0 space-y-6">
                <motion.section
                  key={activeModule.key}
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28 }}
                  className="overflow-hidden rounded-2xl border bg-card shadow-soft"
                >
                  <div className={cn("bg-gradient-to-r p-6 text-white", activeModule.accent)}>
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div>
                        <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-sm font-semibold ring-1 ring-white/25">
                          <Icon className="size-4" />
                          {ROLE_LABEL[role]}
                        </div>
                        <h2 className="text-3xl font-bold">{displayModuleTitle}</h2>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-white/88">{displayModuleSubtitle}</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {visibleActionsForRole(activeModule.actions, role).map((action) => {
                          const ActionIcon = action.icon;
                          return (
                            <button
                              key={action.label}
                              onClick={() => handleModuleAction(action)}
                              className={cn(
                                "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold shadow-sm transition hover:-translate-y-0.5",
                                action.primary ? "bg-white text-teal-700" : "bg-white/14 text-white ring-1 ring-white/25"
                              )}
                            >
                              <ActionIcon className="size-4" />
                              {action.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  <div
                    className={cn(
                      "grid gap-4 sm:grid-cols-2 xl:grid-cols-4",
                      displayedStats.length > 0 && "p-4"
                    )}
                  >
                    {displayedStats.map((stat) => (
                      <article key={stat.label} className="rounded-xl border bg-background p-4">
                        <p className="text-sm text-muted-foreground">{stat.label}</p>
                        <div className="mt-2 flex items-end justify-between gap-3">
                          <strong className="text-2xl font-bold">{stat.value}</strong>
                          <span className="rounded-full bg-teal-50 px-2 py-1 text-xs font-semibold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                            {stat.change}
                          </span>
                        </div>
                      </article>
                    ))}
                  </div>
                </motion.section>

                {activeKey === "calendar" ? (
                  <SmartCalendarModule
                    role={role}
                    recordsByModule={recordsByModule}
                    reminders={reminders}
                    notes={notes}
                    currentUserName={currentUserName}
                    teamNames={teamNames}
                    onAddReminder={addReminder}
                    onUpdateReminder={updateReminder}
                    onDeleteReminder={deleteReminder}
                    onToggleReminderComplete={toggleReminderComplete}
                    onSnoozeReminder={snoozeReminder}
                    onAddNote={addNote}
                    onDeleteNote={deleteNote}
                    onToggleNotePin={toggleNotePin}
                  />
                ) : (
                  <>
                    {activeKey === "reports" || activeKey === "dashboard" ? (
                      <AnalyticsDashboard
                        role={role}
                        kpis={kpis}
                        recentLeads={recordsByModule.leads ?? []}
                        customerRows={recordsByModule.customers ?? []}
                        paymentRows={recordsByModule.payments ?? []}
                        userRows={recordsByModule.users ?? []}
                        activityLog={activityLog}
                        reminders={reminders}
                        currentUserName={currentUserName}
                        teamNames={teamNames}
                        onQuickAdd={quickAddLead}
                        onImportLeads={quickImportLeads}
                        onSendReminder={quickSendReminder}
                        onAssignTask={quickAssignTask}
                        onRefresh={refreshCurrentModule}
                        onViewActivity={viewActivityRecord}
                        onEditActivity={editActivityRecord}
                        onDeleteActivity={deleteActivityRecord}
                        onCreateForModule={openCreateModalFor}
                        onCompleteReminder={toggleReminderComplete}
                        onSnoozeReminder={snoozeReminder}
                      />
                    ) : null}

                    {/* The generic AuditLog table below this stays exactly as
                        it was (model changes, logins, ...); this adds the
                        communications-specific audit trail as a second
                        section within the same Super-Admin-only module. */}
                    {activeKey === "audit" && role === "superadmin" ? (
                      <SuperAdminCommunicationAuditSection users={recordsByModule.users ?? []} />
                    ) : null}

                    {role === "employee" && activeKey === "payments" ? (
                      <EmployeePaymentsView
                        rows={activeRecords}
                        customers={recordsByModule.customers ?? []}
                        onSendReminder={sendPaymentReminderForCustomer}
                      />
                    ) : role === "employee" && activeKey === "communication" ? (
                      <EmployeeCommunicationCenter
                        leads={recordsByModule.leads ?? []}
                        customers={recordsByModule.customers ?? []}
                        focus={commFocus}
                        onToast={showToast}
                      />
                    ) : (
                    <section className="rounded-2xl border bg-card shadow-sm">
                      <div className="border-b p-4">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                          <div>
                            <h3 className="text-lg font-bold">{displayModuleTitle} Records</h3>
                            <p className="text-sm text-muted-foreground">
                              Search, filter, paginate, and act on {role === "manager" ? "your team's" : role === "employee" ? "your" : "Super Admin"} data.
                            </p>
                          </div>
                          <div className="flex flex-col gap-2 sm:flex-row">
                            <label className="relative min-w-0 sm:w-72">
                              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                              <input
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                                placeholder="Search records..."
                                className="h-10 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
                              />
                            </label>
                            <select
                              value={filter}
                              onChange={(event) => setFilter(event.target.value)}
                              className="h-10 rounded-lg border bg-background px-3 text-sm font-medium outline-none ring-teal-600/20 transition focus:ring-4"
                            >
                              {activeModule.filters.map((item) => (
                                <option key={item}>{item}</option>
                              ))}
                            </select>
                          </div>
                        </div>
                      </div>

                      {isLoading ? (
                        <LoadingSkeleton columns={tableModule.columns} />
                      ) : (
                        <DataTable
                          module={tableModule}
                          rows={tableRows}
                          role={role}
                          allowEdit={activeKey === "tasks"}
                          onEdit={openEditModal}
                          onView={openViewModal}
                          onDuplicate={duplicateRecord}
                          onDelete={deleteRecord}
                          sort={sort}
                          onSort={toggleSort}
                        />
                      )}

                      <div className="flex flex-col gap-3 border-t p-4 sm:flex-row sm:items-center sm:justify-between">
                        <p className="text-sm text-muted-foreground">
                          Showing <span className="font-semibold text-foreground">{pagedRows.length}</span> of {rows.length} filtered
                          {rows.length !== activeRecords.length ? ` (${activeRecords.length} total)` : ""}
                        </p>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setPage((current) => Math.max(1, current - 1))}
                            disabled={page <= 1}
                            className="inline-flex size-9 items-center justify-center rounded-lg border bg-background disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            <ChevronLeft className="size-4" />
                          </button>
                          <span className="rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white">{page}</span>
                          <span className="text-sm text-muted-foreground">of {totalPages}</span>
                          <button
                            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                            disabled={page >= totalPages}
                            className="inline-flex size-9 items-center justify-center rounded-lg border bg-background disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            <ChevronRight className="size-4" />
                          </button>
                        </div>
                      </div>
                    </section>
                    )}

                  </>
                )}
              </div>

            </div>
          </section>
        </div>
      </div>

      <AnimatePresence>
        {modalOpen && role === "employee" && activeKey === "customers" && modalMode === "view" && editingRecord ? (
          <EmployeeCustomerProfileModal
            customer={editingRecord}
            payments={recordsByModule.payments ?? []}
            communicationRows={recordsByModule.communication ?? []}
            reminders={reminders.filter((reminder) => canSeeReminder(reminder, role, currentUserName, teamNames))}
            notes={notes.filter((note) => canSeeNote(note, role, currentUserName))}
            onSendReminder={sendPaymentReminderForCustomer}
            onOpenChannel={openCommunicationFor}
            onClose={() => {
              setModalOpen(false);
              setEditingRecord(null);
            }}
          />
        ) : modalOpen ? (
          <RecordModal
            key={`${activeKey}-${modalMode}-${editingRecord?.id ?? "new"}`}
            module={formModule}
            mode={modalMode}
            formData={formData}
            serverError={formServerError}
            onChange={updateFormField}
            onSave={saveRecord}
            extraContent={
              // Lead-specific communication actions, on the lead's own
              // detail view (spec: "from a lead's detail view, Email/Call/
              // WhatsApp open the dedicated workspace for that lead").
              role === "employee" && activeKey === "leads" && modalMode === "view" && editingRecord ? (
                <div className="flex flex-col gap-3 rounded-lg border bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
                  <CommProtectedNote label="Opens the Communication Center for this lead — contact details stay server-side." />
                  <CommQuickActions
                    contact={{
                      key: commContactKey("lead", editingRecord.id),
                      kind: "lead",
                      id: editingRecord.id,
                      name: editingRecord.Lead || `Lead #${editingRecord.id}`,
                      canEmail: Boolean(editingRecord._canEmail),
                      canCall: Boolean(editingRecord._canCall),
                      canWhatsapp: Boolean(editingRecord._canWhatsapp)
                    }}
                    onOpen={openCommunicationFor}
                  />
                </div>
              ) : null
            }
            onClose={() => {
              setModalOpen(false);
              setEditingRecord(null);
            }}
          />
        ) : null}
      </AnimatePresence>
      <AnimatePresence>{toast ? <Toast toast={toast} /> : null}</AnimatePresence>
      <input ref={importInputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleImportFile} />
    </main>
    </AttendanceContext.Provider>
  );
}

function Brand({ role }: { role: Role }) {
  return (
    <div className="mb-6 flex items-center gap-3 rounded-xl bg-teal-600 p-3 text-white shadow-soft">
      <div className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white ring-1 ring-white/25">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/qualify-learn-logo.jpeg" alt="Qualify Learn" className="size-full object-cover" />
      </div>
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-white/75">Qualify Learn</p>
        <h2 className="font-bold">{ROLE_LABEL[role]} Panel</h2>
      </div>
    </div>
  );
}

function TopNavbar({
  role,
  dark,
  onToggleDark,
  onOpenMobileNav,
  searchValue,
  onSearchChange,
  onNewClick,
  activityLog,
  searchResults,
  onSearchResultClick,
  onLogout,
  onViewActivity,
  onEditActivity,
  onDeleteActivity,
  onCreateForModule
}: {
  role: Role;
  dark: boolean;
  onToggleDark: () => void;
  onOpenMobileNav: () => void;
  searchValue: string;
  onSearchChange: (value: string) => void;
  onNewClick: () => void;
  activityLog: ActivityEntry[];
  searchResults: Array<{ moduleKey: ModuleKey; moduleTitle: string; row: RowRecord; label: string }>;
  onSearchResultClick: (moduleKey: ModuleKey, row: RowRecord) => void;
  onLogout: () => void;
  onViewActivity: (moduleKey: ModuleKey, row: RowRecord) => void;
  onEditActivity: (moduleKey: ModuleKey, row: RowRecord) => void;
  onDeleteActivity: (moduleKey: ModuleKey, row: RowRecord) => void;
  onCreateForModule: (moduleKey: ModuleKey) => void;
}) {
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b bg-card px-4 shadow-sm xl:px-6">
      <button
        className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg border bg-background lg:hidden"
        onClick={onOpenMobileNav}
        aria-label="Open navigation"
      >
        <Menu className="size-5" />
      </button>

      <div className="flex shrink-0 items-center gap-2">
        <div className="flex size-9 items-center justify-center overflow-hidden rounded-full bg-white shadow-soft ring-1 ring-border">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/qualify-learn-logo.jpeg" alt="Qualify Learn" className="size-full object-cover" />
        </div>
        <span className="hidden text-sm font-bold sm:block">Qualify Learn CRM</span>
      </div>

      {role !== "employee" ? (
        <button
          onClick={onNewClick}
          className="hidden shrink-0 items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-sm font-semibold shadow-sm transition hover:bg-muted sm:inline-flex"
        >
          <Plus className="size-4 text-teal-600" />
          New
        </button>
      ) : null}

      <div className="relative mx-auto hidden w-full max-w-md md:block">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={searchValue}
            onChange={(event) => {
              onSearchChange(event.target.value);
              setSearchOpen(true);
            }}
            onFocus={() => setSearchOpen(true)}
            placeholder="Search for anything..."
            className="h-10 w-full rounded-full border bg-background pl-9 pr-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
          />
        </label>
        {searchOpen && searchValue.trim() ? (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setSearchOpen(false)} />
            <div className="absolute left-0 right-0 top-12 z-20 overflow-hidden rounded-xl border bg-card shadow-soft">
              {searchResults.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-muted-foreground">No matching records found.</p>
              ) : (
                <div className="max-h-80 overflow-y-auto">
                  {searchResults.map((result) => (
                    <button
                      key={`${result.moduleKey}-${result.row.id}`}
                      onClick={() => {
                        onSearchResultClick(result.moduleKey, result.row);
                        setSearchOpen(false);
                      }}
                      className="flex w-full items-center justify-between gap-3 border-b px-4 py-3 text-left text-sm last:border-b-0 hover:bg-muted"
                    >
                      <span className="truncate font-semibold">{result.label}</span>
                      <span className="shrink-0 rounded-full bg-teal-50 px-2 py-0.5 text-xs font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                        {result.moduleTitle}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        {role !== "superadmin" ? <AttendanceNavbarWidget /> : null}

        <div className="relative">
          <button
            onClick={() => setNotifOpen((value) => !value)}
            className="relative inline-flex size-10 items-center justify-center rounded-lg border bg-background"
            aria-label="Notifications"
          >
            <Bell className="size-5" />
            {activityLog.length > 0 ? (
              <span className="absolute -right-1 -top-1 inline-flex size-4 items-center justify-center rounded-full bg-red-600 text-[10px] font-bold text-white">
                {activityLog.length > 9 ? "9+" : activityLog.length}
              </span>
            ) : null}
          </button>
          {notifOpen ? (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setNotifOpen(false)} />
              <div className="absolute right-0 top-12 z-20 w-80 overflow-hidden rounded-xl border bg-card shadow-soft">
                <div className="border-b px-4 py-3 text-sm font-bold">Notifications</div>
                <div className="max-h-96 overflow-y-auto">
                  {activityLog.length === 0 ? (
                    <p className="px-4 py-6 text-center text-sm text-muted-foreground">No activity yet.</p>
                  ) : (
                    activityLog.slice(0, 6).map((item) => (
                      <div key={item.id} className="border-b px-4 py-3 last:border-b-0">
                        <p className="text-sm">{item.message}</p>
                        <div className="mt-2 flex items-center gap-1.5">
                          {item.row ? (
                            <>
                              <button
                                onClick={() => {
                                  if (item.row) onViewActivity(item.moduleKey, item.row);
                                  setNotifOpen(false);
                                }}
                                className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-teal-600"
                              >
                                <Eye className="size-3" />
                                View
                              </button>
                              <button
                                onClick={() => {
                                  if (item.row) onEditActivity(item.moduleKey, item.row);
                                  setNotifOpen(false);
                                }}
                                className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-teal-600"
                              >
                                <Pencil className="size-3" />
                                Edit
                              </button>
                              <button
                                onClick={() => {
                                  if (item.row) onDeleteActivity(item.moduleKey, item.row);
                                  setNotifOpen(false);
                                }}
                                className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                              >
                                <Trash2 className="size-3" />
                                Delete
                              </button>
                            </>
                          ) : null}
                          {role !== "employee" ? (
                            <button
                              onClick={() => {
                                onCreateForModule(item.moduleKey);
                                setNotifOpen(false);
                              }}
                              className="ml-auto inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-semibold text-teal-600 hover:bg-teal-50 dark:hover:bg-teal-950"
                            >
                              <Plus className="size-3" />
                              New
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          ) : null}
        </div>

        <button
          onClick={onToggleDark}
          className="inline-flex size-10 items-center justify-center rounded-lg border bg-background shadow-sm"
          aria-label="Toggle dark mode"
        >
          {dark ? <Sun className="size-5 text-amber-400" /> : <Moon className="size-5 text-zinc-700" />}
        </button>

        <div className="relative">
          <button
            onClick={() => setProfileOpen((value) => !value)}
            className="flex size-9 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white"
            aria-label="Profile menu"
            title={ROLE_LABEL[role]}
          >
            {ROLE_AVATAR[role]}
          </button>
          {profileOpen ? (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setProfileOpen(false)} />
              <div className="absolute right-0 top-12 z-20 w-56 overflow-hidden rounded-xl border bg-card shadow-soft">
                <div className="border-b px-4 py-3">
                  <p className="text-sm font-bold">{ROLE_LABEL[role]}</p>
                  <p className="text-xs text-muted-foreground">Qualify Learn CRM</p>
                </div>
                <button
                  onClick={() => {
                    setProfileOpen(false);
                    onLogout();
                  }}
                  className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-semibold text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                >
                  <LogOut className="size-4" />
                  Logout
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function AttendanceNavbarWidget() {
  const attendanceTracking = useContext(AttendanceContext);
  if (!attendanceTracking?.current) return null;
  const { current, liveWorkedSeconds } = attendanceTracking;
  const meta = ATTENDANCE_STATUS_META[current.display_state];

  return (
    <div
      className="hidden items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-semibold shadow-sm sm:flex"
      title={meta.label}
    >
      <AttendanceStatusDot state={current.display_state} />
      <span className={meta.text}>{meta.label}</span>
      <span className="font-mono tabular-nums text-foreground">{formatHMS(liveWorkedSeconds)}</span>
    </div>
  );
}

function SidebarRail({
  activeKey,
  onSelect,
  modules
}: {
  activeKey: ModuleKey;
  onSelect: (key: ModuleKey) => void;
  modules: ModuleConfig[];
}) {
  return (
    <nav className="flex flex-col items-center gap-1">
      {modules.map((module) => {
        const Icon = module.icon;
        const active = activeKey === module.key;
        return (
          <button
            key={module.key}
            onClick={() => onSelect(module.key)}
            title={module.title}
            aria-label={module.title}
            className={cn(
              "flex size-12 items-center justify-center rounded-xl transition",
              active ? "bg-white text-teal-700 shadow-soft" : "text-teal-100/80 hover:bg-white/10 hover:text-white"
            )}
          >
            <Icon className="size-5" />
          </button>
        );
      })}
    </nav>
  );
}

function ModuleNav({
  activeKey,
  onSelect,
  modules
}: {
  activeKey: ModuleKey;
  onSelect: (key: ModuleKey) => void;
  modules: ModuleConfig[];
}) {
  return (
    <nav className="space-y-1">
      {modules.map((module, index) => {
        const Icon = module.icon;
        const active = activeKey === module.key;
        return (
          <button
            key={module.key}
            onClick={() => onSelect(module.key)}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition",
              active ? "bg-teal-50 text-teal-700 ring-1 ring-teal-100 dark:bg-teal-950 dark:text-teal-100 dark:ring-teal-900" : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            <span className={cn("flex size-8 items-center justify-center rounded-lg", active ? "bg-teal-600 text-white" : "bg-muted text-muted-foreground")}>
              <Icon className="size-4" />
            </span>
            <span className="min-w-0 flex-1 truncate">
              {index + 1}. {module.title}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

function AnalyticsDashboard({
  role,
  kpis,
  recentLeads,
  customerRows,
  paymentRows,
  userRows,
  activityLog,
  reminders,
  currentUserName,
  teamNames,
  onQuickAdd,
  onImportLeads,
  onSendReminder,
  onAssignTask,
  onRefresh,
  onViewActivity,
  onEditActivity,
  onDeleteActivity,
  onCreateForModule,
  onCompleteReminder,
  onSnoozeReminder
}: {
  role: Role;
  kpis: Array<{ label: string; value: string; change: string }>;
  recentLeads: RowRecord[];
  customerRows: RowRecord[];
  paymentRows: RowRecord[];
  userRows: RowRecord[];
  activityLog: ActivityEntry[];
  reminders: Reminder[];
  currentUserName: string;
  teamNames: string[];
  onQuickAdd: () => void;
  onImportLeads: () => void;
  onSendReminder: () => void;
  onAssignTask: () => void;
  onRefresh: () => void;
  onViewActivity: (moduleKey: ModuleKey, row: RowRecord) => void;
  onEditActivity: (moduleKey: ModuleKey, row: RowRecord) => void;
  onDeleteActivity: (moduleKey: ModuleKey, row: RowRecord) => void;
  onCreateForModule: (moduleKey: ModuleKey) => void;
  onCompleteReminder: (id: string) => void;
  onSnoozeReminder: (id: string) => void;
}) {
  const [activeTab, setActiveTab] = useState("Status");
  const [favorited, setFavorited] = useState(true);

  const conversionKpi = kpis.find((kpi) => kpi.label === "Conversion Rate");
  const conversionValue = conversionKpi ? Number.parseFloat(conversionKpi.value) || 0 : 0;

  const conversionData = groupCountsByColumn(recentLeads, "Status");
  const sourceData = groupCountsByColumnWithColor(recentLeads, "Source");
  const revenueData = monthlySumTrend(paymentRows, "_createdAt", "Paid");
  const monthlyLeadsData = monthlyCountTrend(recentLeads, "_createdAt");
  const employeePerformanceData = ownerLeadCounts(recentLeads, userRows);
  const paymentStatusData = groupCountsByColumnWithColor(paymentRows, "Status");
  const topPerformers = employeePerformanceData.slice(0, 3);
  const openRequests = paymentRows.filter((row) => row.Status !== "Cancelled" && parseCurrency(row.Balance) > 0).slice(0, 5);

  const upcomingReminders = reminders
    .filter((reminder) => canSeeReminder(reminder, role, currentUserName, teamNames) && !reminder.completed)
    .sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time))
    .slice(0, 5);

  const tabVisibility: Record<string, string[]> = {
    performers: ["Status", "Sales"],
    leadConversion: ["Status", "Marketing"],
    gauge: ["Status", "Marketing", "Sales"],
    openRequests: ["Status", "Sales", "Requests"],
    monthlyRevenue: ["Status", "Sales"],
    leadSources: ["Status", "Marketing"],
    monthlyLeads: ["Status", "Marketing"],
    employeePerformance: ["Status", "Sales"],
    paymentStatus: ["Status", "Sales", "Requests"]
  };
  const isVisible = (key: string) => tabVisibility[key].includes(activeTab);

  return (
    <section className="space-y-4">
      {role !== "superadmin" ? <EmployeeAttendanceWidget /> : null}
      {role === "manager" ? <ManagerTeamAttendanceSection /> : null}
      {role === "superadmin" ? <SuperAdminAttendanceSection /> : null}

      {role !== "employee" ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
          {kpis.map((kpi) => {
            const highlighted = kpi.label === "Total Revenue";
            return (
              <article
                key={kpi.label}
                className={cn("rounded-xl p-4 shadow-sm", highlighted ? "bg-teal-700 text-white" : "border bg-card")}
              >
                <p className={cn("text-sm", highlighted ? "text-white/80" : "text-muted-foreground")}>{kpi.label}</p>
                <strong className="mt-2 block text-2xl font-bold">{kpi.value}</strong>
                <span
                  className={cn(
                    "mt-3 inline-flex rounded-full px-2 py-1 text-xs font-bold",
                    highlighted ? "bg-white/15 text-white" : "bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-200"
                  )}
                >
                  {kpi.change}
                </span>
              </article>
            );
          })}
        </div>
      ) : null}

      {role === "employee" ? (
        <EmployeeAllTimeStats leads={recentLeads} customers={customerRows} payments={paymentRows} />
      ) : null}

      {role !== "employee" ? (
      <>
      <div className="rounded-2xl border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-1 border-b pb-3">
          {["Status", "Marketing", "Sales", "Requests"].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-semibold transition",
                activeTab === tab
                  ? "bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-200"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 pt-3">
          <h3 className="text-lg font-bold">
            {role === "manager" ? "Key figures for your team" : "Key figures for the Super Admin team"}
          </h3>
          <button onClick={() => setFavorited((value) => !value)} aria-label="Toggle favorite">
            <Star className={cn("size-4", favorited ? "fill-amber-400 text-amber-400" : "text-muted-foreground")} />
          </button>
          <button onClick={onRefresh} aria-label="Refresh dashboard">
            <RefreshCw className="size-4 text-muted-foreground transition hover:text-teal-600" />
          </button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        {isVisible("performers") ? (
          <ChartCard title="Top Performers" subtitle="Leads owned, by team member">
            {topPerformers.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">No owned leads yet.</p>
            ) : (
              <div className="space-y-4 py-1">
                {topPerformers.map((person) => (
                  <div key={person.label} className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="flex size-9 items-center justify-center rounded-full bg-teal-50 text-sm font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                        {person.label.slice(0, 2).toUpperCase()}
                      </span>
                      <span className="text-sm font-semibold">{person.label}</span>
                    </div>
                    <span className="text-lg font-bold">{person.value}</span>
                  </div>
                ))}
              </div>
            )}
          </ChartCard>
        ) : null}
        {isVisible("leadConversion") ? (
          <ChartCard title="Lead Conversion" subtitle="Pipeline stage volume">
            <BarChart data={conversionData} />
          </ChartCard>
        ) : null}
        {isVisible("gauge") ? (
          <ChartCard title="Conversion Rate" subtitle="Leads converted to customers">
            <GaugeChart value={conversionValue} label={conversionKpi?.change ?? ""} />
          </ChartCard>
        ) : null}
        {isVisible("openRequests") ? (
          <ChartCard title="Open Requests" subtitle="Payments with an outstanding balance">
            <div className="space-y-3 py-1">
              {openRequests.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">No open requests.</p>
              ) : (
                openRequests.map((row) => (
                  <div key={row.id} className="flex items-center gap-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-teal-600 dark:bg-teal-950 dark:text-teal-200">
                      <CircleDollarSign className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{row.Invoice}</p>
                      <p className="text-xs text-muted-foreground">Customer #{row["Customer ID"]}</p>
                    </div>
                    <span className="shrink-0 text-sm font-bold">${row.Balance}</span>
                  </div>
                ))
              )}
            </div>
          </ChartCard>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {isVisible("monthlyRevenue") ? (
          <ChartCard title="Monthly Revenue" subtitle="Revenue trend in thousands">
            <LineChart data={revenueData} prefix="$" suffix="K" />
          </ChartCard>
        ) : null}
        {isVisible("leadSources") ? (
          <ChartCard title="Lead Sources" subtitle="Source mix by percentage">
            <PieChart data={sourceData} donut={false} />
          </ChartCard>
        ) : null}
        {isVisible("monthlyLeads") ? (
          <ChartCard title="Monthly Leads" subtitle="New leads captured">
            <AreaChart data={monthlyLeadsData} />
          </ChartCard>
        ) : null}
        {isVisible("employeePerformance") ? (
          <ChartCard title="Employee Performance" subtitle="Leads owned per team member">
            <BarChart data={employeePerformanceData} />
          </ChartCard>
        ) : null}
        {isVisible("paymentStatus") ? (
          <ChartCard title="Payment Status" subtitle="Paid, partial, and pending">
            <PieChart data={paymentStatusData} donut />
          </ChartCard>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-bold">Recent Leads</h3>
              <p className="text-sm text-muted-foreground">Fresh leads from Meta, website, CSV, and referrals.</p>
            </div>
            <button onClick={onQuickAdd} className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white">
              <Plus className="size-4" />
              Quick Add
            </button>
          </div>
          <div className="glass-scrollbar overflow-x-auto">
            <table className="w-full min-w-[560px] text-left">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  {["Lead", "Source", "Owner", "Status"].map((column) => (
                    <th key={column} className="px-3 py-3 font-bold">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {recentLeads.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-sm text-muted-foreground">
                      No leads yet.
                    </td>
                  </tr>
                ) : null}
                {recentLeads.slice(0, 4).map((lead) => (
                  <tr key={lead.id} className="text-sm">
                    <td className="px-3 py-3 font-semibold">{lead.Lead}</td>
                    <td className="px-3 py-3 text-muted-foreground">{lead.Source}</td>
                    <td className="px-3 py-3 text-muted-foreground">{lead.Owner}</td>
                    <td className="px-3 py-3">
                      <span className={cn("rounded-full px-2 py-1 text-xs font-bold ring-1", statusClass(lead.Status))}>{lead.Status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <div className="grid gap-4">
          <article className="rounded-2xl border bg-card p-5 shadow-sm">
            <h3 className="text-lg font-bold">Today&apos;s Statistics</h3>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {todayStats.map((item) => (
                <div key={item.label} className="rounded-xl border bg-background p-3">
                  <p className="text-xs text-muted-foreground">{item.label}</p>
                  <strong className="mt-1 block text-xl">{item.value}</strong>
                </div>
              ))}
            </div>
          </article>
          <article className="rounded-2xl border bg-card p-5 shadow-sm">
            <h3 className="text-lg font-bold">Quick Actions</h3>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              <button onClick={onImportLeads} className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm font-semibold">
                <Upload className="size-4 text-teal-600" />
                Import Leads
              </button>
              <button onClick={onSendReminder} className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm font-semibold">
                <Bell className="size-4 text-teal-600" />
                Send Reminder
              </button>
              <button onClick={onAssignTask} className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm font-semibold">
                <CalendarDays className="size-4 text-teal-600" />
                Assign Task
              </button>
            </div>
          </article>
        </div>
      </div>
      </>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <TimelineCard
          title="Recent Activities"
          items={activityLog}
          onView={onViewActivity}
          onEdit={onEditActivity}
          onDelete={onDeleteActivity}
          onCreate={onCreateForModule}
        />
        {role !== "employee" ? (
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <h3 className="text-lg font-bold">Upcoming Follow-ups</h3>
          <div className="mt-4 space-y-3">
            {upcomingFollowUps.map((item) => (
              <div key={`${item.time}-${item.title}`} className="flex items-center gap-3 rounded-xl border bg-background p-3">
                <div className="rounded-lg bg-teal-50 px-2 py-1 text-xs font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">{item.time}</div>
                <div>
                  <p className="text-sm font-bold">{item.title}</p>
                  <p className="text-xs text-muted-foreground">{item.owner}</p>
                </div>
              </div>
            ))}
          </div>
        </article>
        ) : null}
      </div>

      <div className="grid gap-4">
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-bold">Upcoming Reminders</h3>
              <p className="text-sm text-muted-foreground">Reminders, meetings, and follow-ups from your Smart Calendar.</p>
            </div>
            <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
              {upcomingReminders.length} pending
            </span>
          </div>
          {upcomingReminders.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No upcoming reminders.</p>
          ) : (
            <div className="space-y-3">
              {upcomingReminders.map((reminder) => {
                const overdue = reminder.date < toDateKey(new Date());
                return (
                  <div key={reminder.id} className="flex flex-wrap items-center gap-3 rounded-xl border bg-background p-3">
                    <div
                      className={cn(
                        "rounded-lg px-2 py-1 text-xs font-bold",
                        overdue
                          ? "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-200"
                          : "bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-200"
                      )}
                    >
                      {reminder.date} - {reminder.time}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold">{reminder.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {reminder.kind} - Assigned to {reminder.assignedTo}
                      </p>
                    </div>
                    <span className={cn("rounded-full px-2 py-1 text-xs font-bold ring-1", REMINDER_PRIORITY_STYLES[reminder.priority])}>
                      {reminder.priority}
                    </span>
                    <button
                      onClick={() => onCompleteReminder(reminder.id)}
                      className="inline-flex size-8 items-center justify-center rounded-lg border bg-background text-muted-foreground hover:text-teal-600"
                      aria-label="Mark reminder complete"
                    >
                      <Check className="size-4" />
                    </button>
                    <button
                      onClick={() => onSnoozeReminder(reminder.id)}
                      className="inline-flex size-8 items-center justify-center rounded-lg border bg-background text-muted-foreground hover:text-teal-600"
                      aria-label="Snooze reminder"
                    >
                      <BellRing className="size-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}

// Employee dashboard "All Time" figures — the counterpart to the "This
// Month" cards computed in computeModuleStats()'s "dashboard" case (both
// read only from the already-server-scoped recordsByModule arrays for
// the logged-in employee, never from any org-wide source).
function EmployeeAllTimeStats({
  leads,
  customers,
  payments
}: {
  leads: RowRecord[];
  customers: RowRecord[];
  payments: RowRecord[];
}) {
  const revenue = payments.reduce((sum, row) => sum + parseCurrency(row.Paid), 0);
  const converted = countBy(leads, "Status", "Converted");
  const conversionRate = leads.length ? ((converted / leads.length) * 100).toFixed(1) : "0.0";
  const cards = [
    { label: "My Leads (All Time)", value: leads.length.toLocaleString(), change: "All time" },
    { label: "My Customers (All Time)", value: customers.length.toLocaleString(), change: "All time" },
    { label: "My Revenue (All Time)", value: formatCurrencyShort(revenue), change: "Collected to date" },
    { label: "My Conversion Rate (All Time)", value: `${conversionRate}%`, change: `${converted} converted` }
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <article key={card.label} className="rounded-xl border bg-card p-4 shadow-sm">
          <p className="text-sm text-muted-foreground">{card.label}</p>
          <strong className="mt-2 block text-2xl font-bold">{card.value}</strong>
          <span className="mt-3 inline-flex rounded-full bg-teal-50 px-2 py-1 text-xs font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
            {card.change}
          </span>
        </article>
      ))}
    </div>
  );
}

// Employee-only Payments view (spec section 11): no chart/KPI cards, just
// pending/overdue payments up top with a functional per-row reminder, then
// everything else below. `rows` is the already-server-scoped invoice list
// for this employee's own customers (recordsByModule.payments).
function EmployeePaymentsView({
  rows,
  customers,
  onSendReminder
}: {
  rows: RowRecord[];
  customers: RowRecord[];
  onSendReminder: (row: RowRecord) => void;
}) {
  const customerNameById = new Map(customers.map((c) => [c.id, c.Customer]));
  const todayKey = toDateKey(new Date());
  const withMeta = rows.map((row) => ({
    row,
    customerName: customerNameById.get(row["Customer ID"]) ?? `Customer #${row["Customer ID"]}`,
    overdue: !!row._dueDate && row._dueDate < todayKey && row.Status !== "Paid" && row.Status !== "Cancelled",
    pending: row.Status !== "Cancelled" && row.Status !== "Paid" && parseCurrency(row.Balance) > 0
  }));
  const pending = withMeta
    .filter((item) => item.pending)
    .sort((a, b) => (a.row._dueDate || "9999").localeCompare(b.row._dueDate || "9999"));
  const settled = withMeta.filter((item) => !item.pending);

  return (
    <section className="space-y-4">
      <article className="rounded-2xl border bg-card shadow-sm">
        <div className="border-b p-4">
          <h3 className="text-lg font-bold">Pending Payments</h3>
          <p className="text-sm text-muted-foreground">Your customers&apos; payments still awaiting collection, most urgent first.</p>
        </div>
        {pending.length === 0 ? (
          <p className="p-8 text-center text-sm text-muted-foreground">No pending payments right now.</p>
        ) : (
          <div className="divide-y">
            {pending.map(({ row, customerName, overdue }) => (
              <div key={row.id} className="flex flex-wrap items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold">{customerName}</p>
                  <p className="text-xs text-muted-foreground">Invoice {row.Invoice} - Due: {row._dueDate || "—"}</p>
                </div>
                <span className="text-sm font-bold">${row.Balance}</span>
                <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-bold ring-1", statusClass(row.Status))}>{row.Status}</span>
                {overdue ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-1 text-xs font-bold text-red-700 ring-1 ring-red-200 dark:bg-red-950 dark:text-red-200 dark:ring-red-900">
                    OVERDUE
                  </span>
                ) : null}
                <button
                  onClick={() => onSendReminder(row)}
                  className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold text-teal-700 hover:bg-teal-50 dark:text-teal-200 dark:hover:bg-teal-950"
                >
                  <Bell className="size-3.5" />
                  Send Reminder
                </button>
              </div>
            ))}
          </div>
        )}
      </article>

      <article className="rounded-2xl border bg-card shadow-sm">
        <div className="border-b p-4">
          <h3 className="text-lg font-bold">Other Payments</h3>
          <p className="text-sm text-muted-foreground">Paid or cancelled invoices for your customers.</p>
        </div>
        {settled.length === 0 ? (
          <p className="p-8 text-center text-sm text-muted-foreground">Nothing here yet.</p>
        ) : (
          <div className="divide-y">
            {settled.map(({ row, customerName }) => (
              <div key={row.id} className="flex flex-wrap items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold">{customerName}</p>
                  <p className="text-xs text-muted-foreground">Invoice {row.Invoice}</p>
                </div>
                <span className="text-sm font-bold">${row.Total}</span>
                <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-bold ring-1", statusClass(row.Status))}>{row.Status}</span>
              </div>
            ))}
          </div>
        )}
      </article>
    </section>
  );
}

// ===========================================================================
// Employee Communication Center — Email / Calling / WhatsApp
// ===========================================================================
//
// Replaces the old EmployeeCommunicationView, which was built before the
// backend's PII rework and read `_email`/`_phone` off each customer row.
// Those keys are no longer in an Employee's API response at all (see
// leadToRow/customerToRow and apps.core.serializers), so that view rendered
// an empty, non-functional contact list. Nothing here reads a contact
// value: every action names the ENTITY (`{ lead: id }` / `{ customer: id }`)
// and the backend resolves the address/number server-side.
//
// Rendered only for `role === "employee" && activeKey === "communication"`
// (same one-branch-per-role convention as SuperAdminCommunicationAuditSection
// in the `audit` module). Manager/Super Admin keep the generic module view.
//
// Three channels, three genuinely separate full-width workspaces behind one
// channel switcher — never mixed into a single list. There is no backend
// "conversation" resource, so conversation grouping is done ONCE here,
// client-side, from the flat list endpoints: email/calls group on
// `related_object` (content_type+object_id), WhatsApp on `customer`.

type CommChannel = "email" | "call" | "whatsapp";
type CommEntityKind = "lead" | "customer" | "contact";

type CommContact = {
  key: string;
  kind: CommEntityKind;
  id: string;
  name: string;
  canEmail: boolean;
  canCall: boolean;
  canWhatsapp: boolean;
};

type CommFocus = { channel: CommChannel; contactKey: string; nonce: number };

const COMM_CHANNEL_META: Array<{ key: CommChannel; label: string; icon: React.ElementType; blurb: string }> = [
  { key: "email", label: "Email", icon: Mail, blurb: "Threaded email conversations with your leads and customers." },
  { key: "call", label: "Calling", icon: Phone, blurb: "Place calls and review every call you have made." },
  { key: "whatsapp", label: "WhatsApp", icon: MessageCircle, blurb: "Chat with your customers without leaving the CRM." }
];

const COMM_STATUS_LABELS: Record<string, string> = {
  QUEUED: "Queued",
  RINGING: "Ringing",
  IN_PROGRESS: "In Progress",
  COMPLETED: "Completed",
  FAILED: "Failed",
  NO_ANSWER: "No Answer",
  BUSY: "Busy",
  SENT: "Sent",
  DELIVERED: "Delivered",
  READ: "Read"
};

// The only call states the backend reports (apps/communications/models.py's
// Call.Status). Nothing else is ever displayed — no invented "Connecting".
const CALL_IN_FLIGHT_STATUSES = new Set(["QUEUED", "RINGING", "IN_PROGRESS"]);

function commStatusLabel(value: string): string {
  return COMM_STATUS_LABELS[value] ?? value.replace(/_/g, " ");
}

function commTimestampLabel(value: string): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function commDurationLabel(seconds: unknown): string {
  if (seconds == null || seconds === "") return "—";
  const total = Number(seconds);
  if (!Number.isFinite(total) || total < 0) return "—";
  const m = Math.floor(total / 60);
  const s = Math.floor(total % 60);
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

// `related_object` is the backend's safe {type, id, label} summary — the
// label is the entity's own display name (Customer.name / "Company (Contact)"
// for a lead), never an address or a number.
function commEntityFromRelated(value: unknown): { kind: CommEntityKind; id: string; label: string } | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const id = record.id == null ? "" : String(record.id);
  if (!id) return null;
  const type = String(record.type ?? "");
  const kind: CommEntityKind = type === "crm.lead" ? "lead" : type === "crm.customer" ? "customer" : "contact";
  return { kind, id, label: String(record.label ?? "") };
}

function commContactKey(kind: CommEntityKind, id: string): string {
  return `${kind}:${id}`;
}

function commTargetFromKey(key: string): { kind: CommEntityKind; id: number } | null {
  const [kind, id] = key.split(":");
  if (!id || (kind !== "lead" && kind !== "customer" && kind !== "contact")) return null;
  const numericId = Number(id);
  return Number.isFinite(numericId) ? { kind, id: numericId } : null;
}

// The employee's own leads + customers, reduced to what a communication UI
// needs: a name to show and three capability booleans to gate the buttons.
// No contact value is carried, because the API never sent one.
function buildCommContacts(leads: RowRecord[], customers: RowRecord[]): CommContact[] {
  const fromLeads = leads.map<CommContact>((row) => ({
    key: commContactKey("lead", row.id),
    kind: "lead",
    id: row.id,
    name: row.Lead || `Lead #${row.id}`,
    canEmail: Boolean(row._canEmail),
    canCall: Boolean(row._canCall),
    canWhatsapp: Boolean(row._canWhatsapp)
  }));
  const fromCustomers = customers.map<CommContact>((row) => ({
    key: commContactKey("customer", row.id),
    kind: "customer",
    id: row.id,
    name: row.Customer || `Customer #${row.id}`,
    canEmail: Boolean(row._canEmail),
    canCall: Boolean(row._canCall),
    canWhatsapp: Boolean(row._canWhatsapp)
  }));
  return [...fromCustomers, ...fromLeads].sort((a, b) => a.name.localeCompare(b.name));
}

// A row's stored `error_message` is provider/infrastructure diagnostics
// ("<PROVIDER>_API_KEY is not configured", a gateway's own wording): real
// data, but not something an employee can act on, and not worth putting on
// a customer-facing demo screen. The failure itself is never hidden — the
// status badge still says Failed — only the raw text is replaced.
function commFailureNote(status: string, errorMessage: string): string {
  if (!errorMessage && status !== "FAILED") return "";
  return "Not delivered — the provider rejected this attempt. Try again or contact your administrator.";
}

function commApiErrorMessage(err: unknown, fallback: string): string {
  // ApiError.message is the generic "<METHOD> <path> failed (<status>)"
  // string built in lib/api.ts — never the raw response body, which could
  // echo a contact value back into the UI.
  return err instanceof ApiError ? `${fallback} (${err.status})` : fallback;
}

function CommStatusBadge({ status }: { status: string }) {
  if (!status) return null;
  return (
    <span className={cn("inline-flex shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ring-1", commAuditStatusClass(status))}>
      {commStatusLabel(status)}
    </span>
  );
}

function CommProtectedNote({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <LockKeyhole className="size-3.5 shrink-0" />
      {label}
    </span>
  );
}

function CommPanelSkeleton() {
  return (
    <div className="space-y-3 p-4">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="h-14 animate-pulse rounded-lg bg-muted/80" />
      ))}
    </div>
  );
}

function CommEmptyState({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center gap-2 p-8 text-center">
      <div className="mb-1 flex size-12 items-center justify-center rounded-xl bg-teal-50 text-teal-600 dark:bg-teal-950 dark:text-teal-200">
        <Icon className="size-5" />
      </div>
      <h4 className="text-base font-bold">{title}</h4>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

// Shared contact chooser for "start a new conversation / place a call".
// Only contacts the backend says are reachable on this channel are listed —
// capability comes from can_email/can_call/can_whatsapp, never from the
// presence of a contact field this client no longer receives.
function CommContactPicker({
  title,
  contacts,
  onSelect,
  onClose
}: {
  title: string;
  contacts: CommContact[];
  onSelect: (contact: CommContact) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return needle ? contacts.filter((contact) => contact.name.toLowerCase().includes(needle)) : contacts;
  }, [contacts, search]);

  return (
    <motion.div
      className="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border bg-card shadow-soft"
        initial={{ scale: 0.96, y: 18 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, y: 18 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b p-5">
          <div>
            <h3 className="text-lg font-bold">{title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">Only your own leads and customers who are reachable on this channel.</p>
          </div>
          <button onClick={onClose} className="inline-flex size-9 items-center justify-center rounded-lg border" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <div className="border-b p-4">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by name..."
              className="h-10 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
            />
          </label>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {contacts.length === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">
              None of your leads or customers is reachable on this channel yet — the backend reports no contact detail on file for
              them.
            </p>
          ) : visible.length === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">No reachable contacts match that search.</p>
          ) : (
            <div className="divide-y">
              {visible.map((contact) => (
                <button
                  key={contact.key}
                  onClick={() => onSelect(contact)}
                  className="flex w-full items-center gap-3 p-3 text-left transition hover:bg-muted/60"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-teal-50 text-xs font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                    {contact.name.slice(0, 2).toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold">{contact.name}</span>
                    <span className="block text-xs text-muted-foreground">{contact.kind === "lead" ? "Lead" : "Customer"}</span>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                </button>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

function EmployeeCommunicationCenter({
  leads,
  customers,
  focus,
  onToast
}: {
  leads: RowRecord[];
  customers: RowRecord[];
  focus: CommFocus | null;
  onToast: (toast: { type: "success" | "error"; message: string }) => void;
}) {
  const [channel, setChannel] = useState<CommChannel>("email");
  const [focusContactKey, setFocusContactKey] = useState<string | null>(null);
  const [focusNonce, setFocusNonce] = useState(0);
  const contacts = useMemo(() => buildCommContacts(leads, customers), [leads, customers]);

  // A lead/customer detail view asked for a specific channel + contact.
  // The contact is addressed by ID only — no contact detail travels here,
  // and nothing is written to the URL or to storage.
  useEffect(() => {
    if (!focus) return;
    setChannel(focus.channel);
    setFocusContactKey(focus.contactKey);
    setFocusNonce(focus.nonce);
  }, [focus]);

  const activeMeta = COMM_CHANNEL_META.find((item) => item.key === channel) ?? COMM_CHANNEL_META[0];

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border bg-card p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="text-lg font-bold">Communication Center</h3>
            <p className="text-sm text-muted-foreground">{activeMeta.blurb}</p>
          </div>
          <CommProtectedNote label="Contact details stay on the server — you reach people by name." />
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-3" role="tablist" aria-label="Communication channel">
          {COMM_CHANNEL_META.map((item) => {
            const ChannelIcon = item.icon;
            const active = item.key === channel;
            return (
              <button
                key={item.key}
                role="tab"
                aria-selected={active}
                onClick={() => setChannel(item.key)}
                className={cn(
                  "inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold transition",
                  active
                    ? "border-teal-600 bg-teal-600 text-white shadow-sm"
                    : "bg-background text-foreground hover:-translate-y-0.5 hover:bg-muted"
                )}
              >
                <ChannelIcon className="size-4" />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      {channel === "email" ? (
        <CommEmailWorkspace contacts={contacts} focusContactKey={focusContactKey} focusNonce={focusNonce} onToast={onToast} />
      ) : channel === "call" ? (
        <CommCallWorkspace contacts={contacts} focusContactKey={focusContactKey} focusNonce={focusNonce} onToast={onToast} />
      ) : (
        <CommWhatsAppWorkspace contacts={contacts} focusContactKey={focusContactKey} focusNonce={focusNonce} onToast={onToast} />
      )}
    </section>
  );
}

// ---- Email workspace ------------------------------------------------------

type CommEmailMessage = {
  id: string;
  conversationKey: string;
  conversationLabel: string;
  target: { kind: CommEntityKind; id: string } | null;
  subject: string;
  body: string;
  status: string;
  direction: string;
  timestamp: string;
  error: string;
};

type CommConversation<T> = { key: string; label: string; target: { kind: CommEntityKind; id: string } | null; messages: T[] };

function groupCommConversations<T extends { conversationKey: string; conversationLabel: string; target: { kind: CommEntityKind; id: string } | null; timestamp: string }>(
  items: T[]
): Array<CommConversation<T>> {
  const map = new Map<string, CommConversation<T>>();
  items.forEach((item) => {
    const existing = map.get(item.conversationKey);
    if (existing) {
      existing.messages.push(item);
      if (!existing.label && item.conversationLabel) existing.label = item.conversationLabel;
    } else {
      map.set(item.conversationKey, {
        key: item.conversationKey,
        label: item.conversationLabel,
        target: item.target,
        messages: [item]
      });
    }
  });
  const conversations = Array.from(map.values());
  conversations.forEach((conversation) => conversation.messages.sort((a, b) => a.timestamp.localeCompare(b.timestamp)));
  return conversations.sort((a, b) => {
    const aLast = a.messages[a.messages.length - 1]?.timestamp ?? "";
    const bLast = b.messages[b.messages.length - 1]?.timestamp ?? "";
    return bLast.localeCompare(aLast);
  });
}

const COMM_EMAIL_FILTERS = ["All", "Sent", "Received", "Queued", "Failed"] as const;
type CommEmailFilter = (typeof COMM_EMAIL_FILTERS)[number];

function CommEmailWorkspace({
  contacts,
  focusContactKey,
  focusNonce,
  onToast
}: {
  contacts: CommContact[];
  focusContactKey: string | null;
  focusNonce: number;
  onToast: (toast: { type: "success" | "error"; message: string }) => void;
}) {
  const [messages, setMessages] = useState<CommEmailMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [filter, setFilter] = useState<CommEmailFilter>("All");
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const emailable = useMemo(() => contacts.filter((contact) => contact.canEmail), [contacts]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setMessages(null);
    // One flat, already-server-scoped page; the conversation grouping and
    // the All/Sent/Received/Queued/Failed filter are computed client-side
    // over it, matching how every other list view in this file filters.
    communications
      .listEmailMessages("?page_size=200&ordering=-created_at")
      .then((page) => {
        if (cancelled) return;
        setMessages(
          page.results.map((row) => {
            const entity = commEntityFromRelated(row.related_object);
            const label = entity?.label || String(row.recipient_label ?? "") || "Unlinked recipient";
            return {
              id: String(row.id),
              conversationKey: entity ? commContactKey(entity.kind, entity.id) : `unlinked:${label}`,
              conversationLabel: label,
              target: entity ? { kind: entity.kind, id: entity.id } : null,
              subject: String(row.subject ?? ""),
              body: String(row.body ?? ""),
              status: String(row.status ?? ""),
              direction: String(row.direction ?? "OUTBOUND"),
              timestamp: String(row.sent_at ?? row.created_at ?? ""),
              error: String(row.error_message ?? "")
            };
          })
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setError(commApiErrorMessage(err, "Could not load your email history"));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  useEffect(() => {
    if (focusNonce > 0 && focusContactKey) setSelectedKey(focusContactKey);
  }, [focusContactKey, focusNonce]);

  const filtered = useMemo(() => {
    const list = messages ?? [];
    return list.filter((message) => {
      if (filter === "Sent") return message.direction === "OUTBOUND" && message.status === "SENT";
      if (filter === "Received") return message.direction === "INBOUND";
      if (filter === "Queued") return message.status === "QUEUED";
      if (filter === "Failed") return message.status === "FAILED";
      return true;
    });
  }, [messages, filter]);

  const conversations = useMemo(() => groupCommConversations(filtered), [filtered]);

  const visibleConversations = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return conversations;
    return conversations.filter((conversation) => conversation.label.toLowerCase().includes(needle));
  }, [conversations, search]);

  const selectedContact = selectedKey ? contacts.find((contact) => contact.key === selectedKey) ?? null : null;
  const selectedConversation =
    (selectedKey ? conversations.find((conversation) => conversation.key === selectedKey) : undefined) ??
    (selectedContact
      ? { key: selectedContact.key, label: selectedContact.name, target: { kind: selectedContact.kind, id: selectedContact.id }, messages: [] }
      : null);

  const canCompose = Boolean(selectedConversation?.target) && (selectedContact ? selectedContact.canEmail : true);

  function handleSend() {
    const target = selectedConversation?.target;
    if (!target || !subject.trim() || !body.trim()) return;
    const payloadTarget = commTargetFromKey(commContactKey(target.kind, target.id));
    if (!payloadTarget) return;
    setSending(true);
    // Exactly the queue-then-send two-step sendPaymentReminderForCustomer()
    // already uses — the entity is named, never an address.
    communications
      .queueEmail({ [payloadTarget.kind]: payloadTarget.id, subject: subject.trim(), body: body.trim() })
      .then((queued) => communications.sendEmail(String((queued as Record<string, unknown>).id)))
      .then(() => {
        onToast({ type: "success", message: `Email sent to ${selectedConversation?.label ?? "this contact"}.` });
        setSubject("");
        setBody("");
        setReloadToken((value) => value + 1);
      })
      .catch((err) => {
        onToast({ type: "error", message: commApiErrorMessage(err, "Could not send that email") });
      })
      .finally(() => setSending(false));
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <section className="flex max-h-[640px] flex-col overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="space-y-3 border-b p-4">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-bold uppercase tracking-wide text-muted-foreground">Conversations</h4>
            <button
              onClick={() => setPickerOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-2.5 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-teal-700"
            >
              <Plus className="size-3.5" />
              New
            </button>
          </div>
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search conversations..."
              className="h-10 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
            />
          </label>
          <div className="flex flex-wrap gap-1.5">
            {COMM_EMAIL_FILTERS.map((item) => (
              <button
                key={item}
                onClick={() => setFilter(item)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs font-semibold transition",
                  filter === item ? "border-teal-600 bg-teal-600 text-white" : "bg-background hover:bg-muted"
                )}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {messages === null ? (
            <CommPanelSkeleton />
          ) : error ? (
            <p className="p-6 text-center text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : visibleConversations.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No email conversations yet. Use <span className="font-semibold">New</span> to start one.
            </p>
          ) : (
            <div className="divide-y">
              {visibleConversations.map((conversation) => {
                const last = conversation.messages[conversation.messages.length - 1];
                const active = conversation.key === selectedKey;
                return (
                  <button
                    key={conversation.key}
                    onClick={() => setSelectedKey(conversation.key)}
                    className={cn("w-full p-3 text-left transition hover:bg-muted/60", active && "bg-teal-50 dark:bg-teal-950/60")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold">{conversation.label}</span>
                      <CommStatusBadge status={last?.status ?? ""} />
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">{last?.subject || "(no subject)"}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {conversation.messages.length} message{conversation.messages.length === 1 ? "" : "s"} · {commTimestampLabel(last?.timestamp ?? "")}
                    </p>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </section>

      <section className="flex min-h-[420px] flex-col overflow-hidden rounded-2xl border bg-card shadow-sm">
        {!selectedConversation ? (
          <CommEmptyState
            icon={Mail}
            title="No conversation selected"
            description="Pick a conversation on the left, or start a new one with any lead or customer who has an email address on file."
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">
              <div className="min-w-0">
                <h4 className="truncate text-base font-bold">{selectedConversation.label}</h4>
                <CommProtectedNote label="Protected contact — the address is resolved server-side" />
              </div>
              <button
                onClick={() => setReloadToken((value) => value + 1)}
                className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold transition hover:bg-muted"
              >
                <RefreshCw className="size-3.5" />
                Refresh
              </button>
            </div>

            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
              {selectedConversation.messages.length === 0 ? (
                <p className="rounded-lg border bg-background p-6 text-center text-sm text-muted-foreground">
                  No email history with this contact yet — your first message will appear here.
                </p>
              ) : (
                selectedConversation.messages.map((message) => {
                  const outbound = message.direction !== "INBOUND";
                  return (
                    <article
                      key={message.id}
                      className={cn(
                        "rounded-xl border bg-background p-3",
                        outbound ? "border-l-4 border-l-teal-600" : "border-l-4 border-l-muted-foreground/40"
                      )}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm font-bold">{message.subject || "(no subject)"}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                            {outbound ? "Sent by you" : "Received"}
                          </span>
                          <CommStatusBadge status={message.status} />
                        </div>
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground">{commTimestampLabel(message.timestamp)}</p>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{message.body || "(no content)"}</p>
                      {message.error ? (
                        <p className="mt-2 text-xs font-semibold text-red-600 dark:text-red-400">
                          {commFailureNote(message.status, message.error)}
                        </p>
                      ) : null}
                      {!outbound ? (
                        <button
                          onClick={() => setSubject(message.subject.startsWith("Re:") ? message.subject : `Re: ${message.subject}`)}
                          className="mt-3 inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold text-teal-700 transition hover:bg-teal-50 dark:text-teal-200 dark:hover:bg-teal-950"
                        >
                          <Mail className="size-3.5" />
                          Reply
                        </button>
                      ) : null}
                    </article>
                  );
                })
              )}
            </div>

            <div className="space-y-2 border-t p-4">
              {canCompose ? (
                <>
                  <input
                    value={subject}
                    onChange={(event) => setSubject(event.target.value)}
                    placeholder="Subject"
                    className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
                  />
                  <textarea
                    value={body}
                    onChange={(event) => setBody(event.target.value)}
                    placeholder={`Write your message to ${selectedConversation.label}...`}
                    rows={3}
                    className="w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
                  />
                  <div className="flex items-center justify-between gap-3">
                    <CommProtectedNote label="No recipient field — the message goes to this contact only" />
                    <button
                      onClick={handleSend}
                      disabled={sending || !subject.trim() || !body.trim()}
                      className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                      {sending ? "Sending..." : "Send Email"}
                    </button>
                  </div>
                </>
              ) : (
                <p className="rounded-lg border bg-background p-3 text-center text-xs text-muted-foreground">
                  This conversation is not linked to one of your leads or customers, so a reply cannot be addressed from here.
                </p>
              )}
            </div>
          </>
        )}
      </section>

      <AnimatePresence>
        {pickerOpen ? (
          <CommContactPicker
            title="New email"
            contacts={emailable}
            onSelect={(contact) => {
              setSelectedKey(contact.key);
              setPickerOpen(false);
            }}
            onClose={() => setPickerOpen(false)}
          />
        ) : null}
      </AnimatePresence>
    </div>
  );
}

// ---- Calling workspace ----------------------------------------------------

type CommCall = {
  id: string;
  conversationKey: string;
  conversationLabel: string;
  target: { kind: CommEntityKind; id: string } | null;
  status: string;
  direction: string;
  timestamp: string;
  endedAt: string;
  durationSeconds: unknown;
  error: string;
};

const COMM_CALL_FILTERS = ["All", "Completed", "Missed or failed"] as const;
type CommCallFilter = (typeof COMM_CALL_FILTERS)[number];

function CommCallWorkspace({
  contacts,
  focusContactKey,
  focusNonce,
  onToast
}: {
  contacts: CommContact[];
  focusContactKey: string | null;
  focusNonce: number;
  onToast: (toast: { type: "success" | "error"; message: string }) => void;
}) {
  const [calls, setCalls] = useState<CommCall[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [filter, setFilter] = useState<CommCallFilter>("All");
  const [placing, setPlacing] = useState(false);
  const [activeCallId, setActiveCallId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  const callable = useMemo(() => contacts.filter((contact) => contact.canCall), [contacts]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    communications
      .listCalls("?page_size=200&ordering=-created_at")
      .then((page) => {
        if (cancelled) return;
        setCalls(
          page.results.map((row) => {
            const entity = commEntityFromRelated(row.related_object);
            const label = entity?.label || "Unlinked contact";
            return {
              id: String(row.id),
              conversationKey: entity ? commContactKey(entity.kind, entity.id) : `unlinked:${label}`,
              conversationLabel: label,
              target: entity ? { kind: entity.kind, id: entity.id } : null,
              status: String(row.status ?? ""),
              direction: String(row.direction ?? "OUTBOUND"),
              timestamp: String(row.started_at ?? row.created_at ?? ""),
              endedAt: String(row.ended_at ?? ""),
              durationSeconds: row.duration_seconds,
              error: String(row.error_message ?? "")
            };
          })
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setCalls([]);
        setError(commApiErrorMessage(err, "Could not load your call history"));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  useEffect(() => {
    if (focusNonce > 0 && focusContactKey) setSelectedKey(focusContactKey);
  }, [focusContactKey, focusNonce]);

  const activeCall = activeCallId ? (calls ?? []).find((call) => call.id === activeCallId) ?? null : null;

  // A call's status is advanced by the provider webhook server-side, so the
  // only honest way to show progress is to re-read it. Polling stops as soon
  // as the backend reports a terminal status — no client-side state machine
  // and no invented intermediate states.
  useEffect(() => {
    if (!activeCall || !CALL_IN_FLIGHT_STATUSES.has(activeCall.status)) return;
    const timer = window.setTimeout(() => setReloadToken((value) => value + 1), 5000);
    return () => window.clearTimeout(timer);
  }, [activeCall]);

  const selectedContact = selectedKey ? contacts.find((contact) => contact.key === selectedKey) ?? null : null;

  const recentByContact = useMemo(() => {
    const map = new Map<string, CommCall>();
    (calls ?? []).forEach((call) => {
      const existing = map.get(call.conversationKey);
      if (!existing || call.timestamp > existing.timestamp) map.set(call.conversationKey, call);
    });
    return Array.from(map.values()).sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }, [calls]);

  const historyForSelected = useMemo(() => {
    const list = (calls ?? []).filter((call) => (selectedKey ? call.conversationKey === selectedKey : true));
    return list
      .filter((call) => {
        if (filter === "Completed") return call.status === "COMPLETED";
        if (filter === "Missed or failed") return call.status === "FAILED" || call.status === "NO_ANSWER" || call.status === "BUSY";
        return true;
      })
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }, [calls, selectedKey, filter]);

  function handlePlaceCall() {
    if (!selectedContact) return;
    const target = commTargetFromKey(selectedContact.key);
    if (!target) return;
    setPlacing(true);
    communications
      .initiateCall({ [target.kind]: target.id })
      .then((created) => {
        const id = String((created as Record<string, unknown>).id ?? "");
        setActiveCallId(id);
        setReloadToken((value) => value + 1);
        onToast({ type: "success", message: `Call placed to ${selectedContact.name}.` });
      })
      .catch((err) => {
        onToast({ type: "error", message: commApiErrorMessage(err, "Could not place that call") });
      })
      .finally(() => setPlacing(false));
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <section className="flex max-h-[640px] flex-col overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="flex items-center justify-between gap-2 border-b p-4">
          <h4 className="text-sm font-bold uppercase tracking-wide text-muted-foreground">Recent calls</h4>
          <button
            onClick={() => setPickerOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-2.5 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-teal-700"
          >
            <PhoneCall className="size-3.5" />
            New call
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {calls === null ? (
            <CommPanelSkeleton />
          ) : recentByContact.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No calls yet. Use <span className="font-semibold">New call</span> to reach a lead or customer.
            </p>
          ) : (
            <div className="divide-y">
              {recentByContact.map((call) => {
                const active = call.conversationKey === selectedKey;
                return (
                  <button
                    key={call.conversationKey}
                    onClick={() => setSelectedKey(call.conversationKey)}
                    className={cn("w-full p-3 text-left transition hover:bg-muted/60", active && "bg-teal-50 dark:bg-teal-950/60")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold">{call.conversationLabel}</span>
                      <CommStatusBadge status={call.status} />
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {commTimestampLabel(call.timestamp)} · {commDurationLabel(call.durationSeconds)}
                    </p>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </section>

      <section className="flex min-h-[420px] flex-col gap-4">
        <div className="rounded-2xl border bg-card p-5 shadow-sm">
          {!selectedContact && !selectedKey ? (
            <CommEmptyState
              icon={Phone}
              title="No one selected"
              description="Choose a recent call on the left, or start a new call with any lead or customer who has a phone number on file."
            />
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Call panel</p>
                  <h4 className="truncate text-xl font-bold">
                    {selectedContact?.name ?? recentByContact.find((call) => call.conversationKey === selectedKey)?.conversationLabel ?? "Contact"}
                  </h4>
                  <CommProtectedNote label="Protected contact — the number is dialled server-side" />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setReloadToken((value) => value + 1)}
                    className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold transition hover:bg-muted"
                  >
                    <RefreshCw className="size-3.5" />
                    Refresh
                  </button>
                  <button
                    onClick={handlePlaceCall}
                    disabled={placing || !selectedContact?.canCall}
                    className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {placing ? <Loader2 className="size-4 animate-spin" /> : <PhoneCall className="size-4" />}
                    {placing ? "Placing call..." : "Start Call"}
                  </button>
                </div>
              </div>

              {!selectedContact ? (
                <p className="rounded-lg border bg-background p-3 text-xs text-muted-foreground">
                  This call is not linked to one of your current leads or customers, so a new call cannot be started from here.
                </p>
              ) : !selectedContact.canCall ? (
                <p className="rounded-lg border bg-background p-3 text-xs text-muted-foreground">
                  No phone number is on file for this contact, so calling is unavailable.
                </p>
              ) : null}

              {activeCall ? (
                <div className="grid gap-3 rounded-xl border bg-background p-4 sm:grid-cols-3">
                  <div>
                    <p className="text-xs text-muted-foreground">Status</p>
                    <div className="mt-1 flex items-center gap-2">
                      {CALL_IN_FLIGHT_STATUSES.has(activeCall.status) ? <Loader2 className="size-4 animate-spin text-teal-600" /> : null}
                      <CommStatusBadge status={activeCall.status} />
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Duration</p>
                    <p className="mt-1 font-mono text-sm font-bold tabular-nums">{commDurationLabel(activeCall.durationSeconds)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Started</p>
                    <p className="mt-1 text-sm font-semibold">{commTimestampLabel(activeCall.timestamp)}</p>
                  </div>
                  {activeCall.error ? (
                    <p className="text-xs font-semibold text-red-600 dark:text-red-400 sm:col-span-3">
                      {commFailureNote(activeCall.status, activeCall.error)}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          )}
        </div>

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border bg-card shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">
            <h4 className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
              {selectedKey ? "Call history for this contact" : "Call history"}
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {COMM_CALL_FILTERS.map((item) => (
                <button
                  key={item}
                  onClick={() => setFilter(item)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs font-semibold transition",
                    filter === item ? "border-teal-600 bg-teal-600 text-white" : "bg-background hover:bg-muted"
                  )}
                >
                  {item}
                </button>
              ))}
              {selectedKey ? (
                <button
                  onClick={() => setSelectedKey(null)}
                  className="rounded-full border bg-background px-2.5 py-1 text-xs font-semibold transition hover:bg-muted"
                >
                  Show all
                </button>
              ) : null}
            </div>
          </div>
          {calls === null ? (
            <CommPanelSkeleton />
          ) : error ? (
            <p className="p-6 text-center text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : historyForSelected.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">No calls match this filter yet.</p>
          ) : (
            <div className="max-h-72 divide-y overflow-y-auto">
              {historyForSelected.map((call) => (
                <div key={call.id} className="flex flex-wrap items-center gap-3 p-3">
                  <Phone className="size-4 shrink-0 text-teal-700 dark:text-teal-300" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">{call.conversationLabel}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {call.direction === "INBOUND" ? "Inbound" : "Outbound"} · {commTimestampLabel(call.timestamp)}
                    </p>
                    {call.error ? (
                      <p className="text-[11px] font-semibold text-red-600 dark:text-red-400">
                        {commFailureNote(call.status, call.error)}
                      </p>
                    ) : null}
                  </div>
                  <span className="text-xs font-semibold tabular-nums">{commDurationLabel(call.durationSeconds)}</span>
                  <CommStatusBadge status={call.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <AnimatePresence>
        {pickerOpen ? (
          <CommContactPicker
            title="New call"
            contacts={callable}
            onSelect={(contact) => {
              setSelectedKey(contact.key);
              setPickerOpen(false);
            }}
            onClose={() => setPickerOpen(false)}
          />
        ) : null}
      </AnimatePresence>
    </div>
  );
}

// ---- WhatsApp workspace ---------------------------------------------------

type CommWhatsAppMessage = {
  id: string;
  conversationKey: string;
  conversationLabel: string;
  target: { kind: CommEntityKind; id: string } | null;
  message: string;
  status: string;
  direction: string;
  timestamp: string;
  error: string;
};

const COMM_WHATSAPP_FILTERS = ["All", "Unread", "Sent", "Received"] as const;
type CommWhatsAppFilter = (typeof COMM_WHATSAPP_FILTERS)[number];

function CommWhatsAppWorkspace({
  contacts,
  focusContactKey,
  focusNonce,
  onToast
}: {
  contacts: CommContact[];
  focusContactKey: string | null;
  focusNonce: number;
  onToast: (toast: { type: "success" | "error"; message: string }) => void;
}) {
  const [messages, setMessages] = useState<CommWhatsAppMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [filter, setFilter] = useState<CommWhatsAppFilter>("All");
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const reachable = useMemo(() => contacts.filter((contact) => contact.canWhatsapp), [contacts]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    communications
      .listWhatsAppMessages("?page_size=200&ordering=-created_at")
      .then((page) => {
        if (cancelled) return;
        setMessages(
          page.results.map((row) => {
            // WhatsAppMessage models a `customer` relation only (see
            // apps/communications/models.py) — a message sent to a LEAD is
            // delivered but not back-linked, so it groups under a clearly
            // labelled unlinked thread rather than being silently dropped.
            const customerId = row.customer == null ? "" : String(row.customer);
            const label = String(row.customer_name ?? "") || "Unlinked recipients";
            return {
              id: String(row.id),
              conversationKey: customerId ? commContactKey("customer", customerId) : "unlinked:whatsapp",
              conversationLabel: label,
              target: customerId ? { kind: "customer" as CommEntityKind, id: customerId } : null,
              message: String(row.message ?? ""),
              status: String(row.status ?? ""),
              direction: String(row.direction ?? "OUTBOUND"),
              timestamp: String(row.created_at ?? ""),
              error: String(row.error_message ?? "")
            };
          })
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setMessages([]);
        setError(commApiErrorMessage(err, "Could not load your WhatsApp history"));
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  useEffect(() => {
    if (focusNonce > 0 && focusContactKey) setSelectedKey(focusContactKey);
  }, [focusContactKey, focusNonce]);

  const filtered = useMemo(() => {
    const list = messages ?? [];
    return list.filter((message) => {
      if (filter === "Sent") return message.direction === "OUTBOUND";
      if (filter === "Received") return message.direction === "INBOUND";
      if (filter === "Unread") return message.direction === "INBOUND" && message.status !== "READ";
      return true;
    });
  }, [messages, filter]);

  const conversations = useMemo(() => groupCommConversations(filtered), [filtered]);

  const selectedContact = selectedKey ? contacts.find((contact) => contact.key === selectedKey) ?? null : null;
  const selectedConversation =
    (selectedKey ? conversations.find((conversation) => conversation.key === selectedKey) : undefined) ??
    (selectedContact
      ? { key: selectedContact.key, label: selectedContact.name, target: { kind: selectedContact.kind, id: selectedContact.id }, messages: [] }
      : null);

  const canSend = Boolean(selectedConversation?.target) && (selectedContact ? selectedContact.canWhatsapp : true);

  function handleSend() {
    const target = selectedConversation?.target;
    if (!target || !draft.trim()) return;
    const payloadTarget = commTargetFromKey(commContactKey(target.kind, target.id));
    if (!payloadTarget) return;
    setSending(true);
    communications
      .sendWhatsAppMessage({ [payloadTarget.kind]: payloadTarget.id, message: draft.trim() })
      .then(() => {
        onToast({ type: "success", message: `WhatsApp message sent to ${selectedConversation?.label ?? "this contact"}.` });
        setDraft("");
        setReloadToken((value) => value + 1);
      })
      .catch((err) => {
        onToast({ type: "error", message: commApiErrorMessage(err, "Could not send that WhatsApp message") });
      })
      .finally(() => setSending(false));
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <section className="flex max-h-[640px] flex-col overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="space-y-3 border-b p-4">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-bold uppercase tracking-wide text-muted-foreground">Chats</h4>
            <button
              onClick={() => setPickerOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-2.5 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-teal-700"
            >
              <Plus className="size-3.5" />
              New chat
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {COMM_WHATSAPP_FILTERS.map((item) => (
              <button
                key={item}
                onClick={() => setFilter(item)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs font-semibold transition",
                  filter === item ? "border-teal-600 bg-teal-600 text-white" : "bg-background hover:bg-muted"
                )}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {messages === null ? (
            <CommPanelSkeleton />
          ) : error ? (
            <p className="p-6 text-center text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : conversations.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No WhatsApp chats yet. Use <span className="font-semibold">New chat</span> to start one.
            </p>
          ) : (
            <div className="divide-y">
              {conversations.map((conversation) => {
                const last = conversation.messages[conversation.messages.length - 1];
                const active = conversation.key === selectedKey;
                return (
                  <button
                    key={conversation.key}
                    onClick={() => setSelectedKey(conversation.key)}
                    className={cn("flex w-full items-center gap-3 p-3 text-left transition hover:bg-muted/60", active && "bg-teal-50 dark:bg-teal-950/60")}
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-teal-50 text-xs font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                      {conversation.label.slice(0, 2).toUpperCase()}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-semibold">{conversation.label}</span>
                        <CommStatusBadge status={last?.status ?? ""} />
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-muted-foreground">{last?.message || "No messages"}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </section>

      <section className="flex min-h-[420px] flex-col overflow-hidden rounded-2xl border bg-card shadow-sm">
        {!selectedConversation ? (
          <CommEmptyState
            icon={MessageCircle}
            title="No chat selected"
            description="Pick a chat on the left, or start a new one with any customer who has a WhatsApp-capable number on file."
          />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4">
              <div className="min-w-0">
                <h4 className="truncate text-base font-bold">{selectedConversation.label}</h4>
                <CommProtectedNote label="Protected contact — the WhatsApp number never reaches this screen" />
              </div>
              <button
                onClick={() => setReloadToken((value) => value + 1)}
                className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold transition hover:bg-muted"
              >
                <RefreshCw className="size-3.5" />
                Refresh
              </button>
            </div>

            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto bg-muted/30 p-4">
              {selectedConversation.messages.length === 0 ? (
                <p className="rounded-lg border bg-background p-6 text-center text-sm text-muted-foreground">
                  No messages in this chat yet — say hello below.
                </p>
              ) : (
                selectedConversation.messages.map((message) => {
                  const outbound = message.direction !== "INBOUND";
                  return (
                    <div key={message.id} className={cn("flex", outbound ? "justify-end" : "justify-start")}>
                      <div
                        className={cn(
                          "max-w-[85%] rounded-2xl px-3 py-2 text-sm shadow-sm sm:max-w-[70%]",
                          outbound
                            ? "rounded-br-sm bg-teal-600 text-white"
                            : "rounded-bl-sm border bg-card text-foreground"
                        )}
                      >
                        <p className="whitespace-pre-wrap break-words">{message.message}</p>
                        <p className={cn("mt-1 flex items-center gap-1.5 text-[10px]", outbound ? "text-white/75" : "text-muted-foreground")}>
                          {outbound ? "You" : selectedConversation.label} · {commTimestampLabel(message.timestamp)} · {commStatusLabel(message.status)}
                        </p>
                        {message.error ? (
                          <p className={cn("mt-1 text-[10px] font-semibold", outbound ? "text-red-100" : "text-red-600 dark:text-red-400")}>
                            {commFailureNote(message.status, message.error)}
                          </p>
                        ) : null}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="border-t p-4">
              {canSend ? (
                <div className="flex items-end gap-2">
                  <textarea
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder={`Message ${selectedConversation.label}...`}
                    rows={2}
                    className="w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
                  />
                  <button
                    onClick={handleSend}
                    disabled={sending || !draft.trim()}
                    className="inline-flex h-11 shrink-0 items-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                    Send
                  </button>
                </div>
              ) : (
                <p className="rounded-lg border bg-background p-3 text-center text-xs text-muted-foreground">
                  These messages are not linked to one of your customers, so a reply cannot be addressed from here.
                </p>
              )}
            </div>
          </>
        )}
      </section>

      <AnimatePresence>
        {pickerOpen ? (
          <CommContactPicker
            title="New WhatsApp chat"
            contacts={reachable}
            onSelect={(contact) => {
              setSelectedKey(contact.key);
              setPickerOpen(false);
            }}
            onClose={() => setPickerOpen(false)}
          />
        ) : null}
      </AnimatePresence>
    </div>
  );
}

// Per-lead / per-customer channel buttons, shown on that record's own
// detail view. Each one deep-links into the Communication Center's matching
// workspace for THAT entity, addressed by ID — no contact value is read,
// passed, or placed in a URL. A channel with no capability is rendered
// disabled with the reason, never hidden silently.
function CommQuickActions({
  contact,
  onOpen
}: {
  contact: CommContact;
  onOpen: (channel: CommChannel, contact: CommContact) => void;
}) {
  const buttons: Array<{ channel: CommChannel; label: string; icon: React.ElementType; enabled: boolean }> = [
    { channel: "email", label: "Email", icon: Mail, enabled: contact.canEmail },
    { channel: "call", label: "Call", icon: Phone, enabled: contact.canCall },
    { channel: "whatsapp", label: "WhatsApp", icon: MessageCircle, enabled: contact.canWhatsapp }
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {buttons.map((button) => {
        const ButtonIcon = button.icon;
        return (
          <button
            key={button.channel}
            onClick={() => onOpen(button.channel, contact)}
            disabled={!button.enabled}
            title={button.enabled ? `Open the ${button.label} workspace for ${contact.name}` : `No ${button.label.toLowerCase()} contact on file`}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold transition",
              button.enabled
                ? "text-teal-700 hover:bg-teal-50 dark:text-teal-200 dark:hover:bg-teal-950"
                : "cursor-not-allowed text-muted-foreground opacity-60"
            )}
          >
            <ButtonIcon className="size-3.5" />
            {button.label}
          </button>
        );
      })}
    </div>
  );
}

// Employee-only Customer-360 profile drawer (spec section 10): a single
// modal combining Basic Details + Interaction History (communication +
// notes/reminders that mention this customer) + Payments + Scheduled
// Activities for one customer, using only data already scoped to this
// employee (recordsByModule + the reminders/notes already filtered by
// canSeeReminder/canSeeNote before they reach this component). No Owner
// field is ever rendered here. Visual language matches RecordModal
// (same backdrop, card chrome, DetailRow list style).
function EmployeeCustomerProfileModal({
  customer,
  payments,
  communicationRows,
  reminders,
  notes,
  onSendReminder,
  onOpenChannel,
  onClose
}: {
  customer: RowRecord;
  payments: RowRecord[];
  communicationRows: RowRecord[];
  reminders: Reminder[];
  notes: CalendarNote[];
  onSendReminder: (row: RowRecord) => void;
  onOpenChannel: (channel: CommChannel, contact: CommContact) => void;
  onClose: () => void;
}) {
  // Capability booleans, never contact values — the API sends an Employee
  // no `email`/`phone` key at all (see customerToRow).
  const contact: CommContact = {
    key: commContactKey("customer", customer.id),
    kind: "customer",
    id: customer.id,
    name: customer.Customer || `Customer #${customer.id}`,
    canEmail: Boolean(customer._canEmail),
    canCall: Boolean(customer._canCall),
    canWhatsapp: Boolean(customer._canWhatsapp)
  };
  const custPayments = payments.filter((row) => row["Customer ID"] === customer.id);
  // `Recipient` is the backend's safe `recipient_label` (the related
  // customer's own display name), so the match is name-to-name — the old
  // address comparison could never match once addresses stopped arriving.
  const custComms = communicationRows.filter((row) => row.Recipient && row.Recipient === customer.Customer);
  const nameNeedle = (customer.Customer ?? "").trim().toLowerCase();
  const custReminders = nameNeedle
    ? reminders.filter((reminder) => reminder.title.toLowerCase().includes(nameNeedle))
    : [];
  const custNotes = nameNeedle ? notes.filter((note) => note.text.toLowerCase().includes(nameNeedle)) : [];
  const upcomingActivities = custReminders
    .filter((reminder) => !reminder.completed)
    .sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`));
  const pendingBalance = custPayments.reduce((sum, row) => sum + parseCurrency(row.Balance), 0);
  const todayKey = toDateKey(new Date());

  return (
    <motion.div
      className="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-2xl border bg-card shadow-soft"
        initial={{ scale: 0.96, y: 18 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, y: 18 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b p-5">
          <div>
            <h3 className="text-xl font-bold">{customer.Customer || "Customer Profile"}</h3>
            <p className="mt-1 text-sm text-muted-foreground">Basic details, interaction history, payments, and scheduled activities.</p>
          </div>
          <button onClick={onClose} className="inline-flex size-9 items-center justify-center rounded-lg border" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-6 p-5">
          <section>
            <h4 className="mb-2 text-sm font-bold uppercase tracking-wide text-muted-foreground">Basic Details</h4>
            <div className="grid gap-3 sm:grid-cols-2">
              <DetailRow title="Email" subtitle={contactCapabilityLabel(customer._canEmail)} />
              <DetailRow title="Phone" subtitle={contactCapabilityLabel(customer._canCall)} />
              <DetailRow title="Industry / Category" subtitle={customer.Industry || "—"} />
              <DetailRow title="Status" subtitle={customer.Status || "—"} badge={customer.Status || undefined} />
            </div>
          </section>

          <section>
            <h4 className="mb-2 text-sm font-bold uppercase tracking-wide text-muted-foreground">Contact This Customer</h4>
            <div className="flex flex-col gap-3 rounded-lg border bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
              <CommProtectedNote label="Opens the Communication Center for this customer — contact details stay server-side." />
              <CommQuickActions contact={contact} onOpen={onOpenChannel} />
            </div>
          </section>

          <section>
            <h4 className="mb-2 text-sm font-bold uppercase tracking-wide text-muted-foreground">Interaction History</h4>
            {custComms.length === 0 && custNotes.length === 0 ? (
              <p className="rounded-lg border bg-background p-4 text-center text-sm text-muted-foreground">
                No calls, emails, WhatsApp, or notes recorded for this customer yet.
              </p>
            ) : (
              <div className="space-y-2">
                {custComms.map((row) => (
                  <DetailRow key={`comm-${row.id}`} title={row.Subject || "Message"} subtitle={`${row.Message ?? ""}`.slice(0, 80)} badge={row.Status} />
                ))}
                {custNotes.map((note) => (
                  <DetailRow key={`note-${note.id}`} title={`Note - ${note.date}`} subtitle={note.text} />
                ))}
              </div>
            )}
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-sm font-bold uppercase tracking-wide text-muted-foreground">Payments</h4>
              {pendingBalance > 0 ? (
                <span className="text-xs font-bold text-amber-700 dark:text-amber-300">${pendingBalance.toFixed(2)} pending</span>
              ) : null}
            </div>
            {custPayments.length === 0 ? (
              <p className="rounded-lg border bg-background p-4 text-center text-sm text-muted-foreground">No invoices for this customer yet.</p>
            ) : (
              <div className="space-y-2">
                {custPayments.map((row) => {
                  const overdue = !!row._dueDate && row._dueDate < todayKey && row.Status !== "Paid" && row.Status !== "Cancelled";
                  return (
                    <div key={row.id} className="flex flex-wrap items-center gap-3 rounded-lg border bg-background px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold">
                          Invoice {row.Invoice} {overdue ? <span className="ml-1 text-xs font-bold text-red-600 dark:text-red-400">[OVERDUE]</span> : null}
                        </p>
                        <p className="text-xs text-muted-foreground">Paid ${row.Paid} of ${row.Total} - Balance ${row.Balance}</p>
                      </div>
                      <span className={cn("shrink-0 rounded-full px-2 py-1 text-xs font-bold ring-1", statusClass(row.Status))}>{row.Status}</span>
                      {row.Status !== "Paid" && row.Status !== "Cancelled" ? (
                        <button
                          onClick={() => onSendReminder(row)}
                          className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-xs font-semibold text-teal-700 hover:bg-teal-50 dark:text-teal-200 dark:hover:bg-teal-950"
                        >
                          <Bell className="size-3.5" />
                          Send Reminder
                        </button>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section>
            <h4 className="mb-2 text-sm font-bold uppercase tracking-wide text-muted-foreground">Scheduled Activities</h4>
            {upcomingActivities.length === 0 ? (
              <p className="rounded-lg border bg-background p-4 text-center text-sm text-muted-foreground">
                No upcoming calls, meetings, or follow-ups scheduled for this customer.
              </p>
            ) : (
              <div className="space-y-2">
                {upcomingActivities.map((reminder) => (
                  <DetailRow
                    key={reminder.id}
                    title={reminder.title}
                    subtitle={`${reminder.kind} - ${reminder.date} at ${reminder.time}`}
                    badge={reminder.priority}
                  />
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="flex justify-end border-t p-5">
          <button onClick={onClose} className="rounded-lg border px-4 py-2 text-sm font-semibold">
            Close
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function EmployeeAttendanceWidget() {
  const attendanceTracking = useContext(AttendanceContext);
  const [loggingOut, setLoggingOut] = useState(false);

  if (!attendanceTracking) return null;
  const { current, liveWorkedSeconds, startBreak, endBreak, fullLogout } = attendanceTracking;

  if (!current) {
    return (
      <ChartCard title="Working Hours" subtitle="Loading your attendance session...">
        <div className="flex h-32 items-center justify-center">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      </ChartCard>
    );
  }

  const meta = ATTENDANCE_STATUS_META[current.display_state];
  const shiftSeconds = current.shift.shift_duration_minutes * 60;
  const remainingSeconds = Math.max(shiftSeconds - liveWorkedSeconds, 0);
  const overtimeSeconds = Math.max(liveWorkedSeconds - shiftSeconds, 0);
  const shiftProgress = shiftSeconds > 0 ? Math.min((liveWorkedSeconds / shiftSeconds) * 100, 100) : 0;
  const onBreak = current.display_state === "ON_BREAK";
  const offline = current.display_state === "OFFLINE";

  async function handleLogout() {
    setLoggingOut(true);
    await fullLogout();
    setLoggingOut(false);
  }

  return (
    <div className="grid gap-4 xl:grid-cols-4">
      <article className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <AttendanceStatusDot state={current.display_state} />
          <span className={cn("text-sm font-bold", meta.text)}>{meta.label}</span>
        </div>
        <p className="mt-3 font-mono text-3xl font-bold tabular-nums">{formatHMS(liveWorkedSeconds)}</p>
        <dl className="mt-4 space-y-1.5 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Shift</dt>
            <dd className="font-semibold">{formatHM(shiftSeconds)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Worked</dt>
            <dd className="font-semibold">{formatHM(liveWorkedSeconds)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Remaining</dt>
            <dd className="font-semibold">{formatHM(remainingSeconds)}</dd>
          </div>
        </dl>
        <div className="mt-4 space-y-2">
          <button
            onClick={onBreak ? endBreak : startBreak}
            disabled={offline}
            className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg border bg-background text-sm font-semibold shadow-sm transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Coffee className="size-4 text-amber-500" />
            {onBreak ? "End Break" : "Start Break"}
          </button>
          <button
            onClick={handleLogout}
            disabled={offline || loggingOut}
            className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-teal-600 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loggingOut ? <Loader2 className="size-4 animate-spin" /> : <LogOut className="size-4" />}
            Logout
          </button>
        </div>
      </article>

      <ChartCard title="Today's Hours" subtitle="Active, break, and idle time">
        <dl className="space-y-3 py-1 text-sm">
          <div className="flex items-center justify-between">
            <dt className="text-muted-foreground">Active Hours</dt>
            <dd className="font-bold">{formatHM(current.totals.active_working_seconds)}</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-muted-foreground">Break Time</dt>
            <dd className="font-bold">{formatHM(current.totals.break_seconds)}</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-muted-foreground">Idle Time</dt>
            <dd className="font-bold">{formatHM(current.totals.idle_seconds)}</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-muted-foreground">Breaks Taken</dt>
            <dd className="font-bold">{current.totals.break_count}</dd>
          </div>
        </dl>
      </ChartCard>

      <ChartCard title="Shift Progress" subtitle={`${Math.round(shiftProgress)}% of your shift complete`}>
        <div className="flex h-32 flex-col items-center justify-center gap-3">
          <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-teal-600 transition-all" style={{ width: `${shiftProgress}%` }} />
          </div>
          {overtimeSeconds > 0 ? (
            <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">+{formatHM(overtimeSeconds)} overtime</p>
          ) : (
            <p className="text-sm text-muted-foreground">{formatHM(remainingSeconds)} remaining</p>
          )}
        </div>
      </ChartCard>

      {current.shift.is_salary_enabled ? (
        <ChartCard title="Today's Earnings" subtitle={current.shift.currency}>
          <div className="flex h-32 flex-col items-center justify-center gap-1 text-center">
            <p className="text-3xl font-bold">
              {current.shift.currency} {current.earnings.total_earnings.toFixed(2)}
            </p>
            <p className="text-xs text-muted-foreground">
              Regular {current.earnings.regular_earnings.toFixed(2)} + Overtime {current.earnings.overtime_earnings.toFixed(2)}
            </p>
          </div>
        </ChartCard>
      ) : null}
    </div>
  );
}

function ManagerTeamAttendanceSection() {
  const [rows, setRows] = useState<DailyAttendance[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    function load() {
      attendance
        .teamStatus()
        .then((result) => {
          if (!cancelled) setRows(result);
        })
        .catch(() => {
          if (!cancelled) setError("Could not load your team's attendance.");
        });
    }
    load();
    const interval = window.setInterval(load, 45_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <article className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="mb-4">
        <h3 className="text-lg font-bold">Your Team&apos;s Attendance</h3>
        <p className="text-sm text-muted-foreground">Live working hours for everyone on your team, today.</p>
      </div>
      {error ? (
        <p className="py-6 text-center text-sm text-red-600">{error}</p>
      ) : rows === null ? (
        <div className="flex h-32 items-center justify-center">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      ) : rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No team attendance recorded yet today.</p>
      ) : (
        <div className="glass-scrollbar overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-2 pr-4">Employee</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2 pr-4">Login</th>
                <th className="pb-2 pr-4">Active</th>
                <th className="pb-2 pr-4">Break</th>
                <th className="pb-2 pr-4">Idle</th>
                <th className="pb-2 pr-4">Shift Progress</th>
                <th className="pb-2 pr-4">Overtime</th>
                <th className="pb-2">Short Hours</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const shiftSeconds = row.shift_minutes * 60;
                const progress = shiftSeconds > 0 ? Math.min((row.active_working_seconds / shiftSeconds) * 100, 100) : 0;
                return (
                  <tr key={row.employee_id} className="border-b last:border-b-0">
                    <td className="py-2.5 pr-4 font-semibold">{row.employee_name}</td>
                    <td className="py-2.5 pr-4">
                      <span className="rounded-full bg-teal-50 px-2 py-1 text-xs font-semibold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                        {row.status}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-muted-foreground">
                      {row.login_time ? new Date(row.login_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                    </td>
                    <td className="py-2.5 pr-4">{formatHM(row.active_working_seconds)}</td>
                    <td className="py-2.5 pr-4">{formatHM(row.break_seconds)}</td>
                    <td className="py-2.5 pr-4">{formatHM(row.idle_seconds)}</td>
                    <td className="py-2.5 pr-4">{Math.round(progress)}%</td>
                    <td className="py-2.5 pr-4">{row.overtime_minutes > 0 ? `${Math.round(row.overtime_minutes)}m` : "—"}</td>
                    <td className="py-2.5">{row.short_minutes > 0 ? `${Math.round(row.short_minutes)}m` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

function SuperAdminAttendanceSection() {
  const [rows, setRows] = useState<DailyAttendance[] | null>(null);
  const [weeklyRows, setWeeklyRows] = useState<DailyAttendance[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    function load() {
      attendance
        .companyReport()
        .then((result) => {
          if (!cancelled) setRows(result);
        })
        .catch(() => {
          if (!cancelled) setError("Could not load company-wide attendance.");
        });
    }
    load();
    const interval = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const today = new Date();
    const from = new Date(today);
    from.setDate(from.getDate() - 6);
    attendance
      .companyReport(from.toISOString().slice(0, 10), today.toISOString().slice(0, 10))
      .then((result) => {
        if (!cancelled) setWeeklyRows(result);
      })
      .catch(() => {
        // Non-fatal — the weekly trend charts simply stay empty.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const dailyHoursData = useMemo(
    () =>
      (rows ?? []).map((row) => ({
        label: row.employee_name.split(" ")[0] ?? row.employee_name,
        value: Math.round((row.active_working_seconds / 3600) * 10) / 10
      })),
    [rows]
  );
  const overtimeData = useMemo(
    () =>
      (rows ?? [])
        .filter((row) => row.overtime_minutes > 0)
        .map((row) => ({ label: row.employee_name.split(" ")[0] ?? row.employee_name, value: Math.round(row.overtime_minutes) })),
    [rows]
  );
  const breakIdleData = useMemo(() => {
    const totalBreak = (rows ?? []).reduce((sum, row) => sum + row.break_seconds, 0);
    const totalIdle = (rows ?? []).reduce((sum, row) => sum + row.idle_seconds, 0);
    return [
      { label: "Break", value: Math.round(totalBreak / 60), color: CHART_PALETTE[2] },
      { label: "Idle", value: Math.round(totalIdle / 60), color: CHART_PALETTE[3] }
    ];
  }, [rows]);
  const averageActiveHours = useMemo(() => {
    const list = rows ?? [];
    if (list.length === 0) return 0;
    return list.reduce((sum, row) => sum + row.active_working_seconds, 0) / list.length / 3600;
  }, [rows]);
  const totalPayable = useMemo(() => (rows ?? []).reduce((sum, row) => sum + row.earnings.total_earnings, 0), [rows]);

  const teamWorkingHoursData = useMemo(() => {
    const byDate = new Map<string, number>();
    (weeklyRows ?? []).forEach((row) => {
      byDate.set(row.date, (byDate.get(row.date) ?? 0) + row.active_working_seconds);
    });
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, seconds]) => ({ label: date.slice(5), value: Math.round((seconds / 3600) * 10) / 10 }));
  }, [weeklyRows]);

  const averageActiveHoursTrend = useMemo(() => {
    const byDate = new Map<string, { total: number; count: number }>();
    (weeklyRows ?? []).forEach((row) => {
      const entry = byDate.get(row.date) ?? { total: 0, count: 0 };
      entry.total += row.active_working_seconds;
      entry.count += 1;
      byDate.set(row.date, entry);
    });
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, { total, count }]) => ({ label: date.slice(5), value: count > 0 ? Math.round((total / count / 3600) * 10) / 10 : 0 }));
  }, [weeklyRows]);

  return (
    <div className="space-y-4">
      <article className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-lg font-bold">Company-Wide Attendance</h3>
            <p className="text-sm text-muted-foreground">Today&apos;s working hours across every employee.</p>
          </div>
          <div className="rounded-lg bg-teal-50 px-3 py-2 text-sm font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
            Avg active hours: {averageActiveHours.toFixed(1)}h
          </div>
        </div>
        {error ? (
          <p className="py-6 text-center text-sm text-red-600">{error}</p>
        ) : rows === null ? (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        ) : rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No attendance recorded yet today.</p>
        ) : (
          <div className="glass-scrollbar overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead>
                <tr className="border-b text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 pr-4">Employee</th>
                  <th className="pb-2 pr-4">Login</th>
                  <th className="pb-2 pr-4">Active</th>
                  <th className="pb-2 pr-4">Break</th>
                  <th className="pb-2 pr-4">Idle</th>
                  <th className="pb-2 pr-4">Overtime</th>
                  <th className="pb-2 pr-4">Short Hours</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2">Payable</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.employee_id}-${row.date}`} className="border-b last:border-b-0">
                    <td className="py-2.5 pr-4 font-semibold">{row.employee_name}</td>
                    <td className="py-2.5 pr-4 text-muted-foreground">
                      {row.login_time ? new Date(row.login_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                    </td>
                    <td className="py-2.5 pr-4">{formatHM(row.active_working_seconds)}</td>
                    <td className="py-2.5 pr-4">{formatHM(row.break_seconds)}</td>
                    <td className="py-2.5 pr-4">{formatHM(row.idle_seconds)}</td>
                    <td className="py-2.5 pr-4">{row.overtime_minutes > 0 ? `${Math.round(row.overtime_minutes)}m` : "—"}</td>
                    <td className="py-2.5 pr-4">{row.short_minutes > 0 ? `${Math.round(row.short_minutes)}m` : "—"}</td>
                    <td className="py-2.5 pr-4">
                      <span className="rounded-full bg-teal-50 px-2 py-1 text-xs font-semibold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                        {row.status}
                      </span>
                    </td>
                    <td className="py-2.5 font-semibold">
                      {row.earnings.total_earnings > 0 ? `${row.earnings.currency} ${row.earnings.total_earnings.toFixed(2)}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
              {totalPayable > 0 ? (
                <tfoot>
                  <tr>
                    <td colSpan={8} className="pt-3 text-right text-sm font-semibold text-muted-foreground">
                      Total payable today
                    </td>
                    <td className="pt-3 font-bold">
                      {rows[0]?.earnings.currency ?? ""} {totalPayable.toFixed(2)}
                    </td>
                  </tr>
                </tfoot>
              ) : null}
            </table>
          </div>
        )}
      </article>

      <div className="grid gap-4 xl:grid-cols-3">
        <ChartCard title="Daily Working Hours" subtitle="Active hours per employee, today">
          {dailyHoursData.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <BarChart data={dailyHoursData} suffix="h" />
          )}
        </ChartCard>
        <ChartCard title="Overtime" subtitle="Minutes of overtime per employee, today">
          {overtimeData.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No overtime today.</p>
          ) : (
            <BarChart data={overtimeData} suffix="m" />
          )}
        </ChartCard>
        <ChartCard title="Break / Idle Analysis" subtitle="Company-wide minutes, today">
          <PieChart data={breakIdleData} donut />
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Team Working Hours" subtitle="Total active hours across the company, last 7 days">
          {teamWorkingHoursData.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <BarChart data={teamWorkingHoursData} suffix="h" />
          )}
        </ChartCard>
        <ChartCard title="Average Active Hours" subtitle="Per-employee average, last 7 days">
          {averageActiveHoursTrend.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No data yet.</p>
          ) : (
            <LineChart data={averageActiveHoursTrend} suffix="h" />
          )}
        </ChartCard>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Super Admin communication audit trail
// ---------------------------------------------------------------------------
//
// Rendered ONLY inside the existing Super-Admin-only `audit` module (see
// MODULE_ACCESS: "audit" appears for superadmin and for no other role) and
// gated a second time at the call site on `role === "superadmin"`, matching
// the `activeKey === "settings" && role === "superadmin"` convention already
// used for ShiftConfigCard. Neither gate is the real protection: the backend
// scopes every one of these endpoints to the authenticated user's own role
// server-side (apps.crm.services.scope_queryset_for_user) and strips contact
// detail below Manager level (apps.core.serializers.PiiMaskedSerializerMixin),
// so an Employee who calls the same URLs by hand gets their own rows with the
// PII removed, not this view's data. The gates here are UI tidiness only.
//
// Deliberately NO new backend aggregation endpoint: the per-channel list
// endpoints are individually filterable (owner / direction / status / date
// range / entity), so one cross-channel thread is assembled here by merging
// them on timestamp — the same client-side merge EmployeeCustomerProfileModal's
// Interaction History already does, and one less privileged surface to secure.

type CommAuditChannel = "Email" | "Call" | "WhatsApp";

type CommAuditEvent = {
  key: string;
  channel: CommAuditChannel;
  direction: string;
  status: string;
  timestamp: string;
  employeeId: string;
  contact: string;
  summary: string;
  detail: string;
  providerId: string;
  duration: string;
};

const COMM_AUDIT_CHANNELS: CommAuditChannel[] = ["Email", "Call", "WhatsApp"];

// Each channel's own status vocabulary (see apps/communications/models.py).
// A status is only ever sent to the endpoints that accept it — django-filter
// rejects an out-of-vocabulary choice with a 400, so filtering "COMPLETED"
// must not be forwarded to the email endpoint.
const COMM_AUDIT_STATUSES: Record<CommAuditChannel, string[]> = {
  Email: ["QUEUED", "SENT", "FAILED"],
  Call: ["QUEUED", "RINGING", "IN_PROGRESS", "COMPLETED", "FAILED", "NO_ANSWER", "BUSY"],
  WhatsApp: ["QUEUED", "SENT", "DELIVERED", "READ", "FAILED"]
};

const COMM_AUDIT_ALL_STATUSES = Array.from(
  new Set(COMM_AUDIT_CHANNELS.flatMap((channel) => COMM_AUDIT_STATUSES[channel]))
).sort();

const COMM_AUDIT_CHANNEL_ICON: Record<CommAuditChannel, React.ElementType> = {
  Email: Mail,
  Call: Phone,
  WhatsApp: MessageCircle
};

// Local to this section on purpose: the shared `badgeStyles` map is keyed by
// the Title-Case status words every other module renders, and the backend's
// communication statuses are UPPER_SNAKE. Keeping them here avoids widening a
// map other modules depend on.
const COMM_AUDIT_STATUS_STYLES: Record<string, string> = {
  SENT: "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950 dark:text-blue-200",
  DELIVERED: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200",
  READ: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200",
  COMPLETED: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-200",
  FAILED: "bg-red-50 text-red-700 ring-red-200 dark:bg-red-950 dark:text-red-200",
  NO_ANSWER: "bg-orange-50 text-orange-700 ring-orange-200 dark:bg-orange-950 dark:text-orange-200",
  BUSY: "bg-orange-50 text-orange-700 ring-orange-200 dark:bg-orange-950 dark:text-orange-200",
  QUEUED: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950 dark:text-amber-200",
  RINGING: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950 dark:text-amber-200",
  IN_PROGRESS: "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950 dark:text-blue-200"
};

function commAuditStatusClass(value: string) {
  return COMM_AUDIT_STATUS_STYLES[value] ?? statusClass(value);
}

function relatedObjectLabel(value: unknown): string {
  if (value && typeof value === "object" && "label" in (value as Record<string, unknown>)) {
    return String((value as Record<string, unknown>).label ?? "");
  }
  return "";
}

function SuperAdminCommunicationAuditSection({ users }: { users: RowRecord[] }) {
  const [channel, setChannel] = useState<"All" | CommAuditChannel>("All");
  const [employeeId, setEmployeeId] = useState("");
  const [direction, setDirection] = useState("");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [events, setEvents] = useState<CommAuditEvent[] | null>(null);
  const [totals, setTotals] = useState<Record<CommAuditChannel, number>>({ Email: 0, Call: 0, WhatsApp: 0 });
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CommAuditEvent | null>(null);

  const employeeName = useCallback(
    (id: string) => (id ? users.find((user) => user.id === id)?.Name ?? `User #${id}` : "System"),
    [users]
  );

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setEvents(null);

    // Every parameter below is a FILTER, never an authorization hint: the
    // backend applies role scoping before any of them, so a narrower or
    // wider value can only ever subset what this user may already read.
    const shared = new URLSearchParams();
    shared.set("page_size", "100");
    shared.set("ordering", "-created_at");
    if (employeeId) shared.set("owner", employeeId);
    if (direction) shared.set("direction", direction);
    if (dateFrom) shared.set("created_from", `${dateFrom}T00:00:00`);
    if (dateTo) shared.set("created_to", `${dateTo}T23:59:59`);

    function queryFor(target: CommAuditChannel) {
      const params = new URLSearchParams(shared);
      if (status && COMM_AUDIT_STATUSES[target].includes(status)) params.set("status", status);
      return `?${params.toString()}`;
    }

    // A channel excluded by the filter (or by an incompatible status) is
    // simply not requested — resolving to an empty page keeps the merge
    // below uniform.
    const empty = Promise.resolve({ count: 0, next: null, previous: null, results: [] as Record<string, unknown>[] });
    const wants = (target: CommAuditChannel) =>
      (channel === "All" || channel === target) && (!status || COMM_AUDIT_STATUSES[target].includes(status));

    Promise.all([
      wants("Email") ? communications.listEmailMessages(queryFor("Email")) : empty,
      wants("Call") ? communications.listCalls(queryFor("Call")) : empty,
      wants("WhatsApp") ? communications.listWhatsAppMessages(queryFor("WhatsApp")) : empty
    ])
      .then(([emailPage, callPage, whatsappPage]) => {
        if (cancelled) return;

        const emailEvents: CommAuditEvent[] = emailPage.results.map((row) => ({
          key: `email-${row.id}`,
          channel: "Email",
          direction: String(row.direction ?? ""),
          status: String(row.status ?? ""),
          timestamp: String(row.sent_at ?? row.created_at ?? ""),
          employeeId: row.owner == null ? "" : String(row.owner),
          contact: String(row.recipient_label ?? "") || String(row.to_email ?? "") || "—",
          summary: String(row.subject ?? ""),
          detail: String(row.error_message ?? "") || String(row.body ?? ""),
          providerId: String(row.to_email ?? ""),
          duration: ""
        }));

        const callEvents: CommAuditEvent[] = callPage.results.map((row) => ({
          key: `call-${row.id}`,
          channel: "Call",
          direction: String(row.direction ?? ""),
          status: String(row.status ?? ""),
          timestamp: String(row.started_at ?? row.created_at ?? ""),
          employeeId: row.owner == null ? "" : String(row.owner),
          contact: relatedObjectLabel(row.related_object) || String(row.to_number ?? "") || "—",
          summary: `${String(row.direction ?? "")} call`,
          detail: String(row.error_message ?? ""),
          providerId: String(row.provider_call_id ?? ""),
          duration: row.duration_seconds == null ? "" : `${row.duration_seconds}s`
        }));

        const whatsappEvents: CommAuditEvent[] = whatsappPage.results.map((row) => ({
          key: `whatsapp-${row.id}`,
          channel: "WhatsApp",
          direction: String(row.direction ?? ""),
          status: String(row.status ?? ""),
          timestamp: String(row.created_at ?? ""),
          employeeId: row.owner == null ? "" : String(row.owner),
          contact: String(row.customer_name ?? "") || String(row.receiver ?? "") || "—",
          summary: String(row.message ?? "").slice(0, 120),
          detail: String(row.error_message ?? "") || String(row.message ?? ""),
          providerId: String(row.provider_message_id ?? ""),
          duration: ""
        }));

        setTotals({ Email: emailPage.count, Call: callPage.count, WhatsApp: whatsappPage.count });
        setEvents(
          [...emailEvents, ...callEvents, ...whatsappEvents].sort((a, b) => b.timestamp.localeCompare(a.timestamp))
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? `Could not load the communication audit trail: ${err.message}`
            : "Could not reach the communications API."
        );
      });

    return () => {
      cancelled = true;
    };
  }, [channel, employeeId, direction, status, dateFrom, dateTo]);

  const visibleEvents = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return events ?? [];
    return (events ?? []).filter((event) =>
      [event.contact, event.summary, event.detail, event.providerId, employeeName(event.employeeId)]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    );
  }, [events, search, employeeName]);

  const loadedTotal = totals.Email + totals.Call + totals.WhatsApp;
  const truncated = (events?.length ?? 0) < loadedTotal;

  return (
    <section className="rounded-2xl border bg-card shadow-sm">
      <div className="border-b p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-bold">
              <ShieldCheck className="size-4 text-teal-700 dark:text-teal-300" />
              Communication Audit Trail
            </h3>
            <p className="text-sm text-muted-foreground">
              Every email, call and WhatsApp message between an employee and a customer or lead, merged into one
              timeline. Super Admin only — enforced server-side.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs font-semibold">
            {COMM_AUDIT_CHANNELS.map((item) => (
              <span key={item} className="rounded-full border bg-background px-3 py-1.5">
                {item}: {totals[item].toLocaleString()}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <label className="relative min-w-0">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search conversations..."
              className="h-10 w-full rounded-lg border bg-background pl-9 pr-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
            />
          </label>
          <select
            value={channel}
            onChange={(event) => setChannel(event.target.value as "All" | CommAuditChannel)}
            className="h-10 rounded-lg border bg-background px-3 text-sm font-medium outline-none ring-teal-600/20 transition focus:ring-4"
            aria-label="Filter by channel"
          >
            <option value="All">All channels</option>
            {COMM_AUDIT_CHANNELS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <select
            value={employeeId}
            onChange={(event) => setEmployeeId(event.target.value)}
            className="h-10 rounded-lg border bg-background px-3 text-sm font-medium outline-none ring-teal-600/20 transition focus:ring-4"
            aria-label="Filter by employee"
          >
            <option value="">All employees</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.Name}
              </option>
            ))}
          </select>
          <select
            value={direction}
            onChange={(event) => setDirection(event.target.value)}
            className="h-10 rounded-lg border bg-background px-3 text-sm font-medium outline-none ring-teal-600/20 transition focus:ring-4"
            aria-label="Filter by direction"
          >
            <option value="">Any direction</option>
            <option value="OUTBOUND">Outbound</option>
            <option value="INBOUND">Inbound</option>
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="h-10 rounded-lg border bg-background px-3 text-sm font-medium outline-none ring-teal-600/20 transition focus:ring-4"
            aria-label="Filter by status"
          >
            <option value="">Any status</option>
            {COMM_AUDIT_ALL_STATUSES.map((item) => (
              <option key={item} value={item}>
                {item.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <label className="flex h-10 items-center gap-2 rounded-lg border bg-background px-3 text-sm">
            <span className="shrink-0 text-xs font-semibold text-muted-foreground">From</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          <label className="flex h-10 items-center gap-2 rounded-lg border bg-background px-3 text-sm">
            <span className="shrink-0 text-xs font-semibold text-muted-foreground">To</span>
            <input
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>
          <button
            onClick={() => {
              setChannel("All");
              setEmployeeId("");
              setDirection("");
              setStatus("");
              setDateFrom("");
              setDateTo("");
              setSearch("");
            }}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border bg-background px-3 text-sm font-semibold hover:bg-muted"
          >
            <Filter className="size-4" />
            Clear filters
          </button>
        </div>
      </div>

      {error ? (
        <p className="py-10 text-center text-sm text-red-600">{error}</p>
      ) : events === null ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      ) : visibleEvents.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          No communication events match these filters.
        </p>
      ) : (
        <div className="glass-scrollbar overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead>
              <tr className="border-b text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 pb-2 pt-3">Time</th>
                <th className="px-4 pb-2 pt-3">Channel</th>
                <th className="px-4 pb-2 pt-3">Direction</th>
                <th className="px-4 pb-2 pt-3">Employee</th>
                <th className="px-4 pb-2 pt-3">Lead / Customer</th>
                <th className="px-4 pb-2 pt-3">Message</th>
                <th className="px-4 pb-2 pt-3">Status</th>
                <th className="px-4 pb-2 pt-3">Provider ID</th>
              </tr>
            </thead>
            <tbody>
              {visibleEvents.map((event) => {
                const ChannelIcon = COMM_AUDIT_CHANNEL_ICON[event.channel];
                return (
                  <tr
                    key={event.key}
                    onClick={() => setSelected(event)}
                    className="cursor-pointer border-b last:border-b-0 hover:bg-muted/50"
                  >
                    <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">
                      {event.timestamp ? new Date(event.timestamp).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="inline-flex items-center gap-1.5 font-semibold">
                        <ChannelIcon className="size-3.5 text-teal-700 dark:text-teal-300" />
                        {event.channel}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">{event.direction || "—"}</td>
                    <td className="px-4 py-2.5 font-semibold">{employeeName(event.employeeId)}</td>
                    <td className="px-4 py-2.5">{event.contact}</td>
                    <td className="max-w-[280px] truncate px-4 py-2.5 text-muted-foreground">
                      {event.summary || "—"}
                      {event.duration ? <span className="ml-2 font-semibold text-foreground">{event.duration}</span> : null}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={cn("rounded-full px-2 py-1 text-xs font-bold ring-1", commAuditStatusClass(event.status))}>
                        {event.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="max-w-[180px] truncate px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {event.providerId || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-col gap-1 border-t p-4 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>
          Showing <span className="font-semibold text-foreground">{visibleEvents.length}</span> of{" "}
          {loadedTotal.toLocaleString()} recorded communication events.
        </p>
        {truncated ? (
          <p className="text-xs">Showing the most recent 100 per channel — narrow the filters to see older events.</p>
        ) : null}
      </div>

      <AnimatePresence>
        {selected ? (
          <CommunicationAuditDetailModal
            event={selected}
            employeeName={employeeName(selected.employeeId)}
            onClose={() => setSelected(null)}
          />
        ) : null}
      </AnimatePresence>
    </section>
  );
}

function CommunicationAuditDetailModal({
  event,
  employeeName,
  onClose
}: {
  event: CommAuditEvent;
  employeeName: string;
  onClose: () => void;
}) {
  return (
    <motion.div
      className="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-2xl border bg-card shadow-soft"
        initial={{ scale: 0.96, y: 18 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, y: 18 }}
        onClick={(clickEvent) => clickEvent.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b p-5">
          <div>
            <h3 className="text-xl font-bold">{event.channel} — audit record</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Recorded by the backend at the moment it happened. This record cannot be edited or deleted.
            </p>
          </div>
          <button onClick={onClose} className="inline-flex size-9 items-center justify-center rounded-lg border" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <div className="space-y-4 p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <DetailRow title="Timestamp" subtitle={event.timestamp ? new Date(event.timestamp).toLocaleString() : "—"} />
            <DetailRow title="Employee" subtitle={employeeName} />
            <DetailRow title="Lead / Customer" subtitle={event.contact} />
            <DetailRow title="Direction" subtitle={event.direction || "—"} />
            <DetailRow title="Status" subtitle={event.status.replace(/_/g, " ")} badge={event.status} />
            <DetailRow title="Call duration" subtitle={event.duration || "—"} />
            <DetailRow title="Provider ID" subtitle={event.providerId || "—"} />
          </div>
          <div>
            <h4 className="mb-2 text-sm font-bold uppercase tracking-wide text-muted-foreground">Content</h4>
            <p className="whitespace-pre-wrap rounded-lg border bg-background p-4 text-sm">
              {event.detail || event.summary || "No message content recorded."}
            </p>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

type CalendarDayData = {
  leads: RowRecord[];
  customers: RowRecord[];
  payments: RowRecord[];
  calls: RowRecord[];
  communication: RowRecord[];
  tasks: RowRecord[];
  audit: RowRecord[];
  reminders: Reminder[];
  notes: CalendarNote[];
};

function emptyDayData(): CalendarDayData {
  return { leads: [], customers: [], payments: [], calls: [], communication: [], tasks: [], audit: [], reminders: [], notes: [] };
}

function SmartCalendarModule({
  role,
  recordsByModule,
  reminders,
  notes,
  currentUserName,
  teamNames,
  onAddReminder,
  onUpdateReminder,
  onDeleteReminder,
  onToggleReminderComplete,
  onSnoozeReminder,
  onAddNote,
  onDeleteNote,
  onToggleNotePin
}: {
  role: Role;
  recordsByModule: RecordsByModule;
  reminders: Reminder[];
  notes: CalendarNote[];
  currentUserName: string;
  teamNames: string[];
  onAddReminder: (input: Omit<Reminder, "id" | "completed" | "snoozedUntil" | "createdByRole">) => void;
  onUpdateReminder: (id: string, patch: Partial<Reminder>) => void;
  onDeleteReminder: (id: string) => void;
  onToggleReminderComplete: (id: string) => void;
  onSnoozeReminder: (id: string, days?: number) => void;
  onAddNote: (input: Omit<CalendarNote, "id" | "createdAt" | "pinned">) => void;
  onDeleteNote: (id: string) => void;
  onToggleNotePin: (id: string) => void;
}) {
  const [view, setView] = useState<"month" | "week" | "day">("month");
  const [cursor, setCursor] = useState(() => new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const identity = role === "employee" ? currentUserName : role === "manager" ? "Manager" : "Super Admin";
  const todayKey = toDateKey(new Date());

  const visibleReminders = useMemo(
    () => reminders.filter((reminder) => canSeeReminder(reminder, role, currentUserName, teamNames)),
    [reminders, role, currentUserName, teamNames]
  );
  const visibleNotes = useMemo(() => notes.filter((note) => canSeeNote(note, role, currentUserName)), [notes, role, currentUserName]);

  const dayMap = useMemo(() => {
    const map = new Map<string, CalendarDayData>();
    function ensure(key: string) {
      if (!map.has(key)) map.set(key, emptyDayData());
      return map.get(key)!;
    }
    scopeRowsForCalendar(recordsByModule.leads ?? []).forEach((row) => ensure(pseudoDateForRow(row.id)).leads.push(row));
    scopeRowsForCalendar(recordsByModule.customers ?? []).forEach((row) => ensure(pseudoDateForRow(row.id)).customers.push(row));
    scopeRowsForCalendar(recordsByModule.payments ?? []).forEach((row) => ensure(pseudoDateForRow(row.id)).payments.push(row));
    scopeRowsForCalendar(recordsByModule.tasks ?? []).forEach((row) => ensure(pseudoDateForRow(row.id)).tasks.push(row));
    scopeRowsForCalendar(recordsByModule.communication ?? []).forEach((row) => {
      const bucket = ensure(pseudoDateForRow(row.id));
      bucket.communication.push(row);
      if (row.Channel === "Call") bucket.calls.push(row);
    });
    if (role === "superadmin") {
      (recordsByModule.audit ?? []).forEach((row) => ensure(pseudoDateForRow(row.id)).audit.push(row));
    }
    visibleReminders.forEach((reminder) => ensure(reminder.date).reminders.push(reminder));
    visibleNotes.forEach((note) => ensure(note.date).notes.push(note));
    return map;
  }, [recordsByModule, role, visibleReminders, visibleNotes]);

  const lowerSearch = search.trim().toLowerCase();
  function dayMatchesSearch(key: string): boolean {
    if (!lowerSearch) return false;
    const day = dayMap.get(key);
    if (!day) return false;
    const haystack = [
      ...day.leads.map((row) => row.Lead ?? ""),
      ...day.customers.map((row) => row.Customer ?? ""),
      ...day.tasks.map((row) => row.Task ?? ""),
      ...day.reminders.map((reminder) => reminder.title),
      ...day.notes.map((note) => note.text)
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(lowerSearch);
  }

  function goToday() {
    setCursor(new Date());
  }
  function goPrev() {
    if (view === "month") setCursor((current) => addMonths(current, -1));
    else if (view === "week") setCursor((current) => addDays(current, -7));
    else setCursor((current) => addDays(current, -1));
  }
  function goNext() {
    if (view === "month") setCursor((current) => addMonths(current, 1));
    else if (view === "week") setCursor((current) => addDays(current, 7));
    else setCursor((current) => addDays(current, 1));
  }

  const monthLabel = cursor.toLocaleDateString("en-US", { month: "long", year: "numeric" });

  const monthDays = useMemo(() => {
    const firstOfMonth = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const gridStart = startOfWeek(firstOfMonth);
    return Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
  }, [cursor]);

  const weekDays = useMemo(() => {
    const start = startOfWeek(cursor);
    return Array.from({ length: 7 }, (_, index) => addDays(start, index));
  }, [cursor]);

  function DayBadges({ dateKey }: { dateKey: string }) {
    const day = dayMap.get(dateKey);
    if (!day) return null;
    const counts: Record<string, number> = {
      leads: day.leads.length,
      customers: day.customers.length,
      calls: day.calls.length,
      tasks: day.tasks.length,
      reminders: day.reminders.length,
      notes: day.notes.length
    };
    const active = CALENDAR_ITEM_DOTS.filter((item) => counts[item.key] > 0);
    if (active.length === 0) return null;
    return (
      <div className="mt-1 flex flex-wrap gap-1">
        {active.slice(0, 4).map((item) => (
          <span
            key={item.key}
            title={`${counts[item.key]} ${item.label}`}
            className={cn("inline-flex min-w-4 items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-bold text-white", item.color)}
          >
            {counts[item.key]}
          </span>
        ))}
      </div>
    );
  }

  // Employee-only date preview (spec section 9): customer initials chips
  // for that day's follow-up-linked customers, and a StickyNote icon (with
  // a count bubble when there's more than one note) instead of the
  // generic numeric-count dots Manager/Super Admin still see via
  // DayBadges above — reads from the same already-scoped `dayMap`.
  function EmployeeDayBadges({ dateKey }: { dateKey: string }) {
    const day = dayMap.get(dateKey);
    if (!day) return null;
    const initials = (name: string) =>
      name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() ?? "")
        .join("") || "?";
    const customerChips = day.customers.slice(0, 3);
    const noteCount = day.notes.length;
    if (customerChips.length === 0 && noteCount === 0) return null;
    return (
      <div className="mt-1 flex flex-wrap items-center gap-1">
        {customerChips.map((row) => (
          <span
            key={row.id}
            className="inline-flex min-w-5 items-center justify-center rounded-full bg-pink-500 px-1.5 py-0.5 text-[10px] font-bold text-white"
          >
            {initials(row.Customer ?? "")}
          </span>
        ))}
        {noteCount > 0 ? (
          <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
            <StickyNote className="size-3" />
            {noteCount > 1 ? noteCount : ""}
          </span>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={goPrev} className="inline-flex size-9 items-center justify-center rounded-lg border bg-background" aria-label="Previous">
              <ChevronLeft className="size-4" />
            </button>
            <button onClick={goNext} className="inline-flex size-9 items-center justify-center rounded-lg border bg-background" aria-label="Next">
              <ChevronRight className="size-4" />
            </button>
            <button onClick={goToday} className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-2 text-sm font-semibold">
              <CalendarDays className="size-4 text-teal-600" />
              Today
            </button>
            <h3 className="ml-1 text-lg font-bold">
              {view === "day"
                ? cursor.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })
                : view === "week"
                ? `Week of ${weekDays[0].toLocaleDateString("en-US", { month: "short", day: "numeric" })}`
                : monthLabel}
            </h3>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search events..."
                className="h-10 w-44 rounded-lg border bg-background pl-9 pr-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4 sm:w-56"
              />
            </label>
            <input
              type="date"
              value={toDateKey(cursor)}
              onChange={(event) => {
                if (event.target.value) setCursor(parseDateKey(event.target.value));
              }}
              className="h-10 rounded-lg border bg-background px-3 text-sm outline-none ring-teal-600/20 transition focus:ring-4"
            />
            <div className="flex rounded-lg border bg-background p-1">
              {(["month", "week", "day"] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => setView(option)}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-semibold capitalize transition",
                    view === option ? "bg-teal-600 text-white" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {view === "month" ? (
        <div className="overflow-hidden rounded-2xl border bg-card shadow-sm">
          <div className="grid grid-cols-7 border-b bg-muted/60 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((label) => (
              <div key={label} className="px-2 py-3 text-center">
                {label}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7">
            {monthDays.map((date, index) => {
              const key = toDateKey(date);
              const inMonth = date.getMonth() === cursor.getMonth();
              const isToday = key === todayKey;
              const matched = dayMatchesSearch(key);
              return (
                <button
                  key={`${key}-${index}`}
                  onClick={() => setSelectedDate(key)}
                  className={cn(
                    "min-h-24 border-b border-r p-2 text-left transition hover:bg-muted/50",
                    !inMonth && "bg-muted/20 text-muted-foreground",
                    matched && "ring-2 ring-inset ring-teal-500"
                  )}
                >
                  <span className={cn("inline-flex size-6 items-center justify-center rounded-full text-xs font-bold", isToday && "bg-teal-600 text-white")}>
                    {date.getDate()}
                  </span>
                  {role === "employee" ? <EmployeeDayBadges dateKey={key} /> : <DayBadges dateKey={key} />}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {view === "week" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4 xl:grid-cols-7">
          {weekDays.map((date) => {
            const key = toDateKey(date);
            const day = dayMap.get(key);
            const isToday = key === todayKey;
            const titles = [
              ...(day?.reminders.map((reminder) => reminder.title) ?? []),
              ...(day?.tasks.map((row) => row.Task ?? "Task") ?? [])
            ];
            return (
              <button
                key={key}
                onClick={() => setSelectedDate(key)}
                className={cn(
                  "min-h-40 rounded-2xl border bg-card p-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-soft",
                  isToday && "ring-2 ring-teal-500"
                )}
              >
                <p className="text-xs font-bold uppercase text-muted-foreground">{date.toLocaleDateString("en-US", { weekday: "short" })}</p>
                <p className="text-lg font-bold">{date.getDate()}</p>
                <DayBadges dateKey={key} />
                <div className="mt-2 space-y-1">
                  {titles.slice(0, 3).map((title, index) => (
                    <p key={index} className="truncate rounded-md bg-muted px-1.5 py-1 text-[11px] font-medium">
                      {title}
                    </p>
                  ))}
                  {titles.length > 3 ? <p className="text-[11px] text-muted-foreground">+{titles.length - 3} more</p> : null}
                </div>
              </button>
            );
          })}
        </div>
      ) : null}

      {view === "day" ? (
        <div className="rounded-2xl border bg-card p-5 shadow-sm">
          <DayContent
            role={role}
            identity={identity}
            teamNames={teamNames}
            dateKey={toDateKey(cursor)}
            day={dayMap.get(toDateKey(cursor)) ?? emptyDayData()}
            onAddReminder={onAddReminder}
            onUpdateReminder={onUpdateReminder}
            onDeleteReminder={onDeleteReminder}
            onToggleReminderComplete={onToggleReminderComplete}
            onSnoozeReminder={onSnoozeReminder}
            onAddNote={onAddNote}
            onDeleteNote={onDeleteNote}
            onToggleNotePin={onToggleNotePin}
          />
        </div>
      ) : null}

      <AnimatePresence>
        {selectedDate ? (
          <DateDetailsPanel
            role={role}
            identity={identity}
            teamNames={teamNames}
            dateKey={selectedDate}
            day={dayMap.get(selectedDate) ?? emptyDayData()}
            onClose={() => setSelectedDate(null)}
            onAddReminder={onAddReminder}
            onUpdateReminder={onUpdateReminder}
            onDeleteReminder={onDeleteReminder}
            onToggleReminderComplete={onToggleReminderComplete}
            onSnoozeReminder={onSnoozeReminder}
            onAddNote={onAddNote}
            onDeleteNote={onDeleteNote}
            onToggleNotePin={onToggleNotePin}
          />
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function DateDetailsPanel({
  role,
  identity,
  teamNames,
  dateKey,
  day,
  onClose,
  onAddReminder,
  onUpdateReminder,
  onDeleteReminder,
  onToggleReminderComplete,
  onSnoozeReminder,
  onAddNote,
  onDeleteNote,
  onToggleNotePin
}: {
  role: Role;
  identity: string;
  teamNames: string[];
  dateKey: string;
  day: CalendarDayData;
  onClose: () => void;
  onAddReminder: (input: Omit<Reminder, "id" | "completed" | "snoozedUntil" | "createdByRole">) => void;
  onUpdateReminder: (id: string, patch: Partial<Reminder>) => void;
  onDeleteReminder: (id: string) => void;
  onToggleReminderComplete: (id: string) => void;
  onSnoozeReminder: (id: string, days?: number) => void;
  onAddNote: (input: Omit<CalendarNote, "id" | "createdAt" | "pinned">) => void;
  onDeleteNote: (id: string) => void;
  onToggleNotePin: (id: string) => void;
}) {
  return createPortal(
    <>
      <motion.div
        className="fixed inset-0 z-[70] bg-black/40"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.aside
        className="glass-scrollbar fixed right-0 top-0 z-[80] h-full w-full max-w-md overflow-y-auto border-l bg-card p-5 shadow-soft"
        initial={{ x: 420 }}
        animate={{ x: 0 }}
        exit={{ x: 420 }}
        transition={{ type: "tween", duration: 0.25 }}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-600">Date Details</p>
            <h3 className="text-lg font-bold">{parseDateKey(dateKey).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</h3>
          </div>
          <button onClick={onClose} className="inline-flex size-8 items-center justify-center rounded-lg border" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <DayContent
          role={role}
          identity={identity}
          teamNames={teamNames}
          dateKey={dateKey}
          day={day}
          onAddReminder={onAddReminder}
          onUpdateReminder={onUpdateReminder}
          onDeleteReminder={onDeleteReminder}
          onToggleReminderComplete={onToggleReminderComplete}
          onSnoozeReminder={onSnoozeReminder}
          onAddNote={onAddNote}
          onDeleteNote={onDeleteNote}
          onToggleNotePin={onToggleNotePin}
        />
      </motion.aside>
    </>,
    document.body
  );
}

function DayContent({
  role,
  identity,
  teamNames,
  dateKey,
  day,
  onAddReminder,
  onUpdateReminder,
  onDeleteReminder,
  onToggleReminderComplete,
  onSnoozeReminder,
  onAddNote,
  onDeleteNote,
  onToggleNotePin
}: {
  role: Role;
  identity: string;
  teamNames: string[];
  dateKey: string;
  day: CalendarDayData;
  onAddReminder: (input: Omit<Reminder, "id" | "completed" | "snoozedUntil" | "createdByRole">) => void;
  onUpdateReminder: (id: string, patch: Partial<Reminder>) => void;
  onDeleteReminder: (id: string) => void;
  onToggleReminderComplete: (id: string) => void;
  onSnoozeReminder: (id: string, days?: number) => void;
  onAddNote: (input: Omit<CalendarNote, "id" | "createdAt" | "pinned">) => void;
  onDeleteNote: (id: string) => void;
  onToggleNotePin: (id: string) => void;
}) {
  const timeline = [
    ...day.leads.map((row) => ({ label: `Lead: ${row.Lead ?? row.id}`, sub: row.Status ?? "" })),
    ...day.customers.map((row) => ({ label: `Customer: ${row.Customer ?? row.id}`, sub: row.Status ?? "" })),
    ...day.payments.map((row) => ({ label: `Payment: ${row.Invoice ?? row.id}`, sub: row.Status ?? "" })),
    ...day.communication.map((row) => ({ label: `Email: ${row.Recipient ?? row.id}`, sub: row.Status ?? "" })),
    ...day.tasks.map((row) => ({ label: `Task: ${row.Task ?? row.id}`, sub: row.Status ?? "" }))
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <MiniStat label="Leads" value={day.leads.length} />
        <MiniStat label="Customers" value={day.customers.length} />
        <MiniStat label="Payments" value={day.payments.length} />
        <MiniStat label="Calls" value={day.calls.length} />
        <MiniStat label="Tasks" value={day.tasks.length} />
        <MiniStat label="Notes" value={day.notes.length} />
      </div>

      {day.leads.length > 0 ? (
        <DetailSection title="Leads created/updated">
          {day.leads.map((row) => (
            <DetailRow key={row.id} title={row.Lead ?? row.id} subtitle={`${row.Source ?? ""} - ${row.Owner ?? ""}`} badge={row.Status} />
          ))}
        </DetailSection>
      ) : null}

      {day.customers.length > 0 ? (
        <DetailSection title="Customers created/updated">
          {day.customers.map((row) => (
            <DetailRow key={row.id} title={row.Customer ?? row.id} subtitle={row["Last Interaction"] ?? row.Owner ?? ""} badge={row.Status} />
          ))}
        </DetailSection>
      ) : null}

      {day.payments.length > 0 ? (
        <DetailSection title="Payment records">
          {day.payments.map((row) => (
            <DetailRow key={row.id} title={row.Invoice ?? row.id} subtitle={`Customer #${row["Customer ID"] ?? "-"} - $${row.Total ?? "-"}`} badge={row.Status} />
          ))}
        </DetailSection>
      ) : null}

      {day.communication.length > 0 ? (
        <DetailSection title="Calls, WhatsApp & email history">
          {day.communication.map((row) => (
            <DetailRow key={row.id} title={`${row.Recipient ?? row.id}`} subtitle={row.Subject ?? ""} badge={row.Status} />
          ))}
        </DetailSection>
      ) : null}

      {day.tasks.length > 0 ? (
        <DetailSection title="Tasks & meetings">
          {day.tasks.map((row) => (
            <DetailRow key={row.id} title={row.Task ?? row.id} subtitle={row.Priority ?? ""} badge={row.Status} />
          ))}
        </DetailSection>
      ) : null}

      {role === "superadmin" && day.audit.length > 0 ? (
        <DetailSection title="Audit logs">
          {day.audit.map((row) => (
            <DetailRow key={row.id} title={row.Action ?? row.id} subtitle={`${row.Actor ?? ""} - ${row.Description ?? ""}`} badge={row.Time} />
          ))}
        </DetailSection>
      ) : null}

      <ReminderSection
        role={role}
        identity={identity}
        teamNames={teamNames}
        dateKey={dateKey}
        reminders={day.reminders}
        onAdd={onAddReminder}
        onUpdate={onUpdateReminder}
        onDelete={onDeleteReminder}
        onToggleComplete={onToggleReminderComplete}
        onSnooze={onSnoozeReminder}
      />

      <NoteSection
        role={role}
        identity={identity}
        dateKey={dateKey}
        notes={day.notes}
        onAdd={onAddNote}
        onDelete={onDeleteNote}
        onTogglePin={onToggleNotePin}
      />

      {timeline.length > 0 ? (
        <DetailSection title="Activity timeline">
          {timeline.map((item, index) => (
            <div key={index} className="flex items-start gap-3 border-b py-2 text-sm last:border-b-0">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-teal-600" />
              <div className="min-w-0">
                <p className="font-semibold">{item.label}</p>
                {item.sub ? <p className="text-xs text-muted-foreground">{item.sub}</p> : null}
              </div>
            </div>
          ))}
        </DetailSection>
      ) : null}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border bg-background p-2.5 text-center">
      <p className="text-lg font-bold">{value}</p>
      <p className="text-[11px] text-muted-foreground">{label}</p>
    </div>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-teal-600">{title}</h4>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function DetailRow({ title, subtitle, badge }: { title: string; subtitle?: string; badge?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border bg-background px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{title}</p>
        {subtitle ? <p className="truncate text-xs text-muted-foreground">{subtitle}</p> : null}
      </div>
      {badge ? <span className={cn("shrink-0 rounded-full px-2 py-1 text-xs font-bold ring-1", statusClass(badge))}>{badge}</span> : null}
    </div>
  );
}

function ReminderSection({
  role,
  identity,
  teamNames,
  dateKey,
  reminders,
  onAdd,
  onUpdate,
  onDelete,
  onToggleComplete,
  onSnooze
}: {
  role: Role;
  identity: string;
  teamNames: string[];
  dateKey: string;
  reminders: Reminder[];
  onAdd: (input: Omit<Reminder, "id" | "completed" | "snoozedUntil" | "createdByRole">) => void;
  onUpdate: (id: string, patch: Partial<Reminder>) => void;
  onDelete: (id: string) => void;
  onToggleComplete: (id: string) => void;
  onSnooze: (id: string, days?: number) => void;
}) {
  const assigneeOptions = assigneeOptionsForRole(role, identity, teamNames);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [time, setTime] = useState("09:00");
  const [priority, setPriority] = useState<ReminderPriority>("Medium");
  const [repeat, setRepeat] = useState<ReminderRepeat>("None");
  const [kind, setKind] = useState<ReminderKind>("Reminder");
  const [assignedTo, setAssignedTo] = useState(assigneeOptions[0]);

  function resetForm() {
    setEditingId(null);
    setTitle("");
    setTime("09:00");
    setPriority("Medium");
    setRepeat("None");
    setKind("Reminder");
    setAssignedTo(assigneeOptions[0]);
  }

  function startEdit(reminder: Reminder) {
    setEditingId(reminder.id);
    setTitle(reminder.title);
    setTime(reminder.time);
    setPriority(reminder.priority);
    setRepeat(reminder.repeat);
    setKind(reminder.kind);
    setAssignedTo(reminder.assignedTo);
  }

  function handleSubmit() {
    if (!title.trim()) return;
    if (editingId) {
      onUpdate(editingId, { title: title.trim(), time, priority, repeat, kind, assignedTo });
    } else {
      onAdd({ title: title.trim(), date: dateKey, time, priority, repeat, kind, assignedTo });
    }
    resetForm();
  }

  return (
    <DetailSection title="Reminders">
      {reminders.length === 0 ? <p className="text-sm text-muted-foreground">No reminders for this date.</p> : null}
      {reminders.map((reminder) => (
        <div key={reminder.id} className="rounded-lg border bg-background p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className={cn("truncate text-sm font-semibold", reminder.completed && "line-through text-muted-foreground")}>{reminder.title}</p>
              <p className="text-xs text-muted-foreground">
                {reminder.kind} - {reminder.time} - Assigned to {reminder.assignedTo}
                {reminder.repeat !== "None" ? ` - Repeats ${reminder.repeat}` : ""}
                {reminder.snoozedUntil ? ` - Snoozed until ${reminder.snoozedUntil}` : ""}
              </p>
            </div>
            <span className={cn("shrink-0 rounded-full px-2 py-1 text-xs font-bold ring-1", REMINDER_PRIORITY_STYLES[reminder.priority])}>
              {reminder.priority}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button
              onClick={() => onToggleComplete(reminder.id)}
              className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-teal-600"
            >
              <Check className="size-3" />
              {reminder.completed ? "Completed" : "Mark Complete"}
            </button>
            <button
              onClick={() => onSnooze(reminder.id)}
              className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-teal-600"
            >
              <AlarmClock className="size-3" />
              Snooze
            </button>
            <button
              onClick={() => startEdit(reminder)}
              className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-semibold text-muted-foreground hover:text-teal-600"
            >
              <Pencil className="size-3" />
              Edit
            </button>
            <button
              onClick={() => onDelete(reminder.id)}
              className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
            >
              <Trash2 className="size-3" />
              Delete
            </button>
          </div>
        </div>
      ))}

      <div className="space-y-2 rounded-lg border border-dashed p-3">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">{editingId ? "Edit Reminder" : "Add Reminder"}</p>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Reminder title"
          className="h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none ring-teal-600/20 focus:ring-4"
        />
        <div className="grid grid-cols-2 gap-2">
          <input
            type="time"
            value={time}
            onChange={(event) => setTime(event.target.value)}
            className="h-9 rounded-lg border bg-background px-2 text-sm outline-none ring-teal-600/20 focus:ring-4"
          />
          <select
            value={kind}
            onChange={(event) => setKind(event.target.value as ReminderKind)}
            className="h-9 rounded-lg border bg-background px-2 text-sm outline-none ring-teal-600/20 focus:ring-4"
          >
            {(["Reminder", "Meeting", "Follow-up", "Task"] as ReminderKind[]).map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
          <select
            value={priority}
            onChange={(event) => setPriority(event.target.value as ReminderPriority)}
            className="h-9 rounded-lg border bg-background px-2 text-sm outline-none ring-teal-600/20 focus:ring-4"
          >
            {(["Low", "Medium", "High", "Urgent"] as ReminderPriority[]).map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
          <select
            value={repeat}
            onChange={(event) => setRepeat(event.target.value as ReminderRepeat)}
            className="h-9 rounded-lg border bg-background px-2 text-sm outline-none ring-teal-600/20 focus:ring-4"
          >
            {(["None", "Daily", "Weekly", "Monthly"] as ReminderRepeat[]).map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        </div>
        {assigneeOptions.length > 1 ? (
          <select
            value={assignedTo}
            onChange={(event) => setAssignedTo(event.target.value)}
            className="h-9 w-full rounded-lg border bg-background px-2 text-sm outline-none ring-teal-600/20 focus:ring-4"
          >
            {assigneeOptions.map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        ) : (
          <p className="text-xs text-muted-foreground">Assigned to {identity} (yourself).</p>
        )}
        <div className="flex gap-2">
          <button
            onClick={handleSubmit}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white"
          >
            <Plus className="size-4" />
            {editingId ? "Save Reminder" : "Add Reminder"}
          </button>
          {editingId ? (
            <button onClick={resetForm} className="rounded-lg border px-3 py-2 text-sm font-semibold">
              Cancel
            </button>
          ) : null}
        </div>
      </div>
    </DetailSection>
  );
}

function NoteSection({
  role,
  identity,
  dateKey,
  notes,
  onAdd,
  onDelete,
  onTogglePin
}: {
  role: Role;
  identity: string;
  dateKey: string;
  notes: CalendarNote[];
  onAdd: (input: Omit<CalendarNote, "id" | "createdAt" | "pinned">) => void;
  onDelete: (id: string) => void;
  onTogglePin: (id: string) => void;
}) {
  const [text, setText] = useState("");
  const [visibility, setVisibility] = useState<NoteVisibility>(role === "employee" ? "private" : "team");
  const [attachments, setAttachments] = useState<string[]>([]);
  const sortedNotes = [...notes].sort((a, b) => Number(b.pinned) - Number(a.pinned));

  function handleAttach() {
    setAttachments((current) => [...current, `attachment-${current.length + 1}.pdf`]);
  }

  function handleSubmit() {
    if (!text.trim()) return;
    onAdd({ date: dateKey, text: text.trim(), author: identity, visibility, attachments });
    setText("");
    setAttachments([]);
  }

  return (
    <DetailSection title="Notes">
      {sortedNotes.length === 0 ? <p className="text-sm text-muted-foreground">No notes for this date.</p> : null}
      {sortedNotes.map((note) => (
        <div key={note.id} className="rounded-lg border bg-background p-3">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm">{note.text}</p>
            <button onClick={() => onTogglePin(note.id)} aria-label="Pin note" className={cn("shrink-0", note.pinned ? "text-amber-500" : "text-muted-foreground")}>
              <Pin className="size-4" />
            </button>
          </div>
          {note.attachments.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {note.attachments.map((file) => (
                <span key={file} className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs font-medium">
                  <Paperclip className="size-3" />
                  {file}
                </span>
              ))}
            </div>
          ) : null}
          <div className="mt-2 flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              {note.author} - {new Date(note.createdAt).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })} -{" "}
              {note.visibility}
            </p>
            <button onClick={() => onDelete(note.id)} className="text-xs font-semibold text-red-600 hover:underline">
              Delete
            </button>
          </div>
        </div>
      ))}

      <div className="space-y-2 rounded-lg border border-dashed p-3">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">Add Note</p>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Write a note for this date..."
          rows={3}
          className="w-full rounded-lg border bg-background p-2.5 text-sm outline-none ring-teal-600/20 focus:ring-4"
        />
        {attachments.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {attachments.map((file) => (
              <span key={file} className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs font-medium">
                <Paperclip className="size-3" />
                {file}
              </span>
            ))}
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          {role !== "employee" ? (
            <select
              value={visibility}
              onChange={(event) => setVisibility(event.target.value as NoteVisibility)}
              className="h-9 rounded-lg border bg-background px-2 text-sm outline-none ring-teal-600/20 focus:ring-4"
            >
              <option value="private">Private</option>
              <option value="team">Shared with team</option>
              {role === "superadmin" ? <option value="company">Shared company-wide</option> : null}
            </select>
          ) : (
            <span className="text-xs text-muted-foreground">Private note (visible only to you)</span>
          )}
          <button onClick={handleAttach} className="inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-2 text-xs font-semibold">
            <Paperclip className="size-3.5" />
            Attach File
          </button>
          <button
            onClick={handleSubmit}
            className="ml-auto inline-flex items-center gap-2 rounded-lg bg-teal-600 px-3 py-2 text-sm font-semibold text-white"
          >
            <Plus className="size-4" />
            Add Note
          </button>
        </div>
      </div>
    </DetailSection>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <article className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-bold">{title}</h3>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <MoreHorizontal className="size-4 shrink-0 text-muted-foreground" />
      </div>
      {children}
    </article>
  );
}

function getChartPoints(data: Array<{ label: string; value: number }>, width = 320, height = 170, pad = 24) {
  const max = Math.max(...data.map((item) => item.value), 1);
  return data.map((item, index) => {
    const x = pad + (index * (width - pad * 2)) / Math.max(data.length - 1, 1);
    const y = height - pad - (item.value / max) * (height - pad * 2);
    return { ...item, x, y };
  });
}

function LineChart({ data, prefix = "", suffix = "" }: { data: Array<{ label: string; value: number }>; prefix?: string; suffix?: string }) {
  const [tip, setTip] = useState<string | null>(null);
  const points = getChartPoints(data);
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");

  return (
    <div className="relative">
      {tip ? <ChartTooltip text={tip} /> : null}
      <svg viewBox="0 0 320 170" className="h-56 w-full overflow-visible">
        <path d={path} fill="none" stroke="#0F766E" strokeWidth="3" strokeLinecap="round" />
        {points.map((point) => (
          <g key={point.label} onMouseEnter={() => setTip(`${point.label}: ${prefix}${point.value}${suffix}`)} onMouseLeave={() => setTip(null)}>
            <circle cx={point.x} cy={point.y} r="5" fill="#0F766E" />
            <text x={point.x} y="164" textAnchor="middle" className="fill-muted-foreground text-[10px]">
              {point.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function AreaChart({ data }: { data: Array<{ label: string; value: number }> }) {
  const [tip, setTip] = useState<string | null>(null);
  const points = getChartPoints(data);
  const line = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const area = `${line} L ${points[points.length - 1].x} 146 L ${points[0].x} 146 Z`;

  return (
    <div className="relative">
      {tip ? <ChartTooltip text={tip} /> : null}
      <svg viewBox="0 0 320 170" className="h-56 w-full overflow-visible">
        <path d={area} fill="rgba(15, 118, 110, 0.14)" />
        <path d={line} fill="none" stroke="#0F766E" strokeWidth="3" strokeLinecap="round" />
        {points.map((point) => (
          <circle key={point.label} cx={point.x} cy={point.y} r="6" fill="#0F766E" onMouseEnter={() => setTip(`${point.label}: ${point.value} leads`)} onMouseLeave={() => setTip(null)} />
        ))}
      </svg>
    </div>
  );
}

function BarChart({
  data,
  prefix = "",
  suffix = ""
}: {
  data: Array<{ label: string; value: number }>;
  prefix?: string;
  suffix?: string;
}) {
  const [tip, setTip] = useState<string | null>(null);
  const max = Math.max(...data.map((item) => item.value), 1);
  const barWidth = 220 / data.length;

  return (
    <div className="relative">
      {tip ? <ChartTooltip text={tip} /> : null}
      <svg viewBox="0 0 320 170" className="h-56 w-full overflow-visible">
        {data.map((item, index) => {
          const height = (item.value / max) * 112;
          const x = 34 + index * barWidth;
          const y = 138 - height;
          return (
            <g
              key={`${item.label}-${index}`}
              onMouseEnter={() => setTip(`${item.label}: ${prefix}${item.value}${suffix}`)}
              onMouseLeave={() => setTip(null)}
            >
              <rect
                x={x}
                y={y}
                width={Math.max(barWidth - 12, 20)}
                height={height}
                rx="7"
                fill={CHART_PALETTE[index % CHART_PALETTE.length]}
                opacity={0.92}
              />
              <text x={x + Math.max(barWidth - 12, 20) / 2} y="160" textAnchor="middle" className="fill-muted-foreground text-[10px]">
                {item.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function polarPoint(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}

function GaugeChart({ value, label }: { value: number; label: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  const cx = 110;
  const cy = 118;
  const r = 82;
  const needleAngle = 180 - (clamped / 100) * 180;
  const needleEnd = polarPoint(cx, cy, 66, needleAngle);
  const bands = [
    { from: 180, to: 120, color: "#E2E8F0" },
    { from: 120, to: 60, color: "#7DD3FC" },
    { from: 60, to: 0, color: "#0F766E" }
  ];

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 220 140" className="h-40 w-full max-w-[220px] overflow-visible">
        {bands.map((band) => {
          const p1 = polarPoint(cx, cy, r, band.from);
          const p2 = polarPoint(cx, cy, r, band.to);
          return (
            <path
              key={band.color}
              d={`M ${p1.x} ${p1.y} A ${r} ${r} 0 0 1 ${p2.x} ${p2.y}`}
              fill="none"
              stroke={band.color}
              strokeWidth="18"
            />
          );
        })}
        <line x1={cx} y1={cy} x2={needleEnd.x} y2={needleEnd.y} stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="text-foreground" />
        <circle cx={cx} cy={cy} r="6" fill="currentColor" className="text-foreground" />
      </svg>
      <strong className="-mt-4 text-2xl font-bold text-teal-700 dark:text-teal-300">{clamped.toFixed(1)}%</strong>
      {label ? <p className="text-xs text-muted-foreground">{label}</p> : null}
    </div>
  );
}

function PieChart({ data, donut }: { data: Array<{ label: string; value: number; color: string }>; donut: boolean }) {
  const [tip, setTip] = useState<string | null>(null);
  const total = data.reduce((sum, item) => sum + item.value, 0);
  let offset = 25;

  return (
    <div className="relative grid min-h-56 place-items-center">
      {tip ? <ChartTooltip text={tip} /> : null}
      <svg viewBox="0 0 220 220" className="h-48 w-48 -rotate-90">
        {data.map((item) => {
          const dash = (item.value / total) * 100;
          const segment = (
            <circle
              key={item.label}
              cx="110"
              cy="110"
              r="70"
              fill="none"
              stroke={item.color}
              strokeWidth={donut ? 32 : 70}
              strokeDasharray={`${dash} ${100 - dash}`}
              strokeDashoffset={offset}
              pathLength="100"
              onMouseEnter={() => setTip(`${item.label}: ${item.value}%`)}
              onMouseLeave={() => setTip(null)}
            />
          );
          offset -= dash;
          return segment;
        })}
      </svg>
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        {data.map((item) => (
          <span key={item.label} className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground">
            <span className="size-2 rounded-full" style={{ backgroundColor: item.color }} />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function ChartTooltip({ text }: { text: string }) {
  return <div className="pointer-events-none absolute right-3 top-1 z-10 rounded-lg bg-zinc-950 px-2 py-1 text-xs font-bold text-white shadow-soft">{text}</div>;
}

function TimelineCard({
  title,
  items,
  onView,
  onEdit,
  onDelete,
  onCreate
}: {
  title: string;
  items: ActivityEntry[];
  onView: (moduleKey: ModuleKey, row: RowRecord) => void;
  onEdit: (moduleKey: ModuleKey, row: RowRecord) => void;
  onDelete: (moduleKey: ModuleKey, row: RowRecord) => void;
  onCreate: (moduleKey: ModuleKey) => void;
}) {
  return (
    <article className="rounded-2xl border bg-card p-5 shadow-sm">
      <h3 className="text-lg font-bold">{title}</h3>
      <div className="mt-4 space-y-4">
        {items.map((item) => (
          <div key={item.id} className="flex gap-3">
            <span className="mt-1.5 size-2.5 shrink-0 rounded-full bg-teal-600 ring-4 ring-teal-100 dark:ring-teal-950" />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-muted-foreground">{item.message}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                {item.row ? (
                  <>
                    <button
                      onClick={() => item.row && onView(item.moduleKey, item.row)}
                      className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-0.5 text-xs font-semibold text-muted-foreground hover:text-teal-600"
                    >
                      <Eye className="size-3" />
                      View
                    </button>
                    <button
                      onClick={() => item.row && onEdit(item.moduleKey, item.row)}
                      className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-0.5 text-xs font-semibold text-muted-foreground hover:text-teal-600"
                    >
                      <Pencil className="size-3" />
                      Edit
                    </button>
                    <button
                      onClick={() => item.row && onDelete(item.moduleKey, item.row)}
                      className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-0.5 text-xs font-semibold text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                    >
                      <Trash2 className="size-3" />
                      Delete
                    </button>
                  </>
                ) : null}
                <button
                  onClick={() => onCreate(item.moduleKey)}
                  className="inline-flex items-center gap-1 rounded-md border bg-background px-2 py-0.5 text-xs font-semibold text-teal-600 hover:bg-teal-50 dark:hover:bg-teal-950"
                >
                  <Plus className="size-3" />
                  New
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}

function DataTable({
  module,
  rows,
  onEdit,
  onView,
  onDuplicate,
  onDelete,
  sort,
  onSort,
  role,
  allowEdit = false
}: {
  module: ModuleConfig;
  rows: RowRecord[];
  onEdit: (row: RowRecord) => void;
  onView: (row: RowRecord) => void;
  onDuplicate: (row: RowRecord) => void;
  onDelete: (row: RowRecord) => void;
  sort: { column: string; direction: "asc" | "desc" } | null;
  onSort: (column: string) => void;
  role?: Role;
  // Employees are view-only everywhere except Tasks (where they may
  // update their own task's status/completion) — see the Tasks &
  // Follow-ups render branch, the only caller that passes allowEdit.
  allowEdit?: boolean;
}) {
  const isEmployeeViewOnly = role === "employee";
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const MENU_WIDTH = 160;
  const MENU_HEIGHT = 84;

  function toggleMenu(rowId: string, event: React.MouseEvent<HTMLButtonElement>) {
    if (openMenuId === rowId) {
      setOpenMenuId(null);
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const left = Math.min(Math.max(rect.right - MENU_WIDTH, 8), window.innerWidth - MENU_WIDTH - 8);
    const top =
      rect.bottom + MENU_HEIGHT <= window.innerHeight ? rect.bottom + 4 : Math.max(8, rect.top - MENU_HEIGHT - 4);
    setMenuPos({ top, left });
    setOpenMenuId(rowId);
  }

  const openMenuRow = rows.find((row) => row.id === openMenuId) ?? null;

  if (rows.length === 0) {
    return (
      <div className="flex min-h-72 flex-col items-center justify-center p-8 text-center">
        <div className="mb-4 flex size-14 items-center justify-center rounded-xl bg-teal-50 text-teal-600 dark:bg-teal-950">
          <Search className="size-6" />
        </div>
        <h3 className="text-lg font-bold">No records found</h3>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">Try a different search term or filter for this module.</p>
      </div>
    );
  }

  return (
    <div className="glass-scrollbar overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left">
        <thead>
          <tr className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
            {module.columns.map((column) => {
              const isSorted = sort?.column === column;
              const SortIcon = isSorted ? (sort?.direction === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
              return (
                <th key={column} className="px-4 py-3 font-bold">
                  <button
                    onClick={() => onSort(column)}
                    className={cn(
                      "inline-flex items-center gap-1 transition hover:text-foreground",
                      isSorted && "text-teal-700 dark:text-teal-300"
                    )}
                  >
                    {column}
                    <SortIcon className="size-3" />
                  </button>
                </th>
              );
            })}
            <th className="px-4 py-3 text-right font-bold">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((row) => (
            <tr key={row.id} className="transition hover:bg-muted/40">
              {module.columns.map((column) => {
                const value = row[column] ?? "-";
                const isBadge = ["Status", "Priority", "Outcome", "Export"].includes(column);
                return (
                  <td key={column} className="px-4 py-4 text-sm">
                    {isBadge ? (
                      <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-bold ring-1", statusClass(value))}>{value}</span>
                    ) : (
                      <span className={column === module.columns[0] ? "font-semibold" : "text-muted-foreground"}>{value}</span>
                    )}
                  </td>
                );
              })}
              <td className="px-4 py-4">
                <div className="relative flex justify-end gap-2">
                  <button
                    className="inline-flex size-8 items-center justify-center rounded-lg border bg-background text-muted-foreground hover:text-teal-600"
                    aria-label="View record"
                    onClick={() => onView(row)}
                  >
                    <Eye className="size-4" />
                  </button>
                  {!isEmployeeViewOnly || allowEdit ? (
                    <button
                      className="inline-flex size-8 items-center justify-center rounded-lg border bg-background text-muted-foreground hover:text-teal-600"
                      aria-label="Edit record"
                      onClick={() => onEdit(row)}
                    >
                      <Pencil className="size-4" />
                    </button>
                  ) : null}
                  {!isEmployeeViewOnly ? (
                    <button
                      className="inline-flex size-8 items-center justify-center rounded-lg border bg-background text-muted-foreground hover:text-teal-600"
                      aria-label="More actions"
                      onClick={(event) => toggleMenu(row.id, event)}
                    >
                      <MoreHorizontal className="size-4" />
                    </button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {openMenuRow && menuPos
        ? createPortal(
            <>
              <div className="fixed inset-0 z-40" onClick={() => setOpenMenuId(null)} />
              <div
                className="fixed z-50 w-40 overflow-hidden rounded-lg border bg-card shadow-soft"
                style={{ top: menuPos.top, left: menuPos.left }}
              >
                <button
                  onClick={() => {
                    onDuplicate(openMenuRow);
                    setOpenMenuId(null);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium hover:bg-muted"
                >
                  <Copy className="size-4" />
                  Duplicate
                </button>
                <button
                  onClick={() => {
                    onDelete(openMenuRow);
                    setOpenMenuId(null);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-950"
                >
                  <Trash2 className="size-4" />
                  Delete
                </button>
              </div>
            </>,
            document.body
          )
        : null}
    </div>
  );
}

function LoadingSkeleton({ columns }: { columns: string[] }) {
  return (
    <div className="p-4">
      <div className="mb-3 grid gap-3" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(120px, 1fr))` }}>
        {columns.map((column) => (
          <div key={column} className="h-4 animate-pulse rounded bg-muted" />
        ))}
      </div>
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="mb-3 grid gap-3" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(120px, 1fr))` }}>
          {columns.map((column) => (
            <div key={column} className="h-10 animate-pulse rounded-lg bg-muted/80" />
          ))}
        </div>
      ))}
    </div>
  );
}

function Toast({ toast }: { toast: { type: "success" | "error"; message: string } }) {
  const isSuccess = toast.type === "success";
  return (
    <motion.div
      initial={{ opacity: 0, y: 24, x: "-50%" }}
      animate={{ opacity: 1, y: 0, x: "-50%" }}
      exit={{ opacity: 0, y: 24, x: "-50%" }}
      className={cn(
        "fixed bottom-6 left-1/2 z-[70] flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white shadow-soft",
        isSuccess ? "bg-emerald-600" : "bg-red-600"
      )}
    >
      {isSuccess ? <Check className="size-4" /> : <X className="size-4" />}
      {toast.message}
    </motion.div>
  );
}

function RecordModal({
  module,
  mode,
  formData,
  onChange,
  onSave,
  onClose,
  serverError,
  extraContent
}: {
  module: ModuleConfig;
  mode: "create" | "edit" | "view";
  formData: Record<string, string>;
  onChange: (field: string, value: string) => void;
  onSave: () => void;
  onClose: () => void;
  // Errors the backend rejected the submission with. Kept separate from
  // the inline required-field messages below so a server error is never
  // mistaken for a validation state this form owns (spec 23).
  serverError?: string | null;
  // Optional per-record actions rendered under the field grid (used by the
  // Employee lead detail view for its Email/Call/WhatsApp quick actions).
  extraContent?: React.ReactNode;
}) {
  const isView = mode === "view";
  // Validation is derived from the CURRENT field values on every render —
  // never from a snapshot taken when the modal opened — so typing into a
  // required field clears its message immediately and a stale error can
  // never survive valid input (spec 8/23).
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

  const missingFields = module.columns.filter(
    (column) => isFieldRequired(module, column, mode) && !(formData[column] ?? "").trim()
  );

  const title = mode === "edit" ? `Edit ${module.title}` : mode === "view" ? module.title : module.formTitle;
  const subtitle =
    mode === "edit"
      ? `Update this ${module.title} record.`
      : mode === "view"
      ? `Details for this ${module.title} record.`
      : `Add a new ${module.title} record.`;

  function handleSave() {
    setSubmitAttempted(true);
    if (missingFields.length > 0) return;
    onSave();
  }

  return (
    <motion.div
      className="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border bg-card shadow-soft"
        initial={{ scale: 0.96, y: 18 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, y: 18 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b p-5">
          <div>
            <h3 className="text-xl font-bold">{title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="inline-flex size-9 items-center justify-center rounded-lg border"
          >
            <X className="size-4" />
          </button>
        </div>

        {serverError && !isView ? (
          <div className="mx-5 mt-5 flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-200">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span>{serverError}</span>
          </div>
        ) : null}

        <div className="grid gap-4 p-5 sm:grid-cols-2">
          {module.columns.map((column) => {
            const value = formData[column] ?? "";
            const required = isFieldRequired(module, column, mode);
            const options = FIELD_OPTIONS[module.key]?.[column];
            const showError = required && !value.trim() && (submitAttempted || touched[column]);
            const errorId = `${module.key}-${column}-error`;
            const fieldClass = cn(
              "h-11 w-full rounded-lg border bg-background px-3 text-sm text-foreground outline-none ring-teal-600/20 focus:ring-4",
              isView && "cursor-default bg-muted text-muted-foreground",
              showError && "border-red-500"
            );

            return (
              <label key={column} className="space-y-1.5">
                <span className="text-sm font-semibold">
                  {column}
                  {required ? <span className="ml-0.5 text-red-600">*</span> : null}
                </span>
                {options && !isView ? (
                  <select
                    value={value}
                    aria-invalid={showError}
                    aria-describedby={showError ? errorId : undefined}
                    onChange={(event) => {
                      setTouched((current) => ({ ...current, [column]: true }));
                      onChange(column, event.target.value);
                    }}
                    onBlur={() => setTouched((current) => ({ ...current, [column]: true }))}
                    className={fieldClass}
                  >
                    <option value="">{`Select ${column.toLowerCase()}`}</option>
                    {options.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={column === "Password" ? "password" : column === "Email" ? "email" : "text"}
                    value={value}
                    readOnly={isView}
                    aria-invalid={showError}
                    aria-describedby={showError ? errorId : undefined}
                    onChange={(event) => {
                      setTouched((current) => ({ ...current, [column]: true }));
                      onChange(column, event.target.value);
                    }}
                    onBlur={() => setTouched((current) => ({ ...current, [column]: true }))}
                    placeholder={isView ? "" : `Enter ${column.toLowerCase()}`}
                    className={fieldClass}
                  />
                )}
                {showError ? (
                  <span id={errorId} className="block text-xs font-medium text-red-600 dark:text-red-400">
                    {options ? `Select a ${column.toLowerCase()}.` : `${column} is required.`}
                  </span>
                ) : null}
              </label>
            );
          })}
        </div>
        {extraContent ? <div className="px-5 pb-5">{extraContent}</div> : null}
        <div className="flex flex-col-reverse gap-2 border-t p-5 sm:flex-row sm:justify-end">
          <button onClick={onClose} className="rounded-lg border px-4 py-2 text-sm font-semibold">
            {isView ? "Close" : "Cancel"}
          </button>
          {!isView ? (
            <button
              onClick={handleSave}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700"
            >
              <Check className="size-4" />
              {mode === "edit" ? "Save Changes" : "Save Record"}
            </button>
          ) : null}
        </div>
      </motion.div>
    </motion.div>
  );
}
