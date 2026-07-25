import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Nav } from "./components/Nav";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { Routing } from "./pages/Routing";
import { Guardrails } from "./pages/Guardrails";
import { Documents } from "./pages/Documents";
import { Chat } from "./pages/Chat";
import { Keys } from "./pages/Keys";
import { Evals } from "./pages/Evals";

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return (
    <div className="min-h-screen bg-paper">
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  );
}

function AppRoutes() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
      />
      <Route
        path="/"
        element={
          <ProtectedLayout>
            <Overview />
          </ProtectedLayout>
        }
      />
      <Route
        path="/routing"
        element={
          <ProtectedLayout>
            <Routing />
          </ProtectedLayout>
        }
      />
      <Route
        path="/guardrails"
        element={
          <ProtectedLayout>
            <Guardrails />
          </ProtectedLayout>
        }
      />
      <Route
        path="/documents"
        element={
          <ProtectedLayout>
            <Documents />
          </ProtectedLayout>
        }
      />
      <Route
        path="/chat"
        element={
          <ProtectedLayout>
            <Chat />
          </ProtectedLayout>
        }
      />
      <Route
        path="/keys"
        element={
          <ProtectedLayout>
            <Keys />
          </ProtectedLayout>
        }
      />
      <Route
        path="/evals"
        element={
          <ProtectedLayout>
            <Evals />
          </ProtectedLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
