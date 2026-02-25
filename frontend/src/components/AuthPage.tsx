"use client";
import { useState } from "react";
import { useI18n } from "@/i18n/context";
import { useAuth } from "@/contexts/AuthContext";
import { Shield, Eye, EyeOff, Loader2, Lock, Mail, User } from "lucide-react";

export default function AuthPage() {
  const { locale } = useI18n();
  const isHe = locale === "he";
  const { login, login2FA, register } = useAuth();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // 2FA state
  const [needs2FA, setNeeds2FA] = useState(false);
  const [totpCode, setTotpCode] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (needs2FA) {
        await login2FA(email, password, totpCode);
        return;
      }

      if (mode === "login") {
        const result = await login(email, password);
        if (result.requires_2fa) {
          setNeeds2FA(true);
          return;
        }
      } else {
        await register(email, password, displayName);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="text-center">
          <div className="inline-flex items-center gap-2 mb-2">
            <Shield className="w-8 h-8 text-cyan-400" />
            <h1 className="text-2xl font-bold text-white">TrendVest</h1>
          </div>
          <p className="text-sm text-[#64748b]">
            {isHe ? "פלטפורמה חכמה לניתוח שוק ההון" : "Smart Market Analysis Platform"}
          </p>
        </div>

        {/* Card */}
        <div className="bg-[#111827] rounded-2xl border border-[#334155] p-6 space-y-5">
          <h2 className="text-lg font-bold text-white text-center">
            {needs2FA
              ? (isHe ? "אימות דו-שלבי" : "Two-Factor Authentication")
              : mode === "login"
              ? (isHe ? "התחברות" : "Sign In")
              : (isHe ? "הרשמה" : "Create Account")
            }
          </h2>

          {error && (
            <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs text-center">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            {needs2FA ? (
              <>
                <p className="text-xs text-[#94a3b8] text-center">
                  {isHe
                    ? "הזן את הקוד מאפליקציית האימות שלך"
                    : "Enter the code from your authenticator app"
                  }
                </p>
                <div className="relative">
                  <Lock className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#475569]" />
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                    placeholder="000000"
                    className="w-full ps-10 pe-4 py-2.5 rounded-xl bg-[#0f172a] border border-[#334155] text-white text-center text-lg tracking-[0.5em] font-mono placeholder:text-[#334155] focus:outline-none focus:border-cyan-500/50"
                    autoFocus
                  />
                </div>
                <button
                  type="button"
                  onClick={() => { setNeeds2FA(false); setTotpCode(""); }}
                  className="w-full text-xs text-[#64748b] hover:text-white transition"
                >
                  {isHe ? "חזור" : "Back to login"}
                </button>
              </>
            ) : (
              <>
                {mode === "register" && (
                  <div className="relative">
                    <User className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#475569]" />
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder={isHe ? "שם תצוגה" : "Display Name"}
                      className="w-full ps-10 pe-4 py-2.5 rounded-xl bg-[#0f172a] border border-[#334155] text-white placeholder:text-[#475569] text-sm focus:outline-none focus:border-cyan-500/50"
                    />
                  </div>
                )}

                <div className="relative">
                  <Mail className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#475569]" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={isHe ? "אימייל" : "Email"}
                    required
                    className="w-full ps-10 pe-4 py-2.5 rounded-xl bg-[#0f172a] border border-[#334155] text-white placeholder:text-[#475569] text-sm focus:outline-none focus:border-cyan-500/50"
                  />
                </div>

                <div className="relative">
                  <Lock className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#475569]" />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={isHe ? "סיסמה" : "Password"}
                    required
                    minLength={8}
                    className="w-full ps-10 pe-10 py-2.5 rounded-xl bg-[#0f172a] border border-[#334155] text-white placeholder:text-[#475569] text-sm focus:outline-none focus:border-cyan-500/50"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute end-3 top-1/2 -translate-y-1/2 text-[#475569] hover:text-white transition"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white font-medium text-sm hover:opacity-90 transition disabled:opacity-40 flex items-center justify-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {needs2FA
                ? (isHe ? "אמת" : "Verify")
                : mode === "login"
                ? (isHe ? "התחבר" : "Sign In")
                : (isHe ? "צור חשבון" : "Create Account")
              }
            </button>
          </form>

          {!needs2FA && (
            <div className="text-center">
              <button
                onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
                className="text-xs text-[#64748b] hover:text-cyan-400 transition"
              >
                {mode === "login"
                  ? (isHe ? "אין לך חשבון? הירשם" : "Don't have an account? Sign up")
                  : (isHe ? "יש לך חשבון? התחבר" : "Already have an account? Sign in")
                }
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
