import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, ApiError } from "../api/client";

type Mode = "login" | "register";

function RelayMark() {
  return (
    <svg
      width="26"
      height="26"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect x="0" y="0" width="4" height="4" fill="#1C7C55" />
      <rect x="5" y="0" width="4" height="4" fill="#1C7C55" opacity="0.4" />
      <rect x="0" y="5" width="4" height="4" fill="#1C7C55" opacity="0.4" />
      <rect x="5" y="5" width="4" height="4" fill="#1C7C55" />
      <rect x="10" y="0" width="4" height="4" fill="#35C67C" opacity="0.5" />
      <rect x="10" y="5" width="4" height="4" fill="#1C7C55" opacity="0.4" />
      <rect x="0" y="10" width="4" height="4" fill="#1C7C55" opacity="0.15" />
      <rect x="5" y="10" width="4" height="4" fill="#1C7C55" opacity="0.4" />
      <rect x="10" y="10" width="4" height="4" fill="#35C67C" opacity="0.5" />
    </svg>
  );
}

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      if (mode === "register") {
        await api.register(email, password);
        setSuccess("Account created — logging you in…");
        const data = await api.login(email, password);
        login(data.access_token);
        navigate("/", { replace: true });
      } else {
        const data = await api.login(email, password);
        login(data.access_token);
        navigate("/", { replace: true });
      }
    } catch (err) {
      if (err instanceof ApiError) {
        try {
          const parsed = JSON.parse(err.message);
          setError(parsed.detail ?? err.message);
        } catch {
          setError(err.message);
        }
      } else {
        setError("Something went wrong. Is the gateway running on port 8001?");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-paper px-4">
      {/* Soft grey-green corner washes */}
      <div
        className="pointer-events-none absolute -right-32 -top-32 h-[420px] w-[420px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(53,198,124,0.14) 0%, transparent 70%)",
        }}
      />
      <div
        className="pointer-events-none absolute -bottom-40 -left-32 h-[420px] w-[420px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(28,124,85,0.10) 0%, transparent 70%)",
        }}
      />

      {/* Card */}
      <div className="relative z-10 w-full max-w-sm rounded-xl border border-line bg-surface p-8 shadow-sm">
        <div className="mb-8 flex items-center gap-2.5">
          <RelayMark />
          <span className="text-xl font-bold tracking-tight text-ink">Relay</span>
        </div>

        <h1 className="text-xl font-semibold tracking-tight text-ink">
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-1 text-sm text-muted">LLM reverse proxy</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 w-full rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-muted/50 outline-none transition-colors focus:border-green/50 focus:ring-1 focus:ring-green/30"
              placeholder="you@example.com"
              autoComplete="username"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-muted">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 w-full rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-muted/50 outline-none transition-colors focus:border-green/50 focus:ring-1 focus:ring-green/30"
              placeholder="••••••••"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </div>

          {error && (
            <p className="rounded-md border border-danger/20 bg-danger/10 px-3 py-2 text-xs text-danger">
              {error}
            </p>
          )}
          {success && (
            <p className="rounded-md border border-green/20 bg-green-soft px-3 py-2 text-xs text-green">
              {success}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-green px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading
              ? "Please wait…"
              : mode === "login"
              ? "Sign in"
              : "Create account"}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-muted">
          {mode === "login" ? (
            <>
              Don't have an account?{" "}
              <button
                onClick={() => { setMode("register"); setError(null); }}
                className="font-medium text-green transition-opacity hover:opacity-80"
              >
                Register
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                onClick={() => { setMode("login"); setError(null); }}
                className="font-medium text-green transition-opacity hover:opacity-80"
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
