import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <main className="foundation-page"><p>Checking your session...</p></main>;
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
