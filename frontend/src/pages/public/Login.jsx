import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { PublicLayout } from "@/components/PublicLayout";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { api, useAuth } from "@/auth";
import { AlertCircle } from "lucide-react";

export default function Login() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [error, setError] = useState(location.state?.error || "");

  useEffect(() => { if (!loading && user) navigate("/portal"); }, [user, loading, navigate]);

  const handleGoogle = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/portal";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <PublicLayout>
      <section className="min-h-[70vh] flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-8 shadow-sm text-center">
          <div className="flex justify-center mb-6"><Logo /></div>
          <h1 className="font-head text-2xl font-extrabold text-brand-navy">Member Login</h1>
          <p className="text-slate-500 text-sm mt-2">Access the private CEC Connect portal with your approved Google account.</p>

          {error && (
            <div className="mt-5 flex items-start gap-2 text-left bg-rose-50 border border-rose-200 text-rose-700 rounded-lg p-3 text-sm" data-testid="login-error">
              <AlertCircle size={18} className="shrink-0 mt-0.5" /><span>{error}</span>
            </div>
          )}

          <Button onClick={handleGoogle} data-testid="google-login-btn" className="mt-6 w-full h-12 rounded-full bg-brand-navy hover:bg-brand-navy-dark text-white gap-3">
            <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.5 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20c11 0 19.7-8 19.7-20 0-1.3-.1-2.3-.1-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.5 6.5 29.5 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 10-2 13.6-5.2l-6.3-5.3C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.1-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4 5.5l6.3 5.3C41.9 36.3 44 30.7 44 24c0-1.3-.1-2.3-.4-3.5z"/></svg>
            Continue with Google
          </Button>
          <p className="text-xs text-slate-400 mt-5">Not a member yet? <button onClick={() => navigate("/apply")} className="text-brand-magenta font-medium hover:underline">Apply here</button></p>
          <p className="text-[11px] text-slate-400 mt-4 leading-relaxed" data-testid="login-legal-ack">By continuing, you acknowledge AAWTA's <a href="https://aawta.org/terms-and-conditions" target="_blank" rel="noreferrer" className="text-brand-magenta underline underline-offset-2">Terms &amp; Conditions</a> and <a href="https://aawta.org/privacy-policy" target="_blank" rel="noreferrer" className="text-brand-magenta underline underline-offset-2">Privacy Policy</a>.</p>
        </div>
      </section>
    </PublicLayout>
  );
}
