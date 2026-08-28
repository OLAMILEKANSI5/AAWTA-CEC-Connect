import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, FileText, Users, UserCircle, ClipboardCheck, FileSignature,
  MessageSquare, Megaphone, Calendar, Target, BookOpen, BarChart3, ScrollText,
  Settings as SettingsIcon, ShieldCheck, LogOut, Bell, Menu, X,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { useAuth, api } from "@/auth";
import { ROLE_LABELS } from "@/lib/constants";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

const STAFF = ["super_admin", "director", "administrator"];

const NAV_ITEMS = [
  { to: "/portal", label: "Dashboard", icon: LayoutDashboard, roles: "all" },
  { to: "/portal/applications", label: "Applications", icon: FileText, roles: STAFF },
  { to: "/portal/members", label: "Members", icon: Users, roles: STAFF },
  { to: "/portal/profile", label: "My Profile", icon: UserCircle, roles: ["ambassador", "volunteer"] },
  { to: "/portal/onboarding", label: "Onboarding", icon: ClipboardCheck, roles: ["ambassador", "volunteer"] },
  { to: "/portal/documents", label: "Documents", icon: FileSignature, roles: "all" },
  { to: "/portal/messages", label: "Messages", icon: MessageSquare, roles: "all" },
  { to: "/portal/announcements", label: "Announcements", icon: Megaphone, roles: "all" },
  { to: "/portal/events", label: "Events & Calendar", icon: Calendar, roles: "all" },
  { to: "/portal/goals", label: "Goals & Activity", icon: Target, roles: "all" },
  { to: "/portal/resources", label: "Resource Center", icon: BookOpen, roles: "all" },
  { to: "/portal/reports", label: "Reports", icon: BarChart3, roles: STAFF },
  { to: "/portal/audit", label: "Audit Log", icon: ScrollText, roles: ["super_admin", "director"] },
  { to: "/portal/users", label: "User Management", icon: ShieldCheck, roles: ["super_admin", "director"] },
  { to: "/portal/settings", label: "Settings", icon: SettingsIcon, roles: STAFF },
];

export const PortalLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notifs, setNotifs] = useState([]);
  const [showNotifs, setShowNotifs] = useState(false);

  const loadNotifs = () => api.get("/notifications").then((r) => setNotifs(r.data)).catch(() => {});
  useEffect(() => { loadNotifs(); const i = setInterval(loadNotifs, 30000); return () => clearInterval(i); }, []);
  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);

  const canSee = (roles) => roles === "all" || roles.includes(user?.role);
  const items = NAV_ITEMS.filter((i) => canSee(i.roles));
  const unread = notifs.filter((n) => !n.read).length;

  const markAll = async () => { await api.post("/notifications/read-all"); loadNotifs(); };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      {/* Sidebar */}
      <aside className={`fixed lg:sticky top-0 z-40 h-screen w-64 bg-brand-navy-dark text-white flex flex-col transition-transform ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}>
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <Link to="/portal"><Logo dark className="h-9 w-9" /></Link>
          <button className="lg:hidden" onClick={() => setSidebarOpen(false)}><X size={18} /></button>
        </div>
        <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
          {items.map((i) => {
            const active = location.pathname === i.to;
            const Icon = i.icon;
            return (
              <Link key={i.to} to={i.to} data-testid={`sidebar-${i.label.toLowerCase().replace(/[^a-z]/g, "-")}`}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${active ? "bg-brand-magenta text-white" : "text-white/70 hover:bg-white/10 hover:text-white"}`}>
                <Icon size={18} /> {i.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-white/10">
          <button onClick={logout} data-testid="logout-btn" className="flex items-center gap-3 px-3 py-2.5 w-full rounded-lg text-sm font-medium text-white/70 hover:bg-white/10 hover:text-white transition-colors">
            <LogOut size={18} /> Sign out
          </button>
        </div>
      </aside>

      {sidebarOpen && <div className="fixed inset-0 bg-black/40 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} />}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-20 bg-white border-b border-slate-200 h-16 flex items-center justify-between px-4 gap-4">
          <button className="lg:hidden" onClick={() => setSidebarOpen(true)} data-testid="portal-menu-toggle"><Menu /></button>
          <div className="font-head font-semibold text-brand-navy hidden sm:block">
            {NAV_ITEMS.find((i) => i.to === location.pathname)?.label || "CEC Connect Portal"}
          </div>
          <div className="flex items-center gap-3 ml-auto">
            <div className="relative">
              <button onClick={() => setShowNotifs(!showNotifs)} data-testid="notifications-btn" className="relative p-2 rounded-full hover:bg-slate-100">
                <Bell size={20} className="text-slate-600" />
                {unread > 0 && <span className="absolute top-1 right-1 h-4 min-w-4 px-1 rounded-full bg-brand-magenta text-white text-[10px] flex items-center justify-center">{unread}</span>}
              </button>
              {showNotifs && (
                <div className="absolute right-0 mt-2 w-80 bg-white border border-slate-200 rounded-xl shadow-xl z-50 max-h-96 overflow-y-auto" data-testid="notifications-panel">
                  <div className="flex items-center justify-between p-3 border-b">
                    <span className="font-semibold text-sm">Notifications</span>
                    <button onClick={markAll} className="text-xs text-brand-magenta hover:underline">Mark all read</button>
                  </div>
                  {notifs.length === 0 ? <p className="p-4 text-sm text-slate-500">No notifications</p> :
                    notifs.slice(0, 20).map((n) => (
                      <div key={n.id} onClick={() => { if (n.link) navigate(n.link); setShowNotifs(false); }}
                        className={`p-3 border-b cursor-pointer hover:bg-slate-50 ${!n.read ? "bg-brand-magenta/5" : ""}`}>
                        <p className="text-sm font-medium text-slate-800">{n.title}</p>
                        <p className="text-xs text-slate-500 line-clamp-2">{n.body}</p>
                      </div>
                    ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Avatar className="h-8 w-8"><AvatarImage src={user?.picture} /><AvatarFallback className="bg-brand-navy text-white text-xs">{user?.name?.[0]}</AvatarFallback></Avatar>
              <div className="hidden sm:block leading-tight">
                <div className="text-sm font-medium text-slate-800">{user?.name}</div>
                <Badge variant="secondary" className="text-[10px] h-4 px-1.5 bg-brand-magenta/10 text-brand-magenta">{ROLE_LABELS[user?.role]}</Badge>
              </div>
            </div>
          </div>
        </header>
        <div className="flex-1 p-4 sm:p-6 max-w-[1400px] w-full mx-auto">{children}</div>
      </div>
    </div>
  );
};
