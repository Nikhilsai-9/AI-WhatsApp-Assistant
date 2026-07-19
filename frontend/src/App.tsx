import { useState, useEffect, useCallback, useRef } from "react";
import {
  MessageSquare, Users, Brain, Settings as SettingsIcon, BarChart3, Shield,
  Pause, Play, Power, Trash2, AlertTriangle, CheckCircle, Clock, Zap,
  Wifi, WifiOff, RefreshCw, Moon, Sun,
  MessageCircle, Database, Send, Mail, Phone, Eye, EyeOff,
  LogOut, Activity, Calendar, ListTodo, Menu, X, Globe, Lock,
  Bell, Download, Upload, Trash, ChevronRight, ExternalLink,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, AreaChart, Area, CartesianGrid,
} from "recharts";
import { format, formatDistanceToNow } from "date-fns";

// ────────────────────────────────────────────────────────────────
// API helpers
// ────────────────────────────────────────────────────────────────
const API = import.meta.env.VITE_API_URL || "/api";

interface Tokens {
  access: string; refresh: string;
}

function getTokens(): Tokens | null {
  const access = localStorage.getItem("access_token");
  const refresh = localStorage.getItem("refresh_token");
  return access && refresh ? { access, refresh } : null;
}
function setTokens(t: Tokens) {
  localStorage.setItem("access_token", t.access);
  localStorage.setItem("refresh_token", t.refresh);
}
function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function refreshAccessToken(): Promise<boolean> {
  const t = getTokens();
  if (!t) return false;
  try {
    const res = await fetch(`${API}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: t.refresh }),
    });
    if (!res.ok) { clearTokens(); return false; }
    const data = await res.json();
    setTokens({ access: data.access_token, refresh: data.refresh_token });
    return true;
  } catch { clearTokens(); return false; }
}

async function apiFetch(path: string, opts?: RequestInit, _retry = false): Promise<any> {
  const t = getTokens();
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(t ? { Authorization: `Bearer ${t.access}` } : {}),
      ...opts?.headers,
    },
  });
  if (res.status === 401 && !_retry) {
    const ok = await refreshAccessToken();
    if (ok) return apiFetch(path, opts, true);
    clearTokens();
    window.location.hash = "#/login";
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

// ────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────
interface User {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  is_active: boolean;
  email_verified: boolean;
  is_ai_enabled: boolean;
  ai_emergency_stop: boolean;
  created_at: string;
}

interface DashboardStats {
  total_contacts: number;
  approved_contacts: number;
  pending_contacts: number;
  blocked_contacts: number;
  messages_today: number;
  messages_this_week: number;
  ai_replies_today: number;
  memory_items: number;
}

interface ActivityDay { date: string; incoming: number; outgoing: number; ai_replies: number; }

// ────────────────────────────────────────────────────────────────
// UI primitives
// ────────────────────────────────────────────────────────────────
function Toggle({
  checked, onChange, disabled,
}: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={() => !disabled && onChange(!checked)}
      aria-pressed={checked}
      className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
        checked ? "bg-green-500" : "bg-gray-300"
      } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-2xl p-5 shadow-sm border border-gray-100 ${className}`}>
      {children}
    </div>
  );
}

function StatCard({
  icon: Icon, label, value, sub, color,
}: {
  icon: React.ElementType; label: string; value: React.ReactNode; sub?: string;
  color: string;
}) {
  return (
    <Card>
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2.5 rounded-xl ${color}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        <span className="text-sm font-medium text-gray-500">{label}</span>
      </div>
      <div className="text-2xl md:text-3xl font-bold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </Card>
  );
}

function Button({
  children, onClick, variant = "primary", disabled, type = "button", className = "",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}) {
  const variants: Record<string, string> = {
    primary: "bg-green-600 hover:bg-green-700 text-white",
    secondary: "bg-gray-100 hover:bg-gray-200 text-gray-800",
    danger: "bg-red-600 hover:bg-red-700 text-white",
    ghost: "bg-transparent hover:bg-gray-100 text-gray-700",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`px-4 py-2.5 rounded-xl font-semibold transition disabled:opacity-50 ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

function Input(
  props: React.InputHTMLAttributes<HTMLInputElement> & { label?: string },
) {
  const { label, className, ...rest } = props;
  return (
    <div>
      {label && <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>}
      <input
        {...rest}
        className={`w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition ${className || ""}`}
      />
    </div>
  );
}

function Spinner({ className = "w-5 h-5" }: { className?: string }) {
  return <RefreshCw className={`animate-spin text-gray-400 ${className}`} />;
}

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

// ────────────────────────────────────────────────────────────────
// Login / Register
// ────────────────────────────────────────────────────────────────
function AuthPage({ onAuth }: { onAuth: () => void }) {
  const [mode, setMode] = useState<"login" | "register" | "forgot" | "verify" | "reset">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  // For verify/reset from email link
  useEffect(() => {
    const hash = window.location.hash;
    const url = new URL(window.location.href);
    const token = url.searchParams.get("token") || hash.split("token=")[1]?.split("&")[0];
    if (token) {
      const hashMode = hash.includes("/reset-password") ? "reset" : hash.includes("/verify-email") ? "verify" : null;
      if (hashMode) setMode(hashMode);
    }
  }, []);

  const doLogin = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setInfo(""); setLoading(true);
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Login failed");
      setTokens({ access: data.access_token, refresh: data.refresh_token });
      onAuth();
    } catch (err: any) { setError(err.message); }
    finally { setLoading(false); }
  };

  const doRegister = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setInfo(""); setLoading(true);
    try {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name: name }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Registration failed");
      setTokens({ access: data.access_token, refresh: data.refresh_token });
      onAuth();
    } catch (err: any) { setError(err.message); }
    finally { setLoading(false); }
  };

  const doGoogle = async () => {
    // @ts-expect-error - google is added by the GIS script
    if (typeof google === "undefined" || !google?.accounts?.id) {
      setError("Google Sign-In is not configured. Please set VITE_GOOGLE_CLIENT_ID.");
      return;
    }
    // @ts-expect-error
    google.accounts.id.initialize({
      client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
      callback: async (response: any) => {
        try {
          const res = await fetch(`${API}/auth/google`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: response.credential }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Google login failed");
          setTokens({ access: data.access_token, refresh: data.refresh_token });
          onAuth();
        } catch (err: any) { setError(err.message); }
      },
    });
    // @ts-expect-error
    google.accounts.id.prompt();
  };

  const doForgot = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setInfo(""); setLoading(true);
    try {
      const res = await fetch(`${API}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      setInfo(data.message || "If an account exists, a reset link has been sent.");
    } catch (err: any) { setError(err.message); }
    finally { setLoading(false); }
  };

  const doVerify = async (token: string) => {
    setError(""); setInfo(""); setLoading(true);
    try {
      const res = await fetch(`${API}/auth/verify-email`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Verification failed");
      setInfo("Email verified! You can now sign in.");
      setMode("login");
    } catch (err: any) { setError(err.message); }
    finally { setLoading(false); }
  };

  const doReset = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setInfo(""); setLoading(true);
    const token = new URL(window.location.href).searchParams.get("token") || window.location.hash.split("token=")[1]?.split("&")[0];
    try {
      const res = await fetch(`${API}/auth/reset-password`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Reset failed");
      setInfo("Password reset successfully. Please log in.");
      setMode("login");
    } catch (err: any) { setError(err.message); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (mode === "verify") {
      const token = new URL(window.location.href).searchParams.get("token") || window.location.hash.split("token=")[1]?.split("&")[0];
      if (token) doVerify(token);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-600 via-emerald-500 to-teal-600 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl p-6 md:p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <MessageSquare className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            {mode === "login" && "Welcome back"}
            {mode === "register" && "Create account"}
            {mode === "forgot" && "Reset password"}
            {mode === "verify" && "Verifying email…"}
            {mode === "reset" && "Set a new password"}
          </h1>
          <p className="text-gray-500 mt-1 text-sm">
            {mode === "login" && "Sign in to your AI assistant"}
            {mode === "register" && "Get started in seconds"}
            {mode === "forgot" && "We'll email you a reset link"}
            {mode === "verify" && "Confirming your email address"}
            {mode === "reset" && "Choose a strong password"}
          </p>
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm mb-4">{error}</div>
        )}
        {info && (
          <div className="bg-green-50 text-green-700 px-4 py-3 rounded-xl text-sm mb-4">{info}</div>
        )}

        {mode === "login" && (
          <form onSubmit={doLogin} className="space-y-4">
            <Input label="Email" type="email" value={email} required
              onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPwd ? "text" : "password"}
                  value={password}
                  required
                  minLength={8}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition pr-12"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                  {showPwd ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Signing in…" : "Sign In"}
            </Button>

            <div className="relative my-4">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-white px-3 text-gray-400">Or continue with</span>
              </div>
            </div>

            <Button type="button" variant="secondary" className="w-full" onClick={doGoogle}>
              <svg className="w-5 h-5 inline mr-2" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Continue with Google
            </Button>

            <div className="flex justify-between text-sm pt-2">
              <button type="button" onClick={() => setMode("forgot")} className="text-green-600 hover:underline">
                Forgot password?
              </button>
              <button type="button" onClick={() => setMode("register")} className="text-green-600 hover:underline">
                Create account
              </button>
            </div>
          </form>
        )}

        {mode === "register" && (
          <form onSubmit={doRegister} className="space-y-4">
            <Input label="Full name" type="text" value={name} required
              onChange={e => setName(e.target.value)} placeholder="Your name" />
            <Input label="Email" type="email" value={email} required
              onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <div className="relative">
                <input type={showPwd ? "text" : "password"} value={password}
                  required minLength={8} onChange={e => setPassword(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-green-500 focus:ring-2 focus:ring-green-100 outline-none transition pr-12"
                  placeholder="At least 8 characters" />
                <button type="button" onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                  {showPwd ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Creating account…" : "Create account"}
            </Button>
            <p className="text-xs text-gray-400 text-center">
              By signing up you agree to our Terms & Privacy.
            </p>
            <div className="text-center text-sm">
              <button type="button" onClick={() => setMode("login")} className="text-green-600 hover:underline">
                Already have an account? Sign in
              </button>
            </div>
          </form>
        )}

        {mode === "forgot" && (
          <form onSubmit={doForgot} className="space-y-4">
            <Input label="Email" type="email" value={email} required
              onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Sending…" : "Send reset link"}
            </Button>
            <div className="text-center text-sm">
              <button type="button" onClick={() => setMode("login")} className="text-green-600 hover:underline">
                Back to sign in
              </button>
            </div>
          </form>
        )}

        {mode === "reset" && (
          <form onSubmit={doReset} className="space-y-4">
            <Input label="New password" type="password" value={password}
              required minLength={8} onChange={e => setPassword(e.target.value)}
              placeholder="At least 8 characters" />
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Resetting…" : "Reset password"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Sidebar / Layout
// ────────────────────────────────────────────────────────────────
function Layout({
  children, page, onNavigate, onLogout, user, aiState,
}: {
  children: React.ReactNode;
  page: Page;
  onNavigate: (p: Page) => void;
  onLogout: () => void;
  user: User;
  aiState: { enabled: boolean; paused: boolean; emergency: boolean };
}) {
  const [open, setOpen] = useState(false);
  const navItems: { id: Page; icon: React.ElementType; label: string }[] = [
    { id: "dashboard", icon: BarChart3, label: "Dashboard" },
    { id: "ai", icon: Brain, label: "AI Assistant" },
    { id: "whatsapp", icon: MessageCircle, label: "WhatsApp" },
    { id: "contacts", icon: Users, label: "Contacts" },
    { id: "messages", icon: MessageSquare, label: "Messages" },
    { id: "reports", icon: Activity, label: "Reports" },
    { id: "settings", icon: SettingsIcon, label: "Settings" },
  ];

  const close = () => setOpen(false);

  const aiBadge = aiState.emergency ? (
    <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full text-xs font-semibold">STOPPED</span>
  ) : aiState.paused ? (
    <span className="bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full text-xs font-semibold">PAUSED</span>
  ) : aiState.enabled ? (
    <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full text-xs font-semibold">ACTIVE</span>
  ) : (
    <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full text-xs font-semibold">OFF</span>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile top bar */}
      <header className="md:hidden sticky top-0 z-30 bg-white border-b border-gray-100 flex items-center justify-between px-4 py-3">
        <button onClick={() => setOpen(true)} className="p-2 -ml-2 text-gray-700">
          <Menu className="w-6 h-6" />
        </button>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-green-600 rounded-lg flex items-center justify-center">
            <MessageSquare className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-gray-900">AI Assistant</span>
        </div>
        {aiBadge}
      </header>

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 flex flex-col transform transition-transform duration-200
        ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0
      `}>
        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-600 rounded-xl flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-gray-900 text-sm leading-tight">AI Assistant</h1>
              <p className="text-xs text-gray-400">WhatsApp · Powered</p>
            </div>
          </div>
          <button onClick={close} className="md:hidden text-gray-400 hover:text-gray-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => { onNavigate(id); close(); }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition font-medium ${
                page === id ? "bg-green-50 text-green-700" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="flex-1">{label}</span>
              {page === id && <ChevronRight className="w-4 h-4" />}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-100 space-y-3">
          <div className="flex items-center gap-3 px-2">
            {user.avatar_url ? (
              <img src={user.avatar_url} alt="" className="w-9 h-9 rounded-full object-cover" />
            ) : (
              <div className="w-9 h-9 bg-green-100 rounded-full flex items-center justify-center text-green-700 font-bold">
                {(user.full_name || user.email)[0].toUpperCase()}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-gray-900 truncate">
                {user.full_name || user.email}
              </p>
              <p className="text-xs text-gray-400 truncate">{user.email}</p>
            </div>
          </div>
          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${aiState.emergency ? "bg-red-500" : aiState.paused || !aiState.enabled ? "bg-yellow-500" : "bg-green-500"} animate-pulse`} />
              <span className="text-xs text-gray-500">
                AI {aiBadge.props.children}
              </span>
            </div>
            <button onClick={onLogout} title="Sign out" className="text-gray-400 hover:text-red-600">
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </aside>

      {open && (
        <div onClick={close} className="fixed inset-0 bg-black/30 z-30 md:hidden" />
      )}

      <main className="md:ml-64 p-4 md:p-8">
        <div className="max-w-6xl mx-auto">{children}</div>
      </main>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Dashboard
// ────────────────────────────────────────────────────────────────
function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityDay[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([
        apiFetch("/dashboard/stats").catch(() => null),
        apiFetch("/dashboard/activity?days=7").catch(() => []),
      ]);
      setStats(s);
      setActivity(a);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="text-center py-20"><Spinner className="w-8 h-8" /></div>;

  return (
    <div>
      <div className="mb-6 md:mb-8">
        <h2 className="text-2xl md:text-3xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-gray-500 mt-1">Overview of your AI WhatsApp Assistant</p>
      </div>

      {stats ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6 md:mb-8">
          <StatCard icon={Users} label="Total Contacts" value={stats.total_contacts} color="bg-blue-500" />
          <StatCard icon={CheckCircle} label="Approved" value={stats.approved_contacts} color="bg-green-500" />
          <StatCard icon={Clock} label="Pending" value={stats.pending_contacts} color="bg-yellow-500" />
          <StatCard icon={Shield} label="Blocked" value={stats.blocked_contacts} color="bg-red-500" />
          <StatCard icon={MessageSquare} label="Messages Today" value={stats.messages_today} color="bg-purple-500" />
          <StatCard icon={Zap} label="AI Replies Today" value={stats.ai_replies_today} color="bg-orange-500" />
          <StatCard icon={Database} label="Memory Items" value={stats.memory_items} color="bg-cyan-500" />
          <StatCard icon={Brain} label="This Week" value={stats.messages_this_week} color="bg-pink-500" />
        </div>
      ) : (
        <Card className="text-center py-12">
          <Brain className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-gray-700">Welcome aboard! 🎉</h3>
          <p className="text-gray-500 mt-1 max-w-md mx-auto">
            Connect your WhatsApp to start using the AI assistant. Your dashboard will populate once your first message arrives.
          </p>
        </Card>
      )}

      {activity.length > 0 && (
        <Card className="mb-6 md:mb-8">
          <h3 className="font-semibold text-gray-900 mb-4">Activity (last 7 days)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={activity}>
              <defs>
                <linearGradient id="gIn" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22c55e" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gAi" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f97316" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#f97316" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tickFormatter={d => format(new Date(d), "EEE")} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v, n) => [String(v), n]} labelFormatter={d => format(new Date(d), "MMM d")} />
              <Area type="monotone" dataKey="incoming" name="Incoming" stroke="#22c55e" fill="url(#gIn)" />
              <Area type="monotone" dataKey="ai_replies" name="AI Replies" stroke="#f97316" fill="url(#gAi)" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// AI Control Page
// ────────────────────────────────────────────────────────────────
function AIPage({
  aiState, onChange, onEmergency, aiEnabled,
}: {
  aiState: { enabled: boolean; paused: boolean; emergency: boolean };
  onChange: (s: { enabled: boolean; paused: boolean }) => void;
  onEmergency: (enabled: boolean) => Promise<void>;
  aiEnabled: boolean;
}) {
  const [emergencyLoading, setEmergencyLoading] = useState(false);
  const [confirmEmergency, setConfirmEmergency] = useState(false);

  const handleEmergency = async () => {
    setEmergencyLoading(true);
    try { await onEmergency(!aiState.emergency); }
    finally { setEmergencyLoading(false); setConfirmEmergency(false); }
  };

  return (
    <div>
      <div className="mb-6 md:mb-8">
        <h2 className="text-2xl md:text-3xl font-bold text-gray-900">AI Assistant</h2>
        <p className="text-gray-500 mt-1">Control how the AI responds to your messages</p>
      </div>

      {/* Master Status */}
      <Card className="mb-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${
              aiState.emergency ? "bg-red-100" : aiState.paused || !aiState.enabled ? "bg-yellow-100" : "bg-green-100"
            }`}>
              {aiState.emergency ? (
                <AlertTriangle className="w-7 h-7 text-red-600" />
              ) : aiState.enabled && !aiState.paused ? (
                <Brain className="w-7 h-7 text-green-600" />
              ) : (
                <Pause className="w-7 h-7 text-yellow-600" />
              )}
            </div>
            <div>
              <p className="text-lg font-bold text-gray-900">
                {aiState.emergency
                  ? "Emergency Stop Active"
                  : !aiState.enabled
                    ? "AI Disabled"
                    : aiState.paused
                      ? "AI Paused"
                      : "AI Active"}
              </p>
              <p className="text-sm text-gray-500">
                {aiState.emergency
                  ? "All AI operations are halted."
                  : !aiState.enabled
                    ? "The assistant will not respond to any chat."
                    : aiState.paused
                      ? "Resume when you're ready."
                      : "Ready to help you in real time."}
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* Granular Controls */}
      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        <Card>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-gray-900">Enable AI</p>
              <p className="text-sm text-gray-500 mt-1">Master switch for all AI operations</p>
            </div>
            <Toggle
              checked={aiState.enabled && !aiState.emergency}
              disabled={aiState.emergency}
              onChange={v => onChange({ enabled: v, paused: aiState.paused })}
            />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-gray-900">Pause</p>
              <p className="text-sm text-gray-500 mt-1">
                {aiState.paused ? "Currently paused" : "Temporarily quiet"}
              </p>
            </div>
            <Toggle
              checked={aiState.paused}
              disabled={!aiState.enabled || aiState.emergency}
              onChange={v => onChange({ enabled: aiState.enabled, paused: v })}
            />
          </div>
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-gray-900">Resume</p>
              <p className="text-sm text-gray-500 mt-1">Back to full speed</p>
            </div>
            <Button
              variant="secondary"
              onClick={() => onChange({ enabled: true, paused: false })}
              disabled={!aiState.enabled || (!aiState.paused && !aiState.emergency)}
            >
              <Play className="w-4 h-4 inline mr-2" /> Resume
            </Button>
          </div>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card className="mb-6">
        <h3 className="font-semibold text-gray-900 mb-4">Quick Actions</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          <Button variant="secondary" onClick={() => onChange({ enabled: aiState.enabled, paused: true })} disabled={aiState.emergency}>
            <Pause className="w-4 h-4 inline mr-2" /> Pause AI
          </Button>
          <Button variant="secondary" onClick={() => onChange({ enabled: false, paused: false })} disabled={aiState.emergency}>
            <Power className="w-4 h-4 inline mr-2" /> Disable AI
          </Button>
          <Button variant="secondary" onClick={() => onChange({ enabled: true, paused: false })} disabled={aiState.emergency}>
            <Play className="w-4 h-4 inline mr-2" /> Resume
          </Button>
          <Button
            variant="danger"
            onClick={() => onChange({ enabled: true, paused: false })}
            disabled={aiState.emergency}
          >
            <RefreshCw className="w-4 h-4 inline mr-2" /> Restart AI Logic
          </Button>
        </div>
      </Card>

      {/* Emergency Kill Switch */}
      <Card className="border-2 border-red-200 bg-red-50">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 bg-red-600 rounded-xl flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-red-900">Emergency Kill Switch</h3>
            <p className="text-sm text-red-700 mt-1">
              Immediately halts every AI action across all chats. Use if the AI is misbehaving.
            </p>
            {confirmEmergency ? (
              <div className="mt-4 space-y-3">
                <p className="text-sm font-semibold text-red-900">
                  Are you absolutely sure? This will stop EVERYTHING immediately.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button variant="danger" disabled={emergencyLoading} onClick={handleEmergency}>
                    {emergencyLoading ? "Stopping…" : aiState.emergency ? "Already STOPPED" : "YES — STOP EVERYTHING"}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirmEmergency(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-4">
                {aiState.emergency ? (
                  <Button variant="primary" disabled={emergencyLoading} onClick={handleEmergency}>
                    {emergencyLoading ? "Resuming…" : "Clear Emergency Stop"}
                  </Button>
                ) : (
                  <Button variant="danger" onClick={() => setConfirmEmergency(true)}>
                    <AlertTriangle className="w-4 h-4 inline mr-2" /> Activate Emergency Stop
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// WhatsApp Setup
// ────────────────────────────────────────────────────────────────
function WhatsAppPage() {
  const [status, setStatus] = useState<string>("connecting");
  const [qr, setQr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const t = getTokens();
      const res = await fetch(`${API}/contacts/bridge/status`, {
        headers: t ? { Authorization: `Bearer ${t.access}` } : {},
      }).catch(() => null);
      if (res && res.ok) {
        const data = await res.json();
        setStatus(data.status);
        setQr(data.qr || null);
      } else {
        // Fallback — try public bridge endpoint
        const r2 = await fetch("/bridge/qr");
        if (r2.ok) {
          const d = await r2.json();
          setStatus(d.status);
          setQr(d.qr);
        } else {
          setStatus("disconnected");
        }
      }
    } catch {
      setStatus("error");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 3000);
    return () => clearInterval(iv);
  }, [load]);

  return (
    <div>
      <div className="mb-6 md:mb-8">
        <h2 className="text-2xl md:text-3xl font-bold text-gray-900">WhatsApp</h2>
        <p className="text-gray-500 mt-1">Connect your account and manage integration</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4">Connection Status</h3>
          <div className="text-center py-8">
            {loading && <Spinner className="w-12 h-12 mx-auto mb-4" />}
            {!loading && status === "connected" && (
              <>
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircle className="w-8 h-8 text-green-600" />
                </div>
                <p className="text-green-700 font-semibold text-lg">WhatsApp Connected!</p>
                <p className="text-sm text-gray-500 mt-2">Your assistant is ready to help.</p>
              </>
            )}
            {!loading && status === "qr_ready" && qr && (
              <>
                <img src={qr} alt="WhatsApp QR Code" className="mx-auto rounded-xl w-64 h-64 border-4 border-white shadow" />
                <p className="text-xs text-gray-400 mt-3">Scan with WhatsApp to link</p>
              </>
            )}
            {!loading && status === "disconnected" && (
              <>
                <WifiOff className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-600 font-medium">Bridge is offline</p>
                <p className="text-sm text-gray-400 mt-1">The QR generator will appear as soon as it's ready.</p>
              </>
            )}
            <button onClick={load} className="mt-4 text-sm text-green-600 hover:text-green-700 font-medium inline-flex items-center gap-1">
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </Card>

        <Card>
          <h3 className="font-semibold text-gray-900 mb-4">How to connect</h3>
          <ol className="space-y-3 text-sm text-gray-600">
            <li className="flex gap-3"><span className="w-6 h-6 bg-green-100 text-green-700 rounded-full flex items-center justify-center font-bold flex-shrink-0">1</span>Open WhatsApp on your phone</li>
            <li className="flex gap-3"><span className="w-6 h-6 bg-green-100 text-green-700 rounded-full flex items-center justify-center font-bold flex-shrink-0">2</span>Go to Settings → Linked Devices</li>
            <li className="flex gap-3"><span className="w-6 h-6 bg-green-100 text-green-700 rounded-full flex items-center justify-center font-bold flex-shrink-0">3</span>Tap "Link a Device"</li>
            <li className="flex gap-3"><span className="w-6 h-6 bg-green-100 text-green-700 rounded-full flex items-center justify-center font-bold flex-shrink-0">4</span>Scan the QR code here</li>
          </ol>
          <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded-xl text-xs">
            💡 Sessions are end-to-end encrypted — we never see your messages directly.
          </div>
        </Card>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Contacts (simplified)
// ────────────────────────────────────────────────────────────────
function ContactsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (filter) params.set("consent_status", filter);
      const data = await apiFetch(`/contacts/?${params}`).catch(() => []);
      setItems(data);
    } finally { setLoading(false); }
  }, [search, filter]);

  useEffect(() => { load(); }, [load]);

  const consent = async (id: string, action: string) => {
    await apiFetch("/contacts/consent", {
      method: "POST",
      body: JSON.stringify({ contact_id: id, action }),
    });
    load();
  };

  return (
    <div>
      <div className="mb-6 md:mb-8">
        <h2 className="text-2xl md:text-3xl font-bold text-gray-900">Contacts</h2>
        <p className="text-gray-500 mt-1">Manage consent and visibility for every chat</p>
      </div>
      <Card className="mb-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <Input placeholder="Search contacts…" value={search}
            onChange={e => setSearch(e.target.value)} className="flex-1" />
          <select
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="px-4 py-3 rounded-xl border border-gray-200 outline-none bg-white"
          >
            <option value="">All status</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="denied">Denied</option>
            <option value="blocked">Blocked</option>
          </select>
        </div>
      </Card>

      {loading ? (
        <div className="text-center py-12"><Spinner /></div>
      ) : items.length === 0 ? (
        <Card className="text-center py-12 text-gray-400">No contacts found</Card>
      ) : (
        <div className="space-y-2">
          {items.map((c: any) => (
            <Card key={c.id} className="!p-3 flex items-center gap-3">
              <div className="w-11 h-11 bg-green-100 rounded-full flex items-center justify-center text-green-600 font-bold flex-shrink-0">
                {c.display_name?.[0]?.toUpperCase() || "?"}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-semibold text-gray-900 truncate">{c.display_name || "Unknown"}</p>
                  <StatusBadge status={c.consent_status} />
                </div>
                <p className="text-xs text-gray-400 mt-0.5 truncate">
                  {c.message_count} msgs · {c.last_message_at
                    ? formatDistanceToNow(new Date(c.last_message_at), { addSuffix: true })
                    : "No messages yet"}
                </p>
              </div>
              <div className="flex gap-1">
                {c.consent_status === "pending" && (
                  <>
                    <button onClick={() => consent(c.id, "approve")}
                      className="p-2 bg-green-50 text-green-600 rounded-lg hover:bg-green-100" title="Approve">
                      <CheckCircle className="w-4 h-4" />
                    </button>
                    <button onClick={() => consent(c.id, "deny")}
                      className="p-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100" title="Deny">
                      <Shield className="w-4 h-4" />
                    </button>
                  </>
                )}
                {c.consent_status === "approved" && (
                  <button onClick={() => consent(c.id, "block")}
                    className="p-2 bg-gray-50 text-gray-500 rounded-lg hover:bg-gray-100" title="Block">
                    <Shield className="w-4 h-4" />
                  </button>
                )}
                {c.consent_status === "blocked" && (
                  <button onClick={() => consent(c.id, "unblock")}
                    className="p-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100" title="Unblock">
                    <CheckCircle className="w-4 h-4" />
                  </button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Messages (placeholder)
// ────────────────────────────────────────────────────────────────
function MessagesPage() {
  return (
    <div>
      <div className="mb-6 md:mb-8">
        <h2 className="text-2xl md:text-3xl font-bold text-gray-900">Messages</h2>
        <p className="text-gray-500 mt-1">View handled and pending conversations</p>
      </div>
      <Card className="text-center py-12">
        <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500">Your handled message history will appear here.</p>
        <p className="text-xs text-gray-400 mt-1">Once WhatsApp is connected and messages flow, you'll see them.</p>
      </Card>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Reports
// ────────────────────────────────────────────────────────────────
function ReportsPage() {
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/dashboard/daily-report").catch(() => ({
        date: new Date().toISOString(),
        summary: "Connect WhatsApp to start collecting statistics.",
        messages_handled: 0,
        ai_replies: 0,
      }));
      setReport(data);
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="mb-6 md:mb-8 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold text-gray-900">Daily Reports</h2>
          <p className="text-gray-500 mt-1">A summary of every handled conversation</p>
        </div>
        <Button onClick={generate} disabled={loading}>
          {loading ? "Generating…" : "Generate Now"}
        </Button>
      </div>

      {report ? (
        <Card>
          <div className="flex items-start gap-3 pb-4 border-b border-gray-100">
            <div className="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center">
              <Activity className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900">Daily Report — {format(new Date(report.date || Date.now()), "PPP")}</h3>
              <p className="text-xs text-gray-400">{report.summary || "No activity in the last 24 hours."}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-4">
            <div>
              <p className="text-xs text-gray-500 uppercase">Messages Handled</p>
              <p className="text-2xl font-bold text-gray-900">{report.messages_handled ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">AI Replies</p>
              <p className="text-2xl font-bold text-gray-900">{report.ai_replies ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Tasks Completed</p>
              <p className="text-2xl font-bold text-gray-900">{report.tasks_completed ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Meetings Detected</p>
              <p className="text-2xl font-bold text-gray-900">{report.meetings_detected ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Reminders Created</p>
              <p className="text-2xl font-bold text-gray-900">{report.reminders_created ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Time Saved (min)</p>
              <p className="text-2xl font-bold text-gray-900">{report.time_saved_minutes ?? 0}</p>
            </div>
          </div>
        </Card>
      ) : (
        <Card className="text-center py-12 text-gray-400">
          Tap "Generate Now" to build today's report.
        </Card>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Settings Page
// ────────────────────────────────────────────────────────────────
function SettingsPage({ user, onUserChange }: { user: User; onUserChange: (u: User) => void }) {
  const [autoReply, setAutoReply] = useState(true);
  const [filterOtp, setFilterOtp] = useState(true);
  const [filterSpam, setFilterSpam] = useState(true);
  const [filterBank, setFilterBank] = useState(true);
  const [filterPromo, setFilterPromo] = useState(true);
  const [language, setLanguage] = useState("en");
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [workingHours, setWorkingHours] = useState({ start: "09:00", end: "18:00" });
  const [reportTime, setReportTime] = useState("20:00");
  const [deliveryMethod, setDeliveryMethod] = useState<"dashboard" | "email" | "whatsapp" | "notification">("dashboard");
  const [notif, setNotif] = useState({ email: true, whatsapp: true, push: true });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Load settings on mount
  useEffect(() => {
    apiFetch("/settings/me").then((s: any) => {
      if (s) {
        setAutoReply(!!s.auto_reply_enabled);
        setFilterOtp(!!s.filter_otp);
        setFilterSpam(!!s.filter_spam);
        setFilterBank(!!s.filter_bank);
        setFilterPromo(!!s.filter_promo);
        setLanguage(s.language || "en");
        setTimezone(s.timezone || timezone);
        setReportTime(s.report_time || "20:00");
        setDeliveryMethod(s.report_delivery || "dashboard");
      }
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await apiFetch("/settings/me", {
        method: "PATCH",
        body: JSON.stringify({
          auto_reply_enabled: autoReply,
          filter_otp: filterOtp,
          filter_spam: filterSpam,
          filter_bank: filterBank,
          filter_promo: filterPromo,
          language,
          timezone,
          working_hours: workingHours,
          report_time: reportTime,
          report_delivery: deliveryMethod,
          notifications: notif,
        }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {}
    finally { setSaving(false); }
  };

  const exportData = async () => {
    try {
      const data = await apiFetch("/settings/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "ai-assistant-export.json";
      a.click();
    } catch {}
  };

  const deleteAccount = async () => {
    if (!confirm("This will permanently delete your account and all data. Continue?")) return;
    try {
      await apiFetch("/auth/me", { method: "DELETE", body: JSON.stringify({ confirm: true }) });
      clearTokens();
      window.location.hash = "#/login";
      window.location.reload();
    } catch {}
  };

  return (
    <div>
      <div className="mb-6 md:mb-8">
        <h2 className="text-2xl md:text-3xl font-bold text-gray-900">Settings</h2>
        <p className="text-gray-500 mt-1">Customize your AI assistant</p>
      </div>

      <div className="space-y-4 max-w-3xl">
        {/* AI Behavior */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Brain className="w-5 h-5 text-green-600" /> AI Behavior
          </h3>
          <SettingRow label="Auto reply" sub="Let the AI reply automatically">
            <Toggle checked={autoReply} onChange={setAutoReply} />
          </SettingRow>
          <SettingRow label="Reply delay (sec)" sub="Human-like pause">
            <input type="number" defaultValue={5}
              className="w-20 px-3 py-1.5 rounded-lg border border-gray-200 outline-none text-center" />
          </SettingRow>
          <SettingRow label="Language" sub="Detected automatically">
            <select value={language} onChange={e => setLanguage(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-gray-200 outline-none bg-white">
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
              <option value="hi">Hindi</option>
              <option value="pt">Portuguese</option>
              <option value="auto">Auto-detect</option>
            </select>
          </SettingRow>
          <SettingRow label="Timezone" sub="Used for working hours">
            <input value={timezone} onChange={e => setTimezone(e.target.value)}
              className="w-40 px-3 py-1.5 rounded-lg border border-gray-200 outline-none" />
          </SettingRow>
        </Card>

        {/* Smart Filters */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-green-600" /> Smart Filters
          </h3>
          <SettingRow label="Block OTP messages"><Toggle checked={filterOtp} onChange={setFilterOtp} /></SettingRow>
          <SettingRow label="Block bank notifications"><Toggle checked={filterBank} onChange={setFilterBank} /></SettingRow>
          <SettingRow label="Block spam"><Toggle checked={filterSpam} onChange={setFilterSpam} /></SettingRow>
          <SettingRow label="Block promotions"><Toggle checked={filterPromo} onChange={setFilterPromo} /></SettingRow>
        </Card>

        {/* Working hours */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-green-600" /> Working Hours
          </h3>
          <p className="text-sm text-gray-500 mb-4">Outside these hours, replies are queued or muted.</p>
          <div className="flex gap-3">
            <Input type="time" value={workingHours.start}
              onChange={e => setWorkingHours(h => ({ ...h, start: e.target.value }))} />
            <Input type="time" value={workingHours.end}
              onChange={e => setWorkingHours(h => ({ ...h, end: e.target.value }))} />
          </div>
        </Card>

        {/* Reports */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-green-600" /> Daily Reports
          </h3>
          <SettingRow label="Report time" sub="When to generate">
            <input type="time" value={reportTime} onChange={e => setReportTime(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-gray-200 outline-none" />
          </SettingRow>
          <SettingRow label="Delivery">
            <select value={deliveryMethod} onChange={e => setDeliveryMethod(e.target.value as any)}
              className="px-3 py-1.5 rounded-lg border border-gray-200 outline-none bg-white">
              <option value="dashboard">Dashboard</option>
              <option value="email">Email</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="notification">Push notification</option>
            </select>
          </SettingRow>
        </Card>

        {/* Notifications */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Bell className="w-5 h-5 text-green-600" /> Notifications
          </h3>
          <SettingRow label="Email notifications">
            <Toggle checked={notif.email} onChange={v => setNotif(n => ({ ...n, email: v }))} />
          </SettingRow>
          <SettingRow label="WhatsApp notifications">
            <Toggle checked={notif.whatsapp} onChange={v => setNotif(n => ({ ...n, whatsapp: v }))} />
          </SettingRow>
          <SettingRow label="Push notifications">
            <Toggle checked={notif.push} onChange={v => setNotif(n => ({ ...n, push: v }))} />
          </SettingRow>
        </Card>

        {/* Account */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Lock className="w-5 h-5 text-green-600" /> Account
          </h3>
          <SettingRow label="Email">{user.email}</SettingRow>
          <SettingRow label="Email verified">
            {user.email_verified
              ? <span className="text-green-600 inline-flex items-center gap-1"><CheckCircle className="w-4 h-4" /> Verified</span>
              : <span className="text-yellow-600">Not verified</span>}
          </SettingRow>
          <SettingRow label="Member since">{format(new Date(user.created_at), "PPP")}</SettingRow>
        </Card>

        {/* Data */}
        <Card>
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Database className="w-5 h-5 text-green-600" /> Data
          </h3>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={exportData}>
              <Download className="w-4 h-4 inline mr-2" /> Export Data
            </Button>
            <Button variant="danger" onClick={deleteAccount}>
              <Trash className="w-4 h-4 inline mr-2" /> Delete Account
            </Button>
          </div>
        </Card>

        <div className="flex gap-3 sticky bottom-0 bg-gray-50 py-3 -mx-4 px-4 md:static md:bg-transparent md:p-0">
          <Button onClick={save} disabled={saving} className="flex-1 md:flex-initial">
            {saving ? "Saving…" : saved ? "✓ Saved" : "Save Changes"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function SettingRow({ label, sub, children }: { label: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3 border-b border-gray-50 last:border-0">
      <div>
        <p className="text-sm font-medium text-gray-800">{label}</p>
        {sub && <p className="text-xs text-gray-400">{sub}</p>}
      </div>
      <div>{children}</div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Root App
// ────────────────────────────────────────────────────────────────
type Page = "dashboard" | "ai" | "whatsapp" | "contacts" | "messages" | "reports" | "settings";

export default function App() {
  const [authed, setAuthed] = useState(!!getTokens());
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState<Page>("dashboard");
  const [aiState, setAiState] = useState({ enabled: true, paused: false, emergency: false });
  const routerRef = useRef<HTMLDivElement>(null);

  const refreshUser = useCallback(async () => {
    try {
      const u = await apiFetch("/auth/me");
      setUser(u);
      setAiState(s => ({
        enabled: u.is_ai_enabled,
        paused: s.paused,
        emergency: u.ai_emergency_stop,
      }));
    } catch { clearTokens(); setAuthed(false); }
  }, []);

  useEffect(() => {
    if (authed) refreshUser();
  }, [authed, refreshUser]);

  // Hash-based routing
  useEffect(() => {
    const handle = () => {
      const hash = window.location.hash.replace("#/", "");
      if (["dashboard", "ai", "whatsapp", "contacts", "messages", "reports", "settings"].includes(hash)) {
        setPage(hash as Page);
      }
    };
    window.addEventListener("hashchange", handle);
    handle();
    return () => window.removeEventListener("hashchange", handle);
  }, []);

  const navigate = (p: Page) => {
    setPage(p);
    window.location.hash = `#/${p}`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const logout = async () => {
    try { await apiFetch("/auth/logout", { method: "POST" }); } catch {}
    clearTokens();
    setAuthed(false);
    window.location.hash = "";
  };

  const setAISettings = async (s: { enabled: boolean; paused: boolean }) => {
    if (!user) return;
    setAiState(prev => ({ ...prev, ...s }));
    try {
      await apiFetch("/auth/me", {
        method: "PATCH",
        body: JSON.stringify({ is_ai_enabled: s.enabled }),
      });
    } catch {}
  };

  const setEmergency = async (enabled: boolean) => {
    try {
      await apiFetch("/auth/ai/emergency-stop", {
        method: "POST",
        body: JSON.stringify({ enabled }),
      });
      await refreshUser();
    } catch {}
  };

  if (!authed) return <AuthPage onAuth={() => setAuthed(true)} />;
  if (!user) return <div className="min-h-screen flex items-center justify-center"><Spinner className="w-10 h-10" /></div>;

  return (
    <Layout
      page={page}
      onNavigate={navigate}
      onLogout={logout}
      user={user}
      aiState={aiState}
    >
      {page === "dashboard" && <DashboardPage />}
      {page === "ai" && (
        <AIPage
          aiState={aiState}
          aiEnabled={user.is_ai_enabled}
          onChange={setAISettings}
          onEmergency={setEmergency}
        />
      )}
      {page === "whatsapp" && <WhatsAppPage />}
      {page === "contacts" && <ContactsPage />}
      {page === "messages" && <MessagesPage />}
      {page === "reports" && <ReportsPage />}
      {page === "settings" && <SettingsPage user={user} onUserChange={setUser} />}
    </Layout>
  );
}
