import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Menu, X, Phone, MapPin, Globe } from "lucide-react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { api } from "@/auth";

const NAV = [
  { to: "/", label: "Home" },
  { to: "/about", label: "About the CEC" },
  { to: "/ambassadors", label: "Ambassador Program" },
  { to: "/volunteer", label: "Volunteer" },
  { to: "/programs", label: "Programs & Impact" },
  { to: "/directory", label: "Directory" },
  { to: "/gallery", label: "Gallery" },
  { to: "/events", label: "Events" },
  { to: "/resources", label: "Resources" },
  { to: "/faq", label: "FAQ" },
  { to: "/contact", label: "Contact" },
];

export const PublicLayout = ({ children }) => {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState({});
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => { api.get("/settings").then((r) => setSettings(r.data)).catch(() => {}); }, []);
  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [location.pathname]);

  return (
    <div className="min-h-screen bg-[#FDFBF7] flex flex-col">
      {/* Top contact bar */}
      <div className="bg-brand-navy text-white text-xs" data-testid="top-contact-bar">
        <div className="max-w-7xl mx-auto px-4 py-2 flex flex-wrap items-center justify-center md:justify-between gap-x-6 gap-y-1">
          <span className="flex items-center gap-1.5"><MapPin size={13} className="text-brand-pink" /> {settings.address || "5269 Buford Highway Suite 213, Doraville GA 30340"}</span>
          <div className="flex items-center gap-6">
            <a href={`tel:${(settings.phone || "").replace(/\s/g, "")}`} className="flex items-center gap-1.5 hover:text-brand-pink transition-colors"><Phone size={13} /> {settings.phone || "770 756 6768"}</a>
            <a href={settings.website || "https://www.aawta.org"} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 hover:text-brand-pink transition-colors"><Globe size={13} /> www.aawta.org</a>
          </div>
        </div>
      </div>

      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-white/85 border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <Link to="/" data-testid="header-logo-link"><Logo /></Link>
          <nav className="hidden xl:flex items-center gap-1">
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} data-testid={`nav-${n.label.toLowerCase().replace(/[^a-z]/g, "-")}`}
                className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${location.pathname === n.to ? "text-brand-magenta" : "text-slate-600 hover:text-brand-navy hover:bg-slate-50"}`}>
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="hidden md:flex items-center gap-2">
            <Button variant="outline" data-testid="member-login-btn" onClick={() => navigate("/login")}
              className="rounded-full border-brand-navy text-brand-navy hover:bg-brand-navy hover:text-white">Member Login</Button>
            <Button data-testid="apply-now-btn" onClick={() => navigate("/apply")}
              className="rounded-full bg-brand-magenta hover:bg-brand-pink text-white">Apply Now</Button>
          </div>
          <button className="xl:hidden p-2" onClick={() => setOpen(!open)} data-testid="mobile-menu-toggle">
            {open ? <X /> : <Menu />}
          </button>
        </div>
        {open && (
          <div className="xl:hidden border-t border-slate-200 bg-white px-4 py-3 space-y-1" data-testid="mobile-menu">
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} className="block px-3 py-2 rounded-md text-slate-700 hover:bg-slate-50">{n.label}</Link>
            ))}
            <div className="flex gap-2 pt-2">
              <Button variant="outline" className="flex-1 rounded-full" onClick={() => navigate("/login")}>Member Login</Button>
              <Button className="flex-1 rounded-full bg-brand-magenta hover:bg-brand-pink" onClick={() => navigate("/apply")}>Apply Now</Button>
            </div>
          </div>
        )}
      </header>

      <main className="flex-1">{children}</main>

      {/* Footer */}
      <footer className="bg-brand-navy-dark text-white mt-20">
        <div className="max-w-7xl mx-auto px-4 py-14 grid md:grid-cols-4 gap-10">
          <div className="md:col-span-2">
            <Logo dark className="h-12 w-12" />
            <p className="text-white/70 text-sm mt-4 max-w-md leading-relaxed">
              The AAWTA Community Engagement Committee connects ambassadors and volunteers to drive impact in trucking, transportation, workforce development, and community empowerment.
            </p>
            <p className="text-brand-pink font-head font-semibold mt-4">Connecting Ambassadors. Engaging Communities. Driving Impact.</p>
          </div>
          <div>
            <h4 className="font-head font-semibold mb-3 text-brand-pink">Explore</h4>
            <ul className="space-y-2 text-sm text-white/70">
              {NAV.slice(0, 6).map((n) => <li key={n.to}><Link to={n.to} className="hover:text-white transition-colors">{n.label}</Link></li>)}
            </ul>
          </div>
          <div>
            <h4 className="font-head font-semibold mb-3 text-brand-pink">Get in touch</h4>
            <ul className="space-y-2 text-sm text-white/70">
              <li>{settings.address}</li>
              <li><a href={`tel:${settings.phone}`} className="hover:text-white">{settings.phone}</a></li>
              <li><a href={`mailto:${settings.email}`} className="hover:text-white">{settings.email}</a></li>
              <li><a href={settings.website} target="_blank" rel="noreferrer" className="hover:text-white">www.aawta.org</a></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-white/10 py-5 px-4 flex flex-col sm:flex-row items-center justify-center gap-x-4 gap-y-2 text-center text-xs text-white/50">
          <span>© {new Date().getFullYear()} African American Women Trucking Association — CEC Connect. All rights reserved.</span>
          <span className="hidden sm:inline text-white/20">|</span>
          <span className="flex items-center gap-3">
            <a href="https://aawta.org/terms-and-conditions" target="_blank" rel="noreferrer" data-testid="footer-terms" className="hover:text-white underline underline-offset-2">Terms &amp; Conditions</a>
            <span className="text-white/20">|</span>
            <a href="https://aawta.org/privacy-policy" target="_blank" rel="noreferrer" data-testid="footer-privacy" className="hover:text-white underline underline-offset-2">Privacy Policy</a>
          </span>
        </div>
      </footer>
    </div>
  );
};
