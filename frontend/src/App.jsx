import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { useAuth } from "./context/AuthContext";
import LandingPage from "./pages/public/LandingPage";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import NotFoundPage from "./pages/public/NotFoundPage";
import ProtectedRoute from "./routes/ProtectedRoute";

const WorkspacePage = lazy(() => import("./pages/dashboard/WorkspacePage"));

function ProtectedWorkspace() {
  return (
    <Suspense fallback={<main className="page-loading" role="status">Loading your workspace...</main>}>
      <WorkspacePage />
    </Suspense>
  );
}

function LegacyRoute() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <ProtectedWorkspace /> : <LandingPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LegacyRoute />} />
      <Route path="/features" element={<LandingPage />} />
      <Route path="/how-it-works" element={<LandingPage />} />
      <Route path="/about" element={<LandingPage />} />
      <Route path="/faq" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<ProtectedWorkspace />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
