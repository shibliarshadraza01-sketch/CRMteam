"use client";

import {
  Activity,
  AlarmClock,
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
  Copy,
  Download,
  Eye,
  EyeOff,
  FileSpreadsheet,
  Filter,
  History,
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
  Pin,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Star,
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
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

type ModuleKey =
  | "users"
  | "team"
  | "dashboard"
  | "calendar"
  | "leads"
  | "customers"
  | "payments"
  | "communication"
  | "tasks"
  | "reports"
  | "audit"
  | "settings";

type Role = "superadmin" | "manager" | "employee";

type ModuleConfig = {
  key: ModuleKey;
  title: string;
  subtitle: string;
  icon: React.ElementType;
  accent: string;
  features: string[];
  stats: Array<{ label: string; value: string; change: string }>;
  columns: string[];
  rows: Array<Record<string, string>>;
  filters: string[];
  actions: Array<{ label: string; icon: React.ElementType; primary?: boolean }>;
  formTitle: string;
  formFields: Array<{ label: string; type: "text" | "email" | "select" | "date" | "number"; placeholder: string }>;
  chart?: { title: string; subtitle: string; column: string; mode: "count" | "sum"; labelColumn?: string; prefix?: string; suffix?: string };
};

type RowRecord = Record<string, string> & { id: string };
type RecordsByModule = Record<ModuleKey, RowRecord[]>;
type ToastState = { type: "success" | "error"; message: string } | null;
type ActivityEntry = { id: string; message: string; moduleKey: ModuleKey; row: RowRecord | null };

const modules: ModuleConfig[] = [
  {
    key: "reports",
    title: "Reports & Dashboard",
    subtitle: "Monitor full company performance, revenue, lead conversion rates, and export reports to CSV or Excel.",
    icon: FileSpreadsheet,
    accent: "from-teal-700 to-emerald-500",
    features: [
      "Full company dashboard for all team performance",
      "Revenue reports and lead conversion rates",
      "Export reports as CSV or Excel"
    ],
    stats: [
      { label: "Team performance", value: "91%", change: "+6.4%" },
      { label: "Lead conversion", value: "18.7%", change: "+2.1%" },
      { label: "Revenue report", value: "$842K", change: "Company total" },
      { label: "Exports", value: "38", change: "CSV and Excel" }
    ],
    columns: ["Report", "Scope", "Metric", "Period", "Export"],
    rows: [
      { Report: "Company dashboard", Scope: "All teams", Metric: "Performance 91%", Period: "July", Export: "CSV" },
      { Report: "Revenue", Scope: "Company", Metric: "$842K", Period: "Q3", Export: "Excel" },
      { Report: "Lead conversion", Scope: "All owners", Metric: "18.7%", Period: "Monthly", Export: "CSV" },
      { Report: "Manager scorecard", Scope: "Managers", Metric: "Pipeline health", Period: "Weekly", Export: "Excel" }
    ],
    filters: ["All reports", "Revenue", "Conversion", "Team performance", "CSV", "Excel"],
    actions: [
      { label: "Export CSV", icon: Download, primary: true },
      { label: "Export Excel", icon: FileSpreadsheet },
      { label: "Refresh Report", icon: RefreshCw }
    ],
    formTitle: "Generate Report",
    formFields: [
      { label: "Report type", type: "select", placeholder: "Revenue / Conversion / Performance" },
      { label: "Date range", type: "select", placeholder: "This month / Quarter / Custom" },
      { label: "Export format", type: "select", placeholder: "CSV / Excel" },
      { label: "Recipient email", type: "email", placeholder: "admin@company.com" }
    ]
  },
  {
    key: "team",
    title: "Team Management",
    subtitle: "View your team's employees, assign or reassign leads, and track employee performance.",
    icon: Users,
    accent: "from-teal-700 to-indigo-500",
    features: [
      "View employees on your team",
      "Assign or reassign leads to your employees",
      "Track employee performance"
    ],
    stats: [
      { label: "Team members", value: "5", change: "1 pending invite" },
      { label: "Leads assigned", value: "117", change: "This month" },
      { label: "Avg. performance", value: "83.6%", change: "+4.1%" },
      { label: "Top performer", value: "Aarav", change: "92% completion" }
    ],
    columns: ["Employee", "Role", "Leads Assigned", "Performance", "Status"],
    rows: [
      { Employee: "Aarav Mehta", Role: "Employee", "Leads Assigned": "32", Performance: "92%", Status: "Active" },
      { Employee: "Nisha Rao", Role: "Employee", "Leads Assigned": "27", Performance: "87%", Status: "Active" },
      { Employee: "Kabir Sethi", Role: "Employee", "Leads Assigned": "19", Performance: "79%", Status: "Active" },
      { Employee: "Zoya Khan", Role: "Employee", "Leads Assigned": "24", Performance: "84%", Status: "Invited" },
      { Employee: "Maya Iyer", Role: "Employee", "Leads Assigned": "15", Performance: "76%", Status: "Active" }
    ],
    filters: ["All employees", "Active", "Invited", "High performers"],
    actions: [
      { label: "Assign Lead", icon: UserCheck, primary: true },
      { label: "Reassign Lead", icon: RefreshCw },
      { label: "View Performance", icon: Eye }
    ],
    chart: {
      title: "Employee Performance",
      subtitle: "Completion score per team member",
      column: "Performance",
      mode: "sum",
      labelColumn: "Employee",
      suffix: "%"
    },
    formTitle: "Assign or Reassign Lead",
    formFields: [
      { label: "Employee", type: "select", placeholder: "Select team member" },
      { label: "Lead", type: "select", placeholder: "Select lead to assign" },
      { label: "Priority", type: "select", placeholder: "High / Medium / Low" },
      { label: "Note", type: "text", placeholder: "Assignment note" }
    ]
  },
  {
    key: "dashboard",
    title: "My Dashboard",
    subtitle: "Track your assigned leads, customers, tasks, and personal performance.",
    icon: Activity,
    accent: "from-teal-700 to-sky-500",
    features: [
      "Personal performance dashboard",
      "Assigned lead status overview",
      "Pending follow-ups and task summary"
    ],
    stats: [
      { label: "My Leads", value: "18", change: "5 new this week" },
      { label: "My Customers", value: "6", change: "2 active" },
      { label: "My Revenue", value: "$12.4K", change: "Collected to date" },
      { label: "My Conversion Rate", value: "22.0%", change: "+3.1%" }
    ],
    columns: ["Item", "Type", "Status", "Updated"],
    rows: [
      { Item: "Priya Sharma", Type: "Lead", Status: "Hot", Updated: "Today" },
      { Item: "Acme Learning", Type: "Customer", Status: "Active", Updated: "Yesterday" },
      { Item: "Call hot leads", Type: "Task", Status: "Open", Updated: "Today" },
      { Item: "Payment follow-up", Type: "Follow-up", Status: "Scheduled", Updated: "Aug 03" }
    ],
    filters: ["All items", "Leads", "Customers", "Tasks", "Follow-ups"],
    actions: [
      { label: "Export CSV", icon: Download, primary: true },
      { label: "Refresh Report", icon: RefreshCw }
    ],
    chart: { title: "My Activity Overview", subtitle: "Status mix across my leads, customers, and tasks", column: "Type", mode: "count" },
    formTitle: "Log Personal Activity",
    formFields: [
      { label: "Item", type: "text", placeholder: "Lead, customer, or task name" },
      { label: "Type", type: "select", placeholder: "Lead / Customer / Task / Follow-up" },
      { label: "Status", type: "select", placeholder: "Current status" },
      { label: "Note", type: "text", placeholder: "Add a note" }
    ]
  },
  {
    key: "calendar",
    title: "Smart Calendar",
    subtitle: "Month, week, and day views with reminders, notes, and a full activity timeline for every date.",
    icon: CalendarDays,
    accent: "from-teal-700 to-violet-500",
    features: [
      "Month, week, and day calendar views",
      "Per-date activity previews for leads, customers, calls, tasks, and reminders",
      "Role-based reminders and notes with priorities and repeats"
    ],
    stats: [
      { label: "Today's Events", value: "-", change: "Live" },
      { label: "This Week", value: "-", change: "Live" },
      { label: "Overdue Reminders", value: "-", change: "Live" },
      { label: "Pinned Notes", value: "-", change: "Live" }
    ],
    columns: ["Event", "Type", "Date", "Priority"],
    rows: [{ Event: "Team pipeline review", Type: "Meeting", Date: "Today", Priority: "Medium" }],
    filters: ["All events"],
    actions: [{ label: "Refresh Report", icon: RefreshCw }],
    formTitle: "Add Calendar Event",
    formFields: [
      { label: "Title", type: "text", placeholder: "Event title" },
      { label: "Date", type: "date", placeholder: "Choose date" },
      { label: "Priority", type: "select", placeholder: "Low / Medium / High / Urgent" },
      { label: "Note", type: "text", placeholder: "Add a note" }
    ]
  },
  {
    key: "users",
    title: "User Management",
    subtitle: "Create, invite, activate, deactivate, assign roles, and set user permissions.",
    icon: UserCog,
    accent: "from-teal-700 to-rose-500",
    features: [
      "Create new Manager and Employee users",
      "Invite users by sending email invite links",
      "Change any user's role",
      "Activate or deactivate users",
      "Set every user's permissions, including what Managers can and cannot see"
    ],
    stats: [
      { label: "Total users", value: "248", change: "+18 this month" },
      { label: "Active accounts", value: "231", change: "93.1% active" },
      { label: "Pending invites", value: "12", change: "4 expiring soon" },
      { label: "Permission sets", value: "17", change: "6 manager views" }
    ],
    columns: ["Name", "Role", "Email", "Status", "Permissions"],
    rows: [
      { Name: "Aarav Mehta", Role: "Manager", Email: "aarav@qualifylearn.com", Status: "Active", Permissions: "Leads, Customers, Tasks" },
      { Name: "Nisha Rao", Role: "Employee", Email: "nisha@qualifylearn.com", Status: "Invited", Permissions: "Assigned leads only" },
      { Name: "Kabir Sethi", Role: "Manager", Email: "kabir@qualifylearn.com", Status: "Inactive", Permissions: "Payments hidden" },
      { Name: "Zoya Khan", Role: "Employee", Email: "zoya@qualifylearn.com", Status: "Active", Permissions: "Calls, WhatsApp, Follow-ups" }
    ],
    filters: ["All roles", "Manager", "Employee", "Active", "Invited", "Inactive"],
    actions: [
      { label: "Create User", icon: Plus, primary: true },
      { label: "Send Invite", icon: Send },
      { label: "Permissions", icon: LockKeyhole }
    ],
    chart: { title: "User Status Breakdown", subtitle: "Active, invited, and inactive accounts", column: "Status", mode: "count" },
    formTitle: "Create or Invite User",
    formFields: [
      { label: "Full name", type: "text", placeholder: "Manager or employee name" },
      { label: "Work email", type: "email", placeholder: "name@company.com" },
      { label: "Role", type: "select", placeholder: "Manager / Employee" },
      { label: "Permission profile", type: "select", placeholder: "Choose what this user can see" }
    ]
  },
  {
    key: "leads",
    title: "Leads - Full Access",
    subtitle: "View every lead, assign ownership, import files, capture Meta leads, update status, and merge duplicates.",
    icon: Sparkles,
    accent: "from-teal-700 to-orange-500",
    features: [
      "View all leads from any employee or manager",
      "Assign leads to any employee or manager",
      "Bulk import leads from CSV or Excel",
      "View auto-captured leads from Meta Lead Ads",
      "Change lead status: new -> hot -> warm -> cold -> converted",
      "Detect and merge duplicate leads"
    ],
    stats: [
      { label: "All leads", value: "4,892", change: "+426 this week" },
      { label: "Meta captured", value: "681", change: "Auto sync on" },
      { label: "Hot leads", value: "316", change: "+11.4%" },
      { label: "Duplicates", value: "28", change: "Ready to merge" }
    ],
    columns: ["Lead", "Source", "Owner", "Status", "Duplicate"],
    rows: [
      { Lead: "Priya Sharma", Source: "Meta Lead Ads", Owner: "Aarav Mehta", Status: "Hot", Duplicate: "No" },
      { Lead: "Rahul Verma", Source: "CSV Import", Owner: "Unassigned", Status: "New", Duplicate: "Possible" },
      { Lead: "Maya Iyer", Source: "Website", Owner: "Nisha Rao", Status: "Warm", Duplicate: "No" },
      { Lead: "Omar Ali", Source: "Referral", Owner: "Kabir Sethi", Status: "Converted", Duplicate: "Merged" }
    ],
    filters: ["All owners", "Unassigned", "New", "Hot", "Warm", "Cold", "Converted", "Duplicates"],
    actions: [
      { label: "Assign Lead", icon: UserCheck, primary: true },
      { label: "Bulk Import", icon: Upload },
      { label: "Merge Duplicates", icon: RefreshCw }
    ],
    chart: { title: "Leads by Status", subtitle: "Pipeline distribution across stages", column: "Status", mode: "count" },
    formTitle: "Create or Update Lead",
    formFields: [
      { label: "Lead name", type: "text", placeholder: "Contact name" },
      { label: "Lead source", type: "select", placeholder: "Meta / CSV / Website / Referral" },
      { label: "Assign to", type: "select", placeholder: "Employee or manager" },
      { label: "Status", type: "select", placeholder: "New / Hot / Warm / Cold / Converted" }
    ]
  },
  {
    key: "customers",
    title: "Customers - Full Access",
    subtitle: "View all customers, convert qualified leads, and review complete profiles with interaction history.",
    icon: Users,
    accent: "from-teal-700 to-pink-500",
    features: [
      "View all customers",
      "Convert a lead into a customer",
      "View full customer profile and interaction history"
    ],
    stats: [
      { label: "Customers", value: "1,284", change: "+73 converted" },
      { label: "Profiles complete", value: "94%", change: "+3.2%" },
      { label: "Open histories", value: "217", change: "Updated today" },
      { label: "Conversion queue", value: "42", change: "Lead-ready" }
    ],
    columns: ["Customer", "Plan", "Owner", "Last Interaction", "Status"],
    rows: [
      { Customer: "Acme Learning", Plan: "Enterprise", Owner: "Aarav Mehta", "Last Interaction": "WhatsApp, today", Status: "Active" },
      { Customer: "Bright Path", Plan: "Growth", Owner: "Nisha Rao", "Last Interaction": "Email, yesterday", Status: "Onboarding" },
      { Customer: "Northstar Labs", Plan: "Pro", Owner: "Kabir Sethi", "Last Interaction": "Call, 2 days ago", Status: "Active" },
      { Customer: "Urban Study", Plan: "Starter", Owner: "Zoya Khan", "Last Interaction": "Timeline note", Status: "At Risk" }
    ],
    filters: ["All customers", "Active", "Onboarding", "At Risk", "Recently converted"],
    actions: [
      { label: "Convert Lead", icon: Check, primary: true },
      { label: "View Profile", icon: Eye },
      { label: "Interaction History", icon: History }
    ],
    chart: { title: "Customers by Status", subtitle: "Active, onboarding, and at-risk accounts", column: "Status", mode: "count" },
    formTitle: "Customer Profile",
    formFields: [
      { label: "Customer name", type: "text", placeholder: "Company or person" },
      { label: "Converted lead", type: "select", placeholder: "Select qualified lead" },
      { label: "Owner", type: "select", placeholder: "Assign owner" },
      { label: "Profile note", type: "text", placeholder: "Interaction summary" }
    ]
  },
  {
    key: "payments",
    title: "Payments - Full Access",
    subtitle: "See all customer payments, add or edit payments, track partials, set reminders, and review company revenue.",
    icon: CircleDollarSign,
    accent: "from-teal-700 to-amber-500",
    features: [
      "View every customer's payments",
      "Add and edit payments",
      "Track partial payments",
      "Set payment reminders",
      "View revenue reports for the full company"
    ],
    stats: [
      { label: "Revenue", value: "$842K", change: "+12.8%" },
      { label: "Partial payments", value: "86", change: "$91K pending" },
      { label: "Reminders set", value: "144", change: "21 due today" },
      { label: "Paid invoices", value: "1,029", change: "97.4% success" }
    ],
    columns: ["Customer", "Amount", "Paid", "Balance", "Reminder"],
    rows: [
      { Customer: "Acme Learning", Amount: "$24,000", Paid: "$18,000", Balance: "$6,000", Reminder: "Aug 03" },
      { Customer: "Bright Path", Amount: "$8,500", Paid: "$8,500", Balance: "$0", Reminder: "None" },
      { Customer: "Northstar Labs", Amount: "$14,200", Paid: "$7,100", Balance: "$7,100", Reminder: "Today" },
      { Customer: "Urban Study", Amount: "$3,600", Paid: "$1,800", Balance: "$1,800", Reminder: "Aug 10" }
    ],
    filters: ["All payments", "Paid", "Partial", "Pending", "Reminder due", "Company revenue"],
    actions: [
      { label: "Add Payment", icon: Plus, primary: true },
      { label: "Edit Payment", icon: Pencil },
      { label: "Set Reminder", icon: Bell }
    ],
    chart: { title: "Payments Received", subtitle: "Amount paid per customer", column: "Paid", mode: "sum", labelColumn: "Customer", prefix: "$" },
    formTitle: "Add or Edit Payment",
    formFields: [
      { label: "Customer", type: "select", placeholder: "Select customer" },
      { label: "Payment amount", type: "number", placeholder: "Enter received amount" },
      { label: "Balance", type: "number", placeholder: "Partial balance" },
      { label: "Reminder date", type: "date", placeholder: "Choose date" }
    ]
  },
  {
    key: "communication",
    title: "Communication - Full Access",
    subtitle: "Send email, send or view WhatsApp messages, inspect call logs, and open a unified communication timeline.",
    icon: MessageCircle,
    accent: "from-teal-700 to-cyan-500",
    features: [
      "Send email to any lead or customer",
      "View and send WhatsApp messages",
      "View call logs",
      "View complete communication history in a unified timeline"
    ],
    stats: [
      { label: "Emails sent", value: "2,408", change: "+334 this week" },
      { label: "WhatsApp threads", value: "936", change: "128 unread" },
      { label: "Call logs", value: "1,762", change: "88 today" },
      { label: "Timeline events", value: "8,914", change: "Unified view" }
    ],
    columns: ["Contact", "Channel", "Owner", "Last Message", "Outcome"],
    rows: [
      { Contact: "Priya Sharma", Channel: "Email", Owner: "Aarav Mehta", "Last Message": "Proposal sent", Outcome: "Opened" },
      { Contact: "Acme Learning", Channel: "WhatsApp", Owner: "Nisha Rao", "Last Message": "Payment reminder", Outcome: "Replied" },
      { Contact: "Rahul Verma", Channel: "Call", Owner: "Kabir Sethi", "Last Message": "Discovery call", Outcome: "Follow-up" },
      { Contact: "Bright Path", Channel: "Timeline", Owner: "Zoya Khan", "Last Message": "Unified activity", Outcome: "Logged" }
    ],
    filters: ["All channels", "Email", "WhatsApp", "Calls", "Timeline", "Unread"],
    actions: [
      { label: "Send Email", icon: Mail, primary: true },
      { label: "WhatsApp", icon: MessageCircle },
      { label: "Call Logs", icon: Phone }
    ],
    chart: { title: "Messages by Channel", subtitle: "Email, WhatsApp, calls, and timeline activity", column: "Channel", mode: "count" },
    formTitle: "Send Communication",
    formFields: [
      { label: "Recipient", type: "select", placeholder: "Lead or customer" },
      { label: "Channel", type: "select", placeholder: "Email / WhatsApp / Call" },
      { label: "Subject", type: "text", placeholder: "Message subject" },
      { label: "Message", type: "text", placeholder: "Write a professional message" }
    ]
  },
  {
    key: "tasks",
    title: "Tasks & Follow-ups",
    subtitle: "Assign tasks to any employee or manager, view the full team's follow-up calendar, and set reminders.",
    icon: CalendarDays,
    accent: "from-teal-700 to-violet-500",
    features: [
      "Assign a task to any employee or manager",
      "View the full team's follow-up calendar",
      "Set reminders"
    ],
    stats: [
      { label: "Open tasks", value: "356", change: "74 due today" },
      { label: "Assigned users", value: "62", change: "Team-wide" },
      { label: "Follow-ups", value: "219", change: "This week" },
      { label: "Reminders", value: "188", change: "Synced" }
    ],
    columns: ["Task", "Assigned To", "Due", "Priority", "Status"],
    rows: [
      { Task: "Call hot leads", "Assigned To": "Aarav Mehta", Due: "Today", Priority: "High", Status: "Open" },
      { Task: "Send onboarding plan", "Assigned To": "Nisha Rao", Due: "Tomorrow", Priority: "Medium", Status: "Scheduled" },
      { Task: "Payment follow-up", "Assigned To": "Kabir Sethi", Due: "Aug 03", Priority: "High", Status: "Open" },
      { Task: "Manager pipeline review", "Assigned To": "Zoya Khan", Due: "Aug 05", Priority: "Low", Status: "Done" }
    ],
    filters: ["All tasks", "Employee", "Manager", "Today", "Overdue", "Completed"],
    actions: [
      { label: "Assign Task", icon: Plus, primary: true },
      { label: "Team Calendar", icon: CalendarDays },
      { label: "Set Reminder", icon: Bell }
    ],
    chart: { title: "Tasks by Priority", subtitle: "Open workload split by priority", column: "Priority", mode: "count" },
    formTitle: "Assign Task or Follow-up",
    formFields: [
      { label: "Task title", type: "text", placeholder: "Follow-up action" },
      { label: "Assign to", type: "select", placeholder: "Employee or manager" },
      { label: "Due date", type: "date", placeholder: "Choose due date" },
      { label: "Reminder", type: "select", placeholder: "Before due date" }
    ]
  },
  {
    key: "audit",
    title: "Audit Logs - Super Admin Only",
    subtitle: "A protected log of who did what and when, visible only to Super Admins.",
    icon: ShieldCheck,
    accent: "from-teal-700 to-slate-600",
    features: [
      "Log who performed each action and when",
      "This screen is visible only to Super Admin, not Manager or Employee"
    ],
    stats: [
      { label: "Logged actions", value: "12,482", change: "Immutable trail" },
      { label: "Today", value: "419", change: "Live capture" },
      { label: "Sensitive events", value: "37", change: "Role and payment edits" },
      { label: "Access scope", value: "Super Admin", change: "Restricted screen" }
    ],
    columns: ["Actor", "Action", "Module", "Time", "IP"],
    rows: [
      { Actor: "Super Admin", Action: "Changed user role", Module: "User Management", Time: "10:42 AM", IP: "103.21.48.12" },
      { Actor: "Super Admin", Action: "Merged duplicate leads", Module: "Leads", Time: "09:58 AM", IP: "103.21.48.12" },
      { Actor: "Super Admin", Action: "Edited partial payment", Module: "Payments", Time: "Yesterday", IP: "103.21.48.12" },
      { Actor: "Super Admin", Action: "Updated integration", Module: "Settings", Time: "Jul 30", IP: "103.21.48.12" }
    ],
    filters: ["All actions", "Users", "Leads", "Payments", "Settings", "Sensitive"],
    actions: [
      { label: "View Log", icon: Eye, primary: true },
      { label: "Export Trail", icon: Download },
      { label: "Filter Events", icon: Filter }
    ],
    chart: { title: "Audit Events by Module", subtitle: "Where Super Admin activity is concentrated", column: "Module", mode: "count" },
    formTitle: "Audit Log Filter",
    formFields: [
      { label: "Actor", type: "select", placeholder: "Super Admin" },
      { label: "Module", type: "select", placeholder: "Users / Leads / Payments / Settings" },
      { label: "Date", type: "date", placeholder: "Choose date" },
      { label: "Action keyword", type: "text", placeholder: "Search action text" }
    ]
  },
  {
    key: "settings",
    title: "Settings / Configuration",
    subtitle: "Configure organization settings, Email, WhatsApp, Calling integrations, and system-wide rules.",
    icon: Settings,
    accent: "from-teal-700 to-zinc-600",
    features: [
      "Organization settings",
      "Configure Email, WhatsApp, and Calling integrations",
      "System-wide settings"
    ],
    stats: [
      { label: "Organization", value: "Qualify Learn", change: "Active workspace" },
      { label: "Integrations", value: "3/3", change: "Email, WhatsApp, Calling" },
      { label: "System rules", value: "24", change: "Company-wide" },
      { label: "Security", value: "On", change: "Super Admin managed" }
    ],
    columns: ["Setting", "Category", "Status", "Owner", "Last Updated"],
    rows: [
      { Setting: "Organization profile", Category: "Organization", Status: "Configured", Owner: "Super Admin", "Last Updated": "Today" },
      { Setting: "Email integration", Category: "Integration", Status: "Connected", Owner: "Super Admin", "Last Updated": "Jul 30" },
      { Setting: "WhatsApp integration", Category: "Integration", Status: "Connected", Owner: "Super Admin", "Last Updated": "Jul 29" },
      { Setting: "Calling integration", Category: "Integration", Status: "Needs review", Owner: "Super Admin", "Last Updated": "Jul 27" }
    ],
    filters: ["All settings", "Organization", "Email", "WhatsApp", "Calling", "System-wide"],
    actions: [
      { label: "Org Settings", icon: Building2, primary: true },
      { label: "Integrations", icon: SlidersHorizontal },
      { label: "System Rules", icon: Settings }
    ],
    chart: { title: "Integration Status", subtitle: "Connected vs. pending configuration", column: "Status", mode: "count" },
    formTitle: "Update Configuration",
    formFields: [
      { label: "Organization name", type: "text", placeholder: "Company name" },
      { label: "Integration type", type: "select", placeholder: "Email / WhatsApp / Calling" },
      { label: "System rule", type: "text", placeholder: "Company-wide setting" },
      { label: "Admin email", type: "email", placeholder: "superadmin@company.com" }
    ]
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

const TEAM_ROSTER = ["Aarav Mehta", "Nisha Rao", "Kabir Sethi", "Zoya Khan", "Maya Iyer"];
const CURRENT_EMPLOYEE_NAME = "Aarav Mehta";

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

function startOfWeek(date: Date): Date {
  const next = new Date(date);
  next.setDate(next.getDate() - next.getDay());
  next.setHours(0, 0, 0, 0);
  return next;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function ownerOf(row: RowRecord): string | undefined {
  return row.Owner ?? row["Assigned To"] ?? undefined;
}

function scopeRowsForCalendar(rows: RowRecord[], role: Role): RowRecord[] {
  if (role !== "employee") return rows;
  return rows.filter((row) => ownerOf(row) === CURRENT_EMPLOYEE_NAME);
}

function pseudoDateForRow(id: string): string {
  const seed = Array.from(id).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const offset = (seed % 41) - 20;
  return toDateKey(addDays(new Date(), offset));
}

function canSeeReminder(reminder: Reminder, role: Role): boolean {
  if (role === "superadmin") return true;
  if (role === "manager") return reminder.assignedTo === "Manager" || TEAM_ROSTER.includes(reminder.assignedTo);
  return reminder.assignedTo === CURRENT_EMPLOYEE_NAME;
}

function canSeeNote(note: CalendarNote, role: Role): boolean {
  if (role === "superadmin") return true;
  if (role === "manager") return !(note.visibility === "private" && note.author === "Super Admin");
  return note.author === CURRENT_EMPLOYEE_NAME;
}

function assigneeOptionsForRole(role: Role): string[] {
  if (role === "superadmin") return ["Super Admin", "Manager", ...TEAM_ROSTER];
  if (role === "manager") return ["Manager", ...TEAM_ROSTER];
  return [CURRENT_EMPLOYEE_NAME];
}

function createInitialReminders(): Reminder[] {
  const today = new Date();
  return [
    {
      id: "reminder-seed-1",
      title: "Follow up with Priya Sharma",
      date: toDateKey(today),
      time: "10:30",
      priority: "High",
      repeat: "None",
      kind: "Follow-up",
      assignedTo: CURRENT_EMPLOYEE_NAME,
      createdByRole: "manager",
      completed: false,
      snoozedUntil: null
    },
    {
      id: "reminder-seed-2",
      title: "Team pipeline review",
      date: toDateKey(addDays(today, 1)),
      time: "15:00",
      priority: "Medium",
      repeat: "Weekly",
      kind: "Meeting",
      assignedTo: "Manager",
      createdByRole: "superadmin",
      completed: false,
      snoozedUntil: null
    },
    {
      id: "reminder-seed-3",
      title: "Send payment reminder to Northstar Labs",
      date: toDateKey(addDays(today, -1)),
      time: "09:00",
      priority: "Urgent",
      repeat: "None",
      kind: "Reminder",
      assignedTo: "Nisha Rao",
      createdByRole: "manager",
      completed: false,
      snoozedUntil: null
    },
    {
      id: "reminder-seed-4",
      title: "Quarterly audit prep",
      date: toDateKey(addDays(today, 3)),
      time: "11:00",
      priority: "Low",
      repeat: "Monthly",
      kind: "Task",
      assignedTo: "Super Admin",
      createdByRole: "superadmin",
      completed: false,
      snoozedUntil: null
    }
  ];
}

function createInitialNotes(): CalendarNote[] {
  const today = new Date();
  return [
    {
      id: "note-seed-1",
      date: toDateKey(today),
      text: "Discussed onboarding checklist with Acme Learning.",
      author: "Aarav Mehta",
      pinned: true,
      visibility: "team",
      attachments: [],
      createdAt: new Date().toISOString()
    },
    {
      id: "note-seed-2",
      date: toDateKey(addDays(today, -2)),
      text: "Personal reminder: prep call script for hot leads.",
      author: CURRENT_EMPLOYEE_NAME,
      pinned: false,
      visibility: "private",
      attachments: [],
      createdAt: new Date().toISOString()
    }
  ];
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

const revenueData = [
  { label: "Jan", value: 48 },
  { label: "Feb", value: 56 },
  { label: "Mar", value: 52 },
  { label: "Apr", value: 69 },
  { label: "May", value: 74 },
  { label: "Jun", value: 88 },
  { label: "Jul", value: 96 }
];

const conversionData = [
  { label: "New", value: 680 },
  { label: "Hot", value: 316 },
  { label: "Warm", value: 482 },
  { label: "Cold", value: 224 },
  { label: "Won", value: 173 }
];

const sourceData = [
  { label: "Meta Ads", value: 42, color: "#0F766E" },
  { label: "Website", value: 24, color: "#F97316" },
  { label: "Referral", value: 18, color: "#0EA5E9" },
  { label: "CSV", value: 16, color: "#10B981" }
];

const monthlyLeadsData = [
  { label: "Jan", value: 410 },
  { label: "Feb", value: 468 },
  { label: "Mar", value: 439 },
  { label: "Apr", value: 522 },
  { label: "May", value: 590 },
  { label: "Jun", value: 641 },
  { label: "Jul", value: 681 }
];

const employeePerformanceData = [
  { label: "Aarav", value: 92 },
  { label: "Nisha", value: 87 },
  { label: "Kabir", value: 79 },
  { label: "Zoya", value: 84 },
  { label: "Maya", value: 76 }
];

const paymentStatusData = [
  { label: "Paid", value: 68, color: "#0F766E" },
  { label: "Partial", value: 21, color: "#F97316" },
  { label: "Pending", value: 11, color: "#F59E0B" }
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
  const pendingPayments = payments.reduce((sum, row) => sum + parseCurrency(row.Balance), 0);
  const activeEmployees = users.filter((row) => row.Status === "Active").length;
  const convertedLeads = leads.filter((row) => row.Status === "Converted").length;
  const conversionRate = leads.length ? ((convertedLeads / leads.length) * 100).toFixed(1) : "0.0";
  const pendingCount = payments.filter((row) => parseCurrency(row.Balance) > 0).length;

  return [
    { label: "Total Leads", value: leads.length.toLocaleString(), change: `${leads.length} tracked` },
    { label: "Total Customers", value: customers.length.toLocaleString(), change: `${customers.length} active accounts` },
    { label: "Total Revenue", value: formatCurrencyShort(totalRevenue), change: "Collected to date" },
    { label: "Pending Payments", value: formatCurrencyShort(pendingPayments), change: `${pendingCount} awaiting` },
    { label: "Active Employees", value: activeEmployees.toLocaleString(), change: `${users.length} total users` },
    { label: "Conversion Rate", value: `${conversionRate}%`, change: `${convertedLeads} converted` }
  ];
}

function rowMatchesFilter(row: RowRecord, filterLabel: string): boolean {
  const normalized = filterLabel.trim().toLowerCase();
  if (!normalized || normalized.startsWith("all")) return true;
  const values = Object.values(row).map((value) => value.toLowerCase());
  if (values.some((value) => value === normalized)) return true;
  const words = normalized.split(/\s+/).filter((word) => word.length > 2);
  return words.some((word) => values.some((value) => value.includes(word)));
}

function exportRecordsToCsv(module: ModuleConfig, records: RowRecord[]) {
  const header = module.columns.join(",");
  const lines = records.map((row) =>
    module.columns.map((column) => `"${(row[column] ?? "").replace(/"/g, '""')}"`).join(",")
  );
  const csv = [header, ...lines].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${module.key}-export-${Date.now()}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function computeModuleChartData(
  records: RowRecord[],
  chart: { column: string; mode: "count" | "sum"; labelColumn?: string }
): Array<{ label: string; value: number }> {
  if (chart.mode === "sum") {
    const labelColumn = chart.labelColumn ?? chart.column;
    return records
      .map((row) => ({ label: row[labelColumn] ?? row.id, value: parseCurrency(row[chart.column]) }))
      .slice(0, 6);
  }

  const counts = new Map<string, number>();
  records.forEach((row) => {
    const value = row[chart.column] || "Unknown";
    counts.set(value, (counts.get(value) ?? 0) + 1);
  });
  return Array.from(counts.entries()).map(([label, value]) => ({ label, value }));
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
const AUTH_STORAGE_KEY = "qualify-learn-crm-auth";
const ROLE_STORAGE_KEY = "qualify-learn-crm-role";
const VALID_USERNAME = "qualifylearncrm";
const VALID_PASSWORD = "crmworkingphase";
const VALID_MANAGER_USERNAME = "qualifylearnmanagercrm";
const VALID_MANAGER_PASSWORD = "crmworkingphasemanager";
const VALID_EMPLOYEE_USERNAME = "qualifylearnemployeecrm";
const VALID_EMPLOYEE_PASSWORD = "crmworkingphaseemployee";

export default function AuthGate() {
  const [role, setRole] = useState<Role | null | undefined>(undefined);

  useEffect(() => {
    const authed =
      window.localStorage.getItem(AUTH_STORAGE_KEY) === "true" || window.sessionStorage.getItem(AUTH_STORAGE_KEY) === "true";
    const storedRole = (window.localStorage.getItem(ROLE_STORAGE_KEY) ?? window.sessionStorage.getItem(ROLE_STORAGE_KEY)) as Role | null;
    setRole(authed && storedRole ? storedRole : null);
  }, []);

  function handleLoginSuccess(nextRole: Role, remember: boolean) {
    const storage = remember ? window.localStorage : window.sessionStorage;
    storage.setItem(AUTH_STORAGE_KEY, "true");
    storage.setItem(ROLE_STORAGE_KEY, nextRole);
    setRole(nextRole);
  }

  function handleLogout() {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    window.localStorage.removeItem(ROLE_STORAGE_KEY);
    window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
    window.sessionStorage.removeItem(ROLE_STORAGE_KEY);
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

  return <SuperAdminPage role={role} onLogout={handleLogout} />;
}

function LoginScreen({ onSuccess }: { onSuccess: (role: Role, remember: boolean) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    window.setTimeout(() => {
      if (username === VALID_USERNAME && password === VALID_PASSWORD) {
        setError("");
        onSuccess("superadmin", rememberMe);
      } else if (username === VALID_MANAGER_USERNAME && password === VALID_MANAGER_PASSWORD) {
        setError("");
        onSuccess("manager", rememberMe);
      } else if (username === VALID_EMPLOYEE_USERNAME && password === VALID_EMPLOYEE_PASSWORD) {
        setError("");
        onSuccess("employee", rememberMe);
      } else {
        setError("Invalid Username or Password.");
      }
      setSubmitting(false);
    }, 320);
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
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="Enter your username"
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
                  placeholder="Enter your password"
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
              Sign In
            </button>
          </div>
        </form>

        <p className="mt-6 text-center text-xs text-muted-foreground">Qualify Learn - Empowering Minds, Elevating Futures.</p>
      </div>
    </div>
  );
}

function SuperAdminPage({ role, onLogout }: { role: Role; onLogout: () => void }) {
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
  const [recordsByModule, setRecordsByModule] = useState<RecordsByModule>(() => createInitialRecords());
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>(() =>
    recentActivities.map((message, index) => ({ id: `seed-${index}`, message, moduleKey: "reports", row: null }))
  );
  const [toast, setToast] = useState<ToastState>(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [dark, setDark] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [reminders, setReminders] = useState<Reminder[]>(() => createInitialReminders());
  const [notes, setNotes] = useState<CalendarNote[]>(() => createInitialNotes());

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    return () => {
      document.documentElement.classList.remove("dark");
    };
  }, [dark]);

  const importInputRef = useRef<HTMLInputElement>(null);
  const importTargetRef = useRef<ModuleKey>("leads");
  const notifiedReminderIds = useRef<Set<string>>(new Set());

  const activeModule = modules.find((module) => module.key === activeKey) ?? modules[0];
  const activeRecords = recordsByModule[activeKey] ?? [];
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

  const kpis = useMemo(() => computeKpis(recordsByModule), [recordsByModule]);

  const globalSearchResults = useMemo(() => {
    const lowerQuery = globalQuery.trim().toLowerCase();
    if (!lowerQuery) return [];
    const results: Array<{ moduleKey: ModuleKey; moduleTitle: string; row: RowRecord; label: string }> = [];
    for (const module of visibleModules) {
      const moduleRows = recordsByModule[module.key] ?? [];
      for (const row of moduleRows) {
        const matches = Object.values(row).some((value) => value.toLowerCase().includes(lowerQuery));
        if (matches) {
          results.push({ moduleKey: module.key, moduleTitle: module.title, row, label: row[module.columns[0]] ?? row.id });
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
    setFormData(Object.fromEntries(targetModule.columns.map((column) => [column, row[column] ?? ""])));
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
      .filter((reminder) => canSeeReminder(reminder, role) && !reminder.completed && reminder.date <= todayKey)
      .forEach((reminder) => {
        if (notifiedReminderIds.current.has(reminder.id)) return;
        notifiedReminderIds.current.add(reminder.id);
        const overdue = reminder.date < todayKey;
        logActivity(`${overdue ? "Overdue" : "Due today"}: ${reminder.kind} "${reminder.title}" (${reminder.priority} priority).`, "calendar", null);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reminders, role]);

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
    setFormData(Object.fromEntries(targetModule.columns.map((column) => [column, currentRow[column] ?? ""])));
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
    setActiveKey(moduleKey);
    setFilter(targetModule.filters[0] ?? "All");
    setEditingRecord(currentRow);
    setModalMode("edit");
    setFormData(Object.fromEntries(targetModule.columns.map((column) => [column, currentRow[column] ?? ""])));
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
    setModalOpen(true);
  }

  function openEditModal(row: RowRecord) {
    setEditingRecord(row);
    setModalMode("edit");
    setFormData(Object.fromEntries(activeModule.columns.map((column) => [column, row[column] ?? ""])));
    setModalOpen(true);
  }

  function openViewModal(row: RowRecord) {
    setEditingRecord(row);
    setModalMode("view");
    setFormData(Object.fromEntries(activeModule.columns.map((column) => [column, row[column] ?? ""])));
    setModalOpen(true);
  }

  function updateFormField(field: string, value: string) {
    setFormData((current) => ({ ...current, [field]: value }));
  }

  function saveRecord() {
    if (modalMode === "view") {
      setModalOpen(false);
      return;
    }

    const missingField = activeModule.columns.find((column) => !formData[column]?.trim());

    if (missingField) {
      showToast({ type: "error", message: `${missingField} is required before saving.` });
      return;
    }

    if (modalMode === "create") {
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
    const confirmed = window.confirm(`Delete this ${activeModule.title} record? This cannot be undone.`);
    if (!confirmed) return;
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

  function mergeDuplicateLeads() {
    const leadRows = recordsByModule.leads ?? [];
    const possibleCount = leadRows.filter((row) => row.Duplicate === "Possible").length;
    if (possibleCount === 0) {
      showToast({ type: "error", message: "No duplicate leads to merge right now." });
      return;
    }
    setRecordsByModule((current) => ({
      ...current,
      leads: (current.leads ?? []).map((row) => (row.Duplicate === "Possible" ? { ...row, Duplicate: "Merged" } : row))
    }));
    showToast({ type: "success", message: `${possibleCount} duplicate lead${possibleCount === 1 ? "" : "s"} merged.` });
    logActivity(`Merged ${possibleCount} duplicate lead${possibleCount === 1 ? "" : "s"}.`, "leads", null);
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

    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result ?? "");
      const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      const dataLines = lines.slice(1);
      const sourceLines = dataLines.length ? dataLines : [""];
      const imported: RowRecord[] = sourceLines.slice(0, 15).map((line, index) => {
        const cells = line.split(",").map((cell) => cell.replace(/^"|"$/g, "").trim());
        const record: RowRecord = { id: `${targetKey}-import-${Date.now()}-${index}` } as RowRecord;
        targetModule.columns.forEach((column, columnIndex) => {
          record[column] = cells[columnIndex] ? cells[columnIndex] : `Imported ${column} ${index + 1}`;
        });
        return record;
      });

      setRecordsByModule((current) => ({
        ...current,
        [targetKey]: [...imported, ...(current[targetKey] ?? [])]
      }));
      setActiveKey(targetKey);
      setFilter(targetModule.filters[0] ?? "All");
      setQuery("");
      showToast({
        type: "success",
        message: `${imported.length} record${imported.length === 1 ? "" : "s"} imported into ${targetModule.title}.`
      });
      logActivity(
        `Imported ${imported.length} record${imported.length === 1 ? "" : "s"} into ${targetModule.title}.`,
        targetKey,
        imported[0] ?? null
      );
    };
    reader.readAsText(file);
  }

  function handleModuleAction(action: { label: string; icon: React.ElementType; primary?: boolean }) {
    const label = action.label;

    if (label === "Export CSV" || label === "Export Excel" || label === "Export Trail") {
      exportRecordsToCsv(activeModule, rows);
      showToast({ type: "success", message: `${rows.length} ${activeModule.title} record${rows.length === 1 ? "" : "s"} exported.` });
      logActivity(`Exported ${rows.length} ${activeModule.title} record${rows.length === 1 ? "" : "s"}.`, activeKey, null);
      return;
    }

    if (label === "Bulk Import") {
      triggerImport(activeKey);
      return;
    }

    if (label === "Refresh Report") {
      setIsLoading(true);
      window.setTimeout(() => setIsLoading(false), 480);
      showToast({ type: "success", message: "Report refreshed with the latest data." });
      logActivity("Refreshed the reports dashboard.", activeKey, null);
      return;
    }

    if (label === "Merge Duplicates") {
      mergeDuplicateLeads();
      return;
    }

    if (label === "Set Reminder") {
      showToast({ type: "success", message: "Reminder scheduled for the selected records." });
      logActivity("Scheduled a reminder for pending records.", activeKey, null);
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

  function quickExportLeads() {
    const leadRows = recordsByModule.leads ?? [];
    const leadsModule = modules.find((module) => module.key === "leads");
    if (!leadsModule) return;
    exportRecordsToCsv(leadsModule, leadRows);
    showToast({ type: "success", message: `${leadRows.length} lead record${leadRows.length === 1 ? "" : "s"} exported.` });
    logActivity(`Exported ${leadRows.length} lead record${leadRows.length === 1 ? "" : "s"}.`, "leads", null);
  }

  function quickSendReminder() {
    showToast({ type: "success", message: "Payment reminders sent to customers with pending balances." });
    logActivity("Sent payment reminders to customers with pending balances.", "payments", null);
  }

  function quickAssignTask() {
    openCreateModalFor("tasks");
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
    <main>
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
          onLogout={onLogout}
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
                    className="hidden items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm font-medium shadow-sm sm:inline-flex"
                    onClick={() => setDrawerOpen(true)}
                  >
                    <Activity className="size-4 text-teal-600" />
                    Live Detail
                  </button>
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

            <div className="grid gap-6 px-4 py-5 xl:grid-cols-[minmax(0,1fr)_360px] xl:px-8">
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
                          {role === "manager"
                            ? "Team-level access only"
                            : role === "employee"
                            ? "Personal access only"
                            : "No restriction: full system access"}
                        </div>
                        <h2 className="text-3xl font-bold">{displayModuleTitle}</h2>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-white/88">{displayModuleSubtitle}</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {activeModule.actions.map((action) => {
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

                  <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-4">
                    {activeModule.stats.map((stat) => (
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
                    dark={dark}
                    recordsByModule={recordsByModule}
                    reminders={reminders}
                    notes={notes}
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
                        paymentRows={recordsByModule.payments ?? []}
                        activityLog={activityLog}
                        reminders={reminders}
                        onQuickAdd={quickAddLead}
                        onImportLeads={quickImportLeads}
                        onExportLeads={quickExportLeads}
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
                    ) : (
                      <ModuleChartSection module={activeModule} records={activeRecords} />
                    )}

                    <FeatureCards module={activeModule} />

                    <section className="rounded-2xl border bg-card shadow-sm">
                      <div className="border-b p-4">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                          <div>
                            <h3 className="text-lg font-bold text-foreground">{displayModuleTitle} Records</h3>
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
                        <LoadingSkeleton columns={activeModule.columns} />
                      ) : (
                        <DataTable
                          module={activeModule}
                          rows={pagedRows}
                          dark={dark}
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

                    <WorkflowPanel module={activeModule} />
                  </>
                )}
              </div>

              <AnimatePresence>
                {drawerOpen ? (
                  <motion.aside
                    initial={{ opacity: 0, x: 26 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 26 }}
                    className="h-fit rounded-2xl border bg-card shadow-soft xl:sticky xl:top-24"
                  >
                    <DetailDrawer
                      role={role}
                      module={activeModule}
                      moduleTitle={displayModuleTitle}
                      onClose={() => setDrawerOpen(false)}
                      onAction={handleModuleAction}
                    />
                  </motion.aside>
                ) : null}
              </AnimatePresence>
            </div>
          </section>
        </div>
      </div>

      <AnimatePresence>
        {modalOpen ? (
          <RecordModal
            module={activeModule}
            mode={modalMode}
            formData={formData}
            onChange={updateFormField}
            onSave={saveRecord}
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

      <button
        onClick={onNewClick}
        className="hidden shrink-0 items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-sm font-semibold shadow-sm transition hover:bg-muted sm:inline-flex"
      >
        <Plus className="size-4 text-teal-600" />
        New
      </button>

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
  paymentRows,
  activityLog,
  reminders,
  onQuickAdd,
  onImportLeads,
  onExportLeads,
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
  paymentRows: RowRecord[];
  activityLog: ActivityEntry[];
  reminders: Reminder[];
  onQuickAdd: () => void;
  onImportLeads: () => void;
  onExportLeads: () => void;
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

  const topPerformers = [...employeePerformanceData].sort((a, b) => b.value - a.value).slice(0, 3);
  const openRequests = paymentRows.filter((row) => parseCurrency(row.Balance) > 0).slice(0, 5);

  const upcomingReminders = reminders
    .filter((reminder) => canSeeReminder(reminder, role) && !reminder.completed)
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
          <h3 className="text-lg font-bold text-foreground">
            {role === "manager" ? "Key figures for your team" : role === "employee" ? "Key figures for you" : "Key figures for the Super Admin team"}
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
          <ChartCard title="Top Performers" subtitle="Against monthly target">
            <div className="space-y-4 py-1">
              {topPerformers.map((person) => (
                <div key={person.label} className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="flex size-9 items-center justify-center rounded-full bg-teal-50 text-sm font-bold text-teal-700 dark:bg-teal-950 dark:text-teal-200">
                      {person.label.slice(0, 2).toUpperCase()}
                    </span>
                    <span className="text-sm font-semibold">{person.label}</span>
                  </div>
                  <span className="text-lg font-bold">{person.value}%</span>
                </div>
              ))}
            </div>
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
                      <p className="truncate text-sm font-semibold">{row.Customer}</p>
                      <p className="text-xs text-muted-foreground">{row.Reminder}</p>
                    </div>
                    <span className="shrink-0 text-sm font-bold">{row.Balance}</span>
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
          <ChartCard title="Employee Performance" subtitle="Team completion score">
            <BarChart data={employeePerformanceData} suffix="%" />
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
              <h3 className="text-lg font-bold text-foreground">Recent Leads</h3>
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
            <h3 className="text-lg font-bold text-foreground">Today's Statistics</h3>
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
            <h3 className="text-lg font-bold text-foreground">Quick Actions</h3>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              <button onClick={onImportLeads} className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm font-semibold">
                <Upload className="size-4 text-teal-600" />
                Import Leads
              </button>
              <button onClick={onExportLeads} className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm font-semibold">
                <Download className="size-4 text-teal-600" />
                Export CSV
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

      <div className="grid gap-4 lg:grid-cols-2">
        <TimelineCard
          title="Recent Activities"
          items={activityLog}
          onView={onViewActivity}
          onEdit={onEditActivity}
          onDelete={onDeleteActivity}
          onCreate={onCreateForModule}
        />
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <h3 className="text-lg font-bold text-foreground">Upcoming Follow-ups</h3>
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
      </div>

      <div className="grid gap-4">
        <article className="rounded-2xl border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-bold text-foreground">Upcoming Reminders</h3>
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
  dark,
  recordsByModule,
  reminders,
  notes,
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
  dark: boolean;
  recordsByModule: RecordsByModule;
  reminders: Reminder[];
  notes: CalendarNote[];
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

  const identity = role === "employee" ? CURRENT_EMPLOYEE_NAME : role === "manager" ? "Manager" : "Super Admin";
  const todayKey = toDateKey(new Date());

  const visibleReminders = useMemo(() => reminders.filter((reminder) => canSeeReminder(reminder, role)), [reminders, role]);
  const visibleNotes = useMemo(() => notes.filter((note) => canSeeNote(note, role)), [notes, role]);

  const dayMap = useMemo(() => {
    const map = new Map<string, CalendarDayData>();
    function ensure(key: string) {
      if (!map.has(key)) map.set(key, emptyDayData());
      return map.get(key)!;
    }
    scopeRowsForCalendar(recordsByModule.leads ?? [], role).forEach((row) => ensure(pseudoDateForRow(row.id)).leads.push(row));
    scopeRowsForCalendar(recordsByModule.customers ?? [], role).forEach((row) => ensure(pseudoDateForRow(row.id)).customers.push(row));
    scopeRowsForCalendar(recordsByModule.payments ?? [], role).forEach((row) => ensure(pseudoDateForRow(row.id)).payments.push(row));
    scopeRowsForCalendar(recordsByModule.tasks ?? [], role).forEach((row) => ensure(pseudoDateForRow(row.id)).tasks.push(row));
    scopeRowsForCalendar(recordsByModule.communication ?? [], role).forEach((row) => {
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
            <h3 className="ml-1 text-lg font-bold text-foreground">
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
                  <DayBadges dateKey={key} />
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
            dark={dark}
            identity={identity}
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
  dark,
  identity,
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
  dark: boolean;
  identity: string;
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
    <div className={cn(dark && "dark")}>
      <motion.div
        className="fixed inset-0 z-[70] bg-black/40"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.aside
        className="glass-scrollbar fixed right-0 top-0 z-[80] h-full w-full max-w-md overflow-y-auto border-l bg-card text-foreground p-5 shadow-soft"
        initial={{ x: 420 }}
        animate={{ x: 0 }}
        exit={{ x: 420 }}
        transition={{ type: "tween", duration: 0.25 }}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-600">Date Details</p>
            <h3 className="text-lg font-bold text-foreground">{parseDateKey(dateKey).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</h3>
          </div>
          <button onClick={onClose} className="inline-flex size-8 items-center justify-center rounded-lg border" aria-label="Close">
            <X className="size-4" />
          </button>
        </div>
        <DayContent
          role={role}
          identity={identity}
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
    </div>,
    document.body
  );
}

function DayContent({
  role,
  identity,
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
    ...day.payments.map((row) => ({ label: `Payment: ${row.Customer ?? row.id}`, sub: row.Balance ?? "" })),
    ...day.communication.map((row) => ({ label: `${row.Channel ?? "Message"}: ${row.Contact ?? row.id}`, sub: row.Outcome ?? "" })),
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
            <DetailRow key={row.id} title={row.Customer ?? row.id} subtitle={`Paid ${row.Paid ?? "-"} of ${row.Amount ?? "-"}`} badge={parseCurrency(row.Balance) > 0 ? "Partial" : "Paid"} />
          ))}
        </DetailSection>
      ) : null}

      {day.communication.length > 0 ? (
        <DetailSection title="Calls, WhatsApp & email history">
          {day.communication.map((row) => (
            <DetailRow key={row.id} title={`${row.Channel ?? "Message"} - ${row.Contact ?? row.id}`} subtitle={row["Last Message"] ?? ""} badge={row.Outcome} />
          ))}
        </DetailSection>
      ) : null}

      {day.tasks.length > 0 ? (
        <DetailSection title="Tasks & meetings">
          {day.tasks.map((row) => (
            <DetailRow key={row.id} title={row.Task ?? row.id} subtitle={row["Assigned To"] ?? ""} badge={row.Status} />
          ))}
        </DetailSection>
      ) : null}

      {role === "superadmin" && day.audit.length > 0 ? (
        <DetailSection title="Audit logs">
          {day.audit.map((row) => (
            <DetailRow key={row.id} title={row.Action ?? row.id} subtitle={`${row.Actor ?? ""} - ${row.Module ?? ""}`} badge={row.Time} />
          ))}
        </DetailSection>
      ) : null}

      <ReminderSection
        role={role}
        identity={identity}
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
  dateKey: string;
  reminders: Reminder[];
  onAdd: (input: Omit<Reminder, "id" | "completed" | "snoozedUntil" | "createdByRole">) => void;
  onUpdate: (id: string, patch: Partial<Reminder>) => void;
  onDelete: (id: string) => void;
  onToggleComplete: (id: string) => void;
  onSnooze: (id: string, days?: number) => void;
}) {
  const assigneeOptions = assigneeOptionsForRole(role);
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
          <h3 className="text-base font-bold text-foreground">{title}</h3>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <MoreHorizontal className="size-4 shrink-0 text-muted-foreground" />
      </div>
      {children}
    </article>
  );
}

function ModuleChartSection({ module, records }: { module: ModuleConfig; records: RowRecord[] }) {
  if (!module.chart) return null;
  const data = computeModuleChartData(records, module.chart);

  return (
    <ChartCard title={module.chart.title} subtitle={module.chart.subtitle}>
      {data.length === 0 ? (
        <div className="flex h-56 flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
          <Filter className="size-6" />
          No data available for this chart yet.
        </div>
      ) : (
        <BarChart data={data} prefix={module.chart.prefix ?? ""} suffix={module.chart.suffix ?? ""} />
      )}
    </ChartCard>
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
      <h3 className="text-lg font-bold text-foreground">{title}</h3>
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

function FeatureCards({ module }: { module: ModuleConfig }) {
  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {module.features.map((feature, index) => (
        <motion.article
          key={feature}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.025 }}
          className="rounded-xl border bg-card p-4 shadow-sm"
        >
          <div className="mb-3 flex size-9 items-center justify-center rounded-lg bg-teal-50 text-teal-600 dark:bg-teal-950 dark:text-teal-200">
            <Check className="size-4" />
          </div>
          <p className="text-sm font-semibold leading-6">{feature}</p>
        </motion.article>
      ))}
    </section>
  );
}

function DataTable({
  module,
  rows,
  dark,
  onEdit,
  onView,
  onDuplicate,
  onDelete,
  sort,
  onSort
}: {
  module: ModuleConfig;
  rows: RowRecord[];
  dark: boolean;
  onEdit: (row: RowRecord) => void;
  onView: (row: RowRecord) => void;
  onDuplicate: (row: RowRecord) => void;
  onDelete: (row: RowRecord) => void;
  sort: { column: string; direction: "asc" | "desc" } | null;
  onSort: (column: string) => void;
}) {
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
        <h3 className="text-lg font-bold text-foreground">No records found</h3>
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
                const isBadge = ["Status", "Duplicate", "Priority", "Outcome", "Export"].includes(column);
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
                  <button
                    className="inline-flex size-8 items-center justify-center rounded-lg border bg-background text-muted-foreground hover:text-teal-600"
                    aria-label="Edit record"
                    onClick={() => onEdit(row)}
                  >
                    <Pencil className="size-4" />
                  </button>
                  <button
                    className="inline-flex size-8 items-center justify-center rounded-lg border bg-background text-muted-foreground hover:text-teal-600"
                    aria-label="More actions"
                    onClick={(event) => toggleMenu(row.id, event)}
                  >
                    <MoreHorizontal className="size-4" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {openMenuRow && menuPos
        ? createPortal(
            <div className={cn(dark && "dark")}>
              <div className="fixed inset-0 z-40" onClick={() => setOpenMenuId(null)} />
              <div
                className="fixed z-50 w-40 overflow-hidden rounded-lg border bg-card text-foreground shadow-soft"
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
            </div>,
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

function WorkflowPanel({ module }: { module: ModuleConfig }) {
  return (
    <section className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
      <article className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-foreground">Form & Validation</h3>
            <p className="text-sm text-muted-foreground">{module.formTitle} with required field checks.</p>
          </div>
          <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-700 dark:bg-red-950 dark:text-red-200">Required</span>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {module.formFields.map((field, index) => (
            <label key={field.label} className="space-y-1.5">
              <span className="text-sm font-semibold">{field.label}</span>
              {field.type === "select" ? (
                <select className="h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none ring-teal-600/20 focus:ring-4">
                  <option>{field.placeholder}</option>
                </select>
              ) : (
                <input
                  type={field.type}
                  placeholder={field.placeholder}
                  className={cn(
                    "h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none ring-teal-600/20 focus:ring-4",
                    index === 1 && "border-red-300"
                  )}
                />
              )}
              {index === 1 ? <span className="text-xs font-medium text-red-600">This field is required.</span> : null}
            </label>
          ))}
        </div>
      </article>

      <article className="rounded-2xl border bg-card p-5 shadow-sm">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-foreground">Empty & Loading States</h3>
            <p className="text-sm text-muted-foreground">Production states for slow or missing records.</p>
          </div>
          <Loader2 className="size-5 animate-spin text-teal-600" />
        </div>
        <div className="rounded-xl border border-dashed p-5 text-center">
          <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-xl bg-muted">
            <Filter className="size-5 text-muted-foreground" />
          </div>
          <h4 className="font-bold">No filtered data yet</h4>
          <p className="mt-1 text-sm text-muted-foreground">Clear filters or create a new record from the module actions.</p>
        </div>
      </article>
    </section>
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

function DetailDrawer({
  role,
  module,
  moduleTitle,
  onClose,
  onAction
}: {
  role: Role;
  module: ModuleConfig;
  moduleTitle: string;
  onClose: () => void;
  onAction: (action: { label: string; icon: React.ElementType; primary?: boolean }) => void;
}) {
  const Icon = module.icon;
  return (
    <div>
      <div className="flex items-start justify-between gap-4 border-b p-5">
        <div>
          <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-teal-50 text-teal-600 dark:bg-teal-950 dark:text-teal-200">
            <Icon className="size-5" />
          </div>
          <h3 className="text-lg font-bold text-foreground">{ROLE_LABEL[role]} Detail Drawer</h3>
          <p className="mt-1 text-sm text-muted-foreground">Quick actions and permission summary for {moduleTitle}.</p>
        </div>
        <button onClick={onClose} className="inline-flex size-8 items-center justify-center rounded-lg border">
          <X className="size-4" />
        </button>
      </div>

      <div className="space-y-4 p-5">
        <div className="rounded-xl border bg-background p-4">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-600">Permissions</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {role === "manager"
              ? "Manager can view, create, update, assign, and export this module for their own team only. Audit Logs and other teams' data stay hidden."
              : role === "employee"
              ? "Employee can view, create, and update records assigned to them only. Other employees' data, reports, audit logs, and settings stay hidden."
              : "Super Admin can view, create, update, assign, configure, export, and audit this module with no restrictions."}
          </p>
        </div>
        <div className="space-y-2">
          {module.actions.map((action) => {
            const ActionIcon = action.icon;
            return (
              <button
                key={action.label}
                onClick={() => onAction(action)}
                className="flex w-full items-center justify-between rounded-lg border bg-background px-3 py-2 text-sm font-semibold"
              >
                <span className="flex items-center gap-2">
                  <ActionIcon className="size-4 text-teal-600" />
                  {action.label}
                </span>
                <ChevronRight className="size-4 text-muted-foreground" />
              </button>
            );
          })}
        </div>
        <div className="rounded-xl bg-muted p-4">
          <p className="text-sm font-bold">Unified Timeline Preview</p>
          <div className="mt-3 space-y-3">
            {["Permission checked", "Record updated", "Audit entry saved"].map((item) => (
              <div key={item} className="flex gap-3 text-sm">
                <span className="mt-1 size-2 rounded-full bg-teal-600" />
                <span className="text-muted-foreground">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function RecordModal({
  module,
  mode,
  formData,
  onChange,
  onSave,
  onClose
}: {
  module: ModuleConfig;
  mode: "create" | "edit" | "view";
  formData: Record<string, string>;
  onChange: (field: string, value: string) => void;
  onSave: () => void;
  onClose: () => void;
}) {
  const isView = mode === "view";
  const title = mode === "edit" ? `Edit ${module.title}` : mode === "view" ? `View ${module.title}` : module.formTitle;
  const subtitle =
    mode === "edit"
      ? `Update the existing record for ${module.title}.`
      : mode === "view"
      ? `Read-only details for this ${module.title} record.`
      : `Modal form with validation for ${module.title}.`;

  return (
    <motion.div
      className="fixed inset-0 z-[60] grid place-items-center bg-black/45 p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-2xl rounded-2xl border bg-card shadow-soft"
        initial={{ scale: 0.96, y: 18 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.96, y: 18 }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b p-5">
          <div>
            <h3 className="text-xl font-bold text-foreground">{title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          </div>
          <button onClick={onClose} className="inline-flex size-9 items-center justify-center rounded-lg border text-foreground">
            <X className="size-4" />
          </button>
        </div>
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          {module.columns.map((column, index) => (
            <label key={column} className="space-y-1.5">
              <span className="text-sm font-semibold text-foreground">{column}</span>
              <input
                type="text"
                value={formData[column] ?? ""}
                readOnly={isView}
                onChange={(event) => onChange(column, event.target.value)}
                placeholder={`Enter ${column.toLowerCase()}`}
                className={cn(
                  "h-11 w-full rounded-lg border bg-background px-3 text-sm text-foreground outline-none ring-teal-600/20 focus:ring-4",
                  isView && "cursor-default bg-muted text-muted-foreground",
                  !isView && index === 0 && "border-red-300"
                )}
              />
              {!isView && index === 0 ? <span className="text-xs font-medium text-red-600">Required field cannot be empty.</span> : null}
            </label>
          ))}
        </div>
        <div className="flex flex-col-reverse gap-2 border-t p-5 sm:flex-row sm:justify-end">
          <button onClick={onClose} className="rounded-lg border px-4 py-2 text-sm font-semibold text-foreground">
            {isView ? "Close" : "Cancel"}
          </button>
          {!isView ? (
            <button
              onClick={onSave}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-sm"
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
