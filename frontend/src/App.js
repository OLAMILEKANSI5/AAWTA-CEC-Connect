import React, { useEffect, useRef, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation, useNavigate, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth, api } from "@/auth";
import { PortalLayout } from "@/components/PortalLayout";

// Public pages
import Home from "@/pages/public/Home";
import About from "@/pages/public/About";
import AmbassadorProgram from "@/pages/public/AmbassadorProgram";
import Volunteer from "@/pages/public/Volunteer";
import Programs from "@/pages/public/Programs";
import ResourcesPublic from "@/pages/public/ResourcesPublic";
import FAQ from "@/pages/public/FAQ";
import Contact from "@/pages/public/Contact";
import Directory from "@/pages/public/Directory";
import Apply from "@/pages/public/Apply";
import Login from "@/pages/public/Login";

// Portal pages
import Dashboard from "@/pages/portal/Dashboard";
import Applications from "@/pages/portal/Applications";
import ApplicationDetail from "@/pages/portal/ApplicationDetail";
import Members from "@/pages/portal/Members";
import MemberDetail from "@/pages/portal/MemberDetail";
import MyProfile from "@/pages/portal/MyProfile";
import Onboarding from "@/pages/portal/Onboarding";
import Documents from "@/pages/portal/Documents";
import Messages from "@/pages/portal/Messages";
import Announcements from "@/pages/portal/Announcements";
import Events from "@/pages/portal/Events";
import Goals from "@/pages/portal/Goals";
import ResourceCenter from "@/pages/portal/ResourceCenter";
import Reports from "@/pages/portal/Reports";
import AuditLog from "@/pages/portal/AuditLog";
import Users from "@/pages/portal/Users";
import Settings from "@/pages/portal/Settings";

const AuthCallback = () => {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const hash = window.location.hash;
    const sid = new URLSearchParams(hash.replace("#", "")).get("session_id");
    if (!sid) { navigate("/login"); return; }
    api.post("/auth/session", {}, { headers: { "X-Session-ID": sid } })
      .then((r) => { localStorage.setItem("cec_has_session", "1"); setUser(r.data); window.history.replaceState(null, "", "/portal"); navigate("/portal", { state: { user: r.data } }); })
      .catch((e) => {
        const msg = e?.response?.data?.detail || "Authentication failed";
        navigate("/login", { state: { error: msg } });
      });
  }, [navigate, setUser]);
  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-navy-dark text-white">
      <div className="text-center">
        <div className="h-10 w-10 border-3 border-brand-magenta border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="font-head">Signing you in…</p>
      </div>
    </div>
  );
};

const STAFF = ["super_admin", "director", "administrator"];

const ProtectedRoute = ({ children, roles }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="h-10 w-10 border-3 border-brand-magenta border-t-transparent rounded-full animate-spin" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <PortalLayout><div className="text-center py-24"><p className="font-head text-2xl font-bold text-brand-navy">Not authorized</p><p className="text-slate-500 mt-2">You don't have access to this section.</p></div></PortalLayout>;
  return <PortalLayout>{children}</PortalLayout>;
};

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/about" element={<About />} />
      <Route path="/ambassadors" element={<AmbassadorProgram />} />
      <Route path="/volunteer" element={<Volunteer />} />
      <Route path="/programs" element={<Programs />} />
      <Route path="/resources" element={<ResourcesPublic />} />
      <Route path="/faq" element={<FAQ />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/directory" element={<Directory />} />
      <Route path="/apply" element={<Apply />} />
      <Route path="/login" element={<Login />} />

      <Route path="/portal" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/portal/applications" element={<ProtectedRoute roles={STAFF}><Applications /></ProtectedRoute>} />
      <Route path="/portal/applications/:id" element={<ProtectedRoute roles={STAFF}><ApplicationDetail /></ProtectedRoute>} />
      <Route path="/portal/members" element={<ProtectedRoute roles={STAFF}><Members /></ProtectedRoute>} />
      <Route path="/portal/members/:id" element={<ProtectedRoute roles={STAFF}><MemberDetail /></ProtectedRoute>} />
      <Route path="/portal/profile" element={<ProtectedRoute roles={["ambassador", "volunteer"]}><MyProfile /></ProtectedRoute>} />
      <Route path="/portal/onboarding" element={<ProtectedRoute roles={["ambassador", "volunteer"]}><Onboarding /></ProtectedRoute>} />
      <Route path="/portal/documents" element={<ProtectedRoute><Documents /></ProtectedRoute>} />
      <Route path="/portal/messages" element={<ProtectedRoute><Messages /></ProtectedRoute>} />
      <Route path="/portal/announcements" element={<ProtectedRoute><Announcements /></ProtectedRoute>} />
      <Route path="/portal/events" element={<ProtectedRoute><Events /></ProtectedRoute>} />
      <Route path="/portal/goals" element={<ProtectedRoute><Goals /></ProtectedRoute>} />
      <Route path="/portal/resources" element={<ProtectedRoute><ResourceCenter /></ProtectedRoute>} />
      <Route path="/portal/reports" element={<ProtectedRoute roles={STAFF}><Reports /></ProtectedRoute>} />
      <Route path="/portal/audit" element={<ProtectedRoute roles={["super_admin", "director"]}><AuditLog /></ProtectedRoute>} />
      <Route path="/portal/users" element={<ProtectedRoute roles={["super_admin", "director"]}><Users /></ProtectedRoute>} />
      <Route path="/portal/settings" element={<ProtectedRoute roles={STAFF}><Settings /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <AppRouter />
          <Toaster position="top-right" richColors />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
