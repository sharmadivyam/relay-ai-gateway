import { useState } from "react";
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

function MenuIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

export function Nav() {
  const { logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40">
      <div className="border-b border-line bg-paper/90 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setIsOpen(true)}
              className="-ml-1.5 mr-0.5 rounded-md p-1.5 text-ink transition-colors hover:bg-ink/5 md:hidden"
              aria-label="Open menu"
              aria-expanded={isOpen}
            >
              <MenuIcon />
            </button>
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
          className="hidden text-sm font-medium text-muted transition-colors hover:text-ink md:block"
        >
          Sign out
        </button>
      </div>
      </div>

      {/* Mobile sidebar overlay */}
      <div
        className={`fixed inset-0 z-50 md:hidden ${
          isOpen ? "pointer-events-auto" : "pointer-events-none"
        }`}
        aria-hidden={!isOpen}
      >
        {/* Backdrop */}
        <div
          onClick={() => setIsOpen(false)}
          className={`absolute inset-0 bg-ink/30 transition-opacity duration-200 ${
            isOpen ? "opacity-100" : "opacity-0"
          }`}
        />

        {/* Sliding panel */}
        <div
          className={`absolute inset-y-0 left-0 flex h-full w-72 max-w-[80vw] flex-col bg-paper shadow-xl transition-transform duration-200 ease-out ${
            isOpen ? "translate-x-0" : "-translate-x-full"
          }`}
          role="dialog"
          aria-modal="true"
        >
          <div className="flex h-16 items-center justify-between border-b border-line px-5">
            <div className="flex items-center gap-2.5">
              <RelayMark />
              <span className="text-lg font-bold tracking-tight text-ink">
                Relay
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded-md p-1.5 text-ink transition-colors hover:bg-ink/5"
              aria-label="Close menu"
            >
              <CloseIcon />
            </button>
          </div>

          <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-4">
            {LINKS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                onClick={() => setIsOpen(false)}
                className={({ isActive }) =>
                  `rounded-md px-3 py-2.5 text-sm font-medium transition-colors duration-150 ${
                    isActive
                      ? "bg-green/10 text-green"
                      : "text-muted hover:bg-ink/5 hover:text-ink"
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="border-t border-line px-3 py-4">
            <button
              onClick={() => {
                setIsOpen(false);
                logout();
              }}
              className="w-full rounded-md px-3 py-2.5 text-left text-sm font-medium text-muted transition-colors hover:bg-ink/5 hover:text-ink"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}