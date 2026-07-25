import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const LINKS = [
  { to: "/", label: "Overview" },
  { to: "/routing", label: "Intelligence" },
  { to: "/guardrails", label: "Guardrails" },
  { to: "/evals", label: "Evals" },
  { to: "/chat", label: "Chat" },
  { to: "/documents", label: "Documents" },
  { to: "/keys", label: "API Keys" },
];

function RelayMark() {
  return (
    <svg
      width="22"
      height="22"
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

export function Nav() {
  const { logout } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2.5">
            <RelayMark />
            <span className="text-lg font-bold tracking-tight text-ink">
              Relay
            </span>
          </div>

          <nav className="hidden items-center gap-1 md:flex">
            {LINKS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `relative px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
                    isActive ? "text-green" : "text-muted hover:text-ink"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {label}
                    {isActive && (
                      <span className="nav-active-line absolute -bottom-[22px] left-3 right-3 h-0.5 bg-green" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <button
          onClick={logout}
          className="text-sm font-medium text-muted transition-colors hover:text-ink"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
