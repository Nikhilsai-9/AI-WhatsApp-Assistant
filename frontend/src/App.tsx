import { useState, useEffect, useCallback } from "react";
import {
  MessageSquare, Users, Brain, Settings, BarChart3, Shield,
  Pause, Play, Trash2, Ban, CheckCircle, Clock, Zap,
  ChevronRight, Wifi, WifiOff, RefreshCw, Moon, Sun,
  MessageCircle, TrendingUp, Database, AlertCircle
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line
} from "recharts";
import { format, formatDistanceToNow } from "date-fns";

// ─── Types ──────────────────────────────────────────────────────

interface DashboardStats {
  total_contacts: number;
  approved_contacts: number;
  pending_contacts: number;
  blocked_contacts: number;
  messages_today: number;
  messages_this_week: number;
  ai_replies_today: number;
  memory_items: number;
  learning_progress: number;
}

interface Contact {
  id: string;
  display_name: string;
  whatsapp_jid: string;
  consent_status: string;
  relationship_type: string;
  message_count: number;
  last_message_at: string | null;
  is_favorite: boolean;
  is_blacklisted: boolean;
}

interface ActivityDay {
  date: string;
  incoming: number;
  outgoing: number;
  ai_replies: number;
}

interface Settings {
  ai_enabled: boolean;
  auto_reply_delay: number;
  filter_otps: boolean;
  filter_bank_messages: boolean;
  filter_spam: boolean;
  filter_promotions: boolean;
  ai_provider: string;
  theme: string;
}

// ─── Token Refresh ──────────────────────────────────────────────

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return false;
  
  try {
    const res = await fetch(`${API}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    
    if (!res.ok) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      return false;
    }
    
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

// ─── API helpers ────────────────────────────────────────────────

const API = "/api";

async function apiFetch(path: string, opts?: RequestInit, _retry = false): Promise<any> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      Authorization: token ? `Bearer ${token}` : "",
      ...opts?.headers,
    },
  });
  
  if (res.status === 401 && !_retry) {
    // Try to refresh token
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch(path, opts, true);
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.hash = "#/login";
    throw new Error("Session expired");
  }
  
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  window.location.hash = "#/login";
}

// ─── Stat Card ──────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType; label: string; value: string | number;
  sub?: string; color: string;
}) {
  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2.5 rounded-xl ${color}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        <span className="text-sm font-medium text-gray-500">{label}</span>
      </div>
      <div className="text-3xl font-bold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

// ─── Status Badge ───────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    approved: { cls: "bg-green-100 text-green-700", label: "Approved" },
    pending: { cls: "bg-yellow-100 text-yellow-700", label: "Pending" },
    denied: { cls: "bg-red-100 text-red-700", label: "Denied" },
    blocked: { cls: "bg-gray-100 text-gray-600", label: "Blocked" },
  };
  const { cls, label } = map[status] || { cls: "bg-gray-100 text-gray-600", label: status };
  return <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${cls}`}>{label}</span>;
}

// ─── Login Page ─────────────────────────────────────────────────

function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showRegister, setShowRegister] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const form = new URLSearchParams({ username: email, password });
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed");
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      onLogin();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name: email.split("@")[0] }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Registration failed");
      // Auto login after register
      const form = new URLSearchParams({ username: email, password });
      const loginRes = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form,
      });
      const loginData = await loginRes.json();
      if (!loginRes.ok) throw new Error(loginData.detail || "Login failed");
      localStorage.setItem("access_token", loginData.access_token);
      localStorage.setItem("refresh_token", loginData.refresh_token);
      onLogin();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (showRegister) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-600 via-emerald-500 to-teal-600 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl shadow-2xl p-8 w-full max-w-md">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <MessageSquare className="w-8 h-8 text-green-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Create Account</h1>
            <p className="text-gray-500 mt-1">Join AI WhatsApp Assistant</p>
          </div>
          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition"
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition"
                placeholder="Create a strong password"
                required
                minLength={8}
              />
            </div>
            {error && (
              <div className="bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm">{error}</div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl transition disabled:opacity-50"
            >
              {loading ? "Creating account..." : "Create Account"}
            </button>
            <button
              type="button"
              onClick={() => setShowRegister(false)}
              className="w-full text-gray-500 hover:text-gray-700 py-2 text-sm"
            >
              Already have an account? Sign In
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-600 via-emerald-500 to-teal-600 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <MessageSquare className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">AI WhatsApp Assistant</h1>
          <p className="text-gray-500 mt-1">Sign in to your dashboard</p>
        </div>
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition"
              placeholder="you@example.com"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition"
              placeholder="••••••••"
              required
            />
          </div>
          {error && (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm">{error}</div>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl transition disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
          <button
            type="button"
            onClick={() => setShowRegister(true)}
            className="w-full text-gray-500 hover:text-gray-700 py-2 text-sm"
          >
            Don't have an account? Create one
          </button>
        </form>
      </div>
    </div>
  );
}

// ─── WhatsApp Setup Page ────────────────────────────────────────

function WhatsAppSetupPage() {
  const [qrData, setQrData] = useState<string | null>(null);
  const [status, setStatus] = useState("connecting");
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/bridge/qr");
      const data = await res.json();
      setStatus(data.status);
      setQrData(data.qr);
    } catch {
      setStatus("error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return (
    <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100 text-center max-w-sm mx-auto">
      <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <MessageCircle className="w-8 h-8 text-green-600" />
      </div>
      <h2 className="text-xl font-bold text-gray-900 mb-2">Connect WhatsApp</h2>
      <p className="text-gray-500 text-sm mb-6">
        Scan the QR code with your WhatsApp to link your account
      </p>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
        </div>
      )}

      {!loading && status === "connected" && (
        <div className="py-8">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-green-600" />
          </div>
          <p className="text-green-600 font-semibold">WhatsApp Connected!</p>
        </div>
      )}

      {!loading && status === "qr_ready" && qrData && (
        <div className="py-4">
          <img src={qrData} alt="WhatsApp QR Code" className="mx-auto rounded-xl w-64 h-64" />
          <p className="text-xs text-gray-400 mt-3">Scan within 60 seconds</p>
        </div>
      )}

      {!loading && status === "disconnected" && (
        <div className="py-8">
          <WifiOff className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">Bridge is starting up...</p>
        </div>
      )}

      <button
        onClick={fetchStatus}
        className="mt-4 text-sm text-green-600 hover:text-green-700 font-medium"
      >
        <RefreshCw className="w-4 h-4 inline mr-1" /> Refresh
      </button>
    </div>
  );
}

// ─── Contacts Page ──────────────────────────────────────────────

function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (filter) params.set("consent_status", filter);
      const data = await apiFetch(`/contacts/?${params}`);
      setContacts(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [search, filter]);

  useEffect(() => { load(); }, [load]);

  const handleConsent = async (id: string, action: string) => {
    await apiFetch("/contacts/consent", {
      method: "POST",
      body: JSON.stringify({ contact_id: id, action }),
    });
    load();
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search contacts..."
          className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 outline-none focus:border-green-500"
        />
        <select
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="px-4 py-2.5 rounded-xl border border-gray-200 outline-none"
        >
          <option value="">All</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="denied">Denied</option>
          <option value="blocked">Blocked</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : contacts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">No contacts found</div>
      ) : (
        <div className="space-y-2">
          {contacts.map(c => (
            <div key={c.id} className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center gap-4">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center text-green-600 font-bold text-lg flex-shrink-0">
                {c.display_name?.[0]?.toUpperCase() || "?"}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-gray-900 truncate">{c.display_name || "Unknown"}</span>
                  <StatusBadge status={c.consent_status} />
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {c.message_count} messages · {c.last_message_at ? formatDistanceToNow(new Date(c.last_message_at), { addSuffix: true }) : "No messages"}
                </div>
              </div>
              <div className="flex gap-1">
                {c.consent_status === "pending" && (
                  <>
                    <button onClick={() => handleConsent(c.id, "approve")} className="p-2 bg-green-50 text-green-600 rounded-lg hover:bg-green-100" title="Approve">
                      <CheckCircle className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleConsent(c.id, "deny")} className="p-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100" title="Deny">
                      <Ban className="w-4 h-4" />
                    </button>
                  </>
                )}
                {c.consent_status === "approved" && (
                  <button onClick={() => handleConsent(c.id, "block")} className="p-2 bg-gray-50 text-gray-500 rounded-lg hover:bg-gray-100" title="Block">
                    <Ban className="w-4 h-4" />
                  </button>
                )}
                {c.consent_status === "blocked" && (
                  <button onClick={() => handleConsent(c.id, "unblock")} className="p-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100" title="Unblock">
                    <CheckCircle className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Settings Page ──────────────────────────────────────────────

function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiFetch("/settings/").then(s => { setSettings(s); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const update = (key: string, value: any) => {
    setSettings(s => s ? { ...s, [key]: value } : s);
  };

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await apiFetch("/settings/", { method: "PATCH", body: JSON.stringify(settings) });
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) return <div className="text-center py-12 text-gray-400">Loading...</div>;

  return (
    <div className="space-y-6 max-w-2xl">
      {/* AI Control */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5 text-green-600" /> AI Control
        </h3>
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-gray-800">AI Assistant</p>
            <p className="text-sm text-gray-500">{settings.ai_enabled ? "Responding to messages" : "Paused"}</p>
          </div>
          <button
            onClick={() => update("ai_enabled", !settings.ai_enabled)}
            className={`relative w-14 h-7 rounded-full transition-colors ${settings.ai_enabled ? "bg-green-500" : "bg-gray-300"}`}
          >
            <span className={`absolute top-1 w-5 h-5 bg-white rounded-full shadow transition-transform ${settings.ai_enabled ? "left-8" : "left-1"}`} />
          </button>
        </div>
        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Reply Delay (seconds)</label>
          <input
            type="number"
            value={settings.auto_reply_delay}
            onChange={e => update("auto_reply_delay", parseInt(e.target.value))}
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 outline-none"
            min={0}
            max={300}
          />
        </div>
        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">AI Provider</label>
          <select
            value={settings.ai_provider}
            onChange={e => update("ai_provider", e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 outline-none"
          >
            <option value="gemini">Google Gemini</option>
            <option value="openai">OpenAI GPT-4</option>
            <option value="anthropic">Anthropic Claude</option>
            <option value="openrouter">OpenRouter</option>
            <option value="minimax">MiniMax</option>
            <option value="ollama">Local Ollama</option>
          </select>
        </div>
      </div>

      {/* Smart Filters */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-green-600" /> Smart Filters
        </h3>
        {[
          { key: "filter_otps", label: "Block OTP Messages" },
          { key: "filter_bank_messages", label: "Block Bank Messages" },
          { key: "filter_spam", label: "Block Spam" },
          { key: "filter_promotions", label: "Block Promotions" },
        ].map(({ key, label }) => (
          <div key={key} className="flex items-center justify-between py-2">
            <span className="text-gray-700">{label}</span>
            <button
              onClick={() => update(key, !settings[key as keyof Settings])}
              className={`relative w-12 h-6 rounded-full transition-colors ${settings[key as keyof Settings] ? "bg-green-500" : "bg-gray-300"}`}
            >
              <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${settings[key as keyof Settings] ? "left-6" : "left-0.5"}`} />
            </button>
          </div>
        ))}
      </div>

      {/* Appearance */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Sun className="w-5 h-5 text-green-600" /> Appearance
        </h3>
        <div className="flex gap-3">
          {["light", "dark", "system"].map(t => (
            <button
              key={t}
              onClick={() => update("theme", t)}
              className={`flex-1 py-2.5 rounded-xl border-2 font-medium capitalize transition ${settings.theme === t ? "border-green-500 bg-green-50 text-green-700" : "border-gray-200 text-gray-600"}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={save}
        disabled={saving}
        className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl transition disabled:opacity-50"
      >
        {saving ? "Saving..." : "Save Settings"}
      </button>
    </div>
  );
}

// ─── Main App ───────────────────────────────────────────────────

export default function App() {
  const [page, setPage] = useState<"dashboard" | "contacts" | "settings" | "setup">("dashboard");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityDay[]>([]);
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem("access_token"));
  const [loading, setLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    try {
      const [statsData, activityData] = await Promise.all([
        apiFetch("/dashboard/stats"),
        apiFetch("/dashboard/activity?days=7"),
      ]);
      setStats(statsData);
      setActivity(activityData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isLoggedIn) loadDashboard();
    else setLoading(false);
  }, [isLoggedIn, loadDashboard]);

  if (!isLoggedIn) return <LoginPage onLogin={() => setIsLoggedIn(true)} />;

  const navItems = [
    { id: "dashboard", icon: BarChart3, label: "Dashboard" },
    { id: "contacts", icon: Users, label: "Contacts" },
    { id: "setup", icon: MessageCircle, label: "WhatsApp" },
    { id: "settings", icon: Settings, label: "Settings" },
  ] as const;

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col fixed h-full">
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-600 rounded-xl flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-gray-900 text-sm">AI Assistant</h1>
              <p className="text-xs text-gray-400">WhatsApp Bot</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => setPage(id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition font-medium ${
                page === id ? "bg-green-50 text-green-700" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              <Icon className="w-5 h-5" />
              {label}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center gap-2 px-4 py-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs text-gray-500">System Online</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-64 p-8">
        {page === "dashboard" && (
          <div className="max-w-6xl">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
              <p className="text-gray-500 mt-1">Overview of your AI WhatsApp Assistant</p>
            </div>

            {loading ? (
              <div className="text-center py-20 text-gray-400">Loading dashboard...</div>
            ) : stats ? (
              <>
                {/* Stats Grid */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                  <StatCard icon={Users} label="Total Contacts" value={stats.total_contacts} color="bg-blue-500" />
                  <StatCard icon={CheckCircle} label="Approved" value={stats.approved_contacts} color="bg-green-500" />
                  <StatCard icon={Clock} label="Pending" value={stats.pending_contacts} color="bg-yellow-500" />
                  <StatCard icon={Ban} label="Blocked" value={stats.blocked_contacts} color="bg-red-500" />
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                  <StatCard icon={MessageSquare} label="Messages Today" value={stats.messages_today} color="bg-purple-500" />
                  <StatCard icon={Zap} label="AI Replies Today" value={stats.ai_replies_today} color="bg-orange-500" />
                  <StatCard icon={Database} label="Memory Items" value={stats.memory_items} color="bg-cyan-500" />
                  <StatCard icon={Brain} label="Learning" value={`${Math.round(stats.learning_progress)}%`} color="bg-pink-500" />
                </div>

                {/* Activity Chart */}
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 mb-8">
                  <h3 className="font-semibold text-gray-900 mb-4">Message Activity (7 Days)</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={activity}>
                      <XAxis dataKey="date" tickFormatter={d => format(new Date(d), "EEE")} tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip formatter={(v, n) => [String(v), n]} labelFormatter={d => format(new Date(d), "MMM d")} />
                      <Bar dataKey="incoming" name="Incoming" fill="#22c55e" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="ai_replies" name="AI Replies" fill="#f97316" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Quick Actions */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <button onClick={() => setPage("contacts")} className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 text-left hover:shadow-md transition">
                    <Users className="w-8 h-8 text-blue-500 mb-3" />
                    <h4 className="font-semibold text-gray-900">Manage Contacts</h4>
                    <p className="text-sm text-gray-500 mt-1">Approve or block contacts</p>
                  </button>
                  <button onClick={() => setPage("setup")} className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 text-left hover:shadow-md transition">
                    <MessageCircle className="w-8 h-8 text-green-500 mb-3" />
                    <h4 className="font-semibold text-gray-900">WhatsApp Setup</h4>
                    <p className="text-sm text-gray-500 mt-1">Scan QR to connect</p>
                  </button>
                  <button onClick={() => setPage("settings")} className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 text-left hover:shadow-md transition">
                    <Settings className="w-8 h-8 text-gray-500 mb-3" />
                    <h4 className="font-semibold text-gray-900">Settings</h4>
                    <p className="text-sm text-gray-500 mt-1">Configure AI behavior</p>
                  </button>
                </div>
              </>
            ) : null}
          </div>
        )}

        {page === "contacts" && (
          <div className="max-w-4xl">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Contacts</h2>
              <p className="text-gray-500 mt-1">Manage your WhatsApp contacts and consent</p>
            </div>
            <ContactsPage />
          </div>
        )}

        {page === "setup" && (
          <div className="max-w-4xl">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">WhatsApp Setup</h2>
              <p className="text-gray-500 mt-1">Connect your WhatsApp account via QR code</p>
            </div>
            <WhatsAppSetupPage />
          </div>
        )}

        {page === "settings" && (
          <div className="max-w-4xl">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Settings</h2>
              <p className="text-gray-500 mt-1">Configure your AI assistant behavior</p>
            </div>
            <SettingsPage />
          </div>
        )}
      </main>
    </div>
  );
}