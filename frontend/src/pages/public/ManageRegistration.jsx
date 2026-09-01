import React, { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PublicLayout } from "@/components/PublicLayout";
import { Loading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { api, API } from "@/auth";
import { Calendar, MapPin, Clock, Ticket, CheckCircle2, XCircle, Video } from "lucide-react";

export default function ManageRegistration() {
  const { conf } = useParams();
  const [sp] = useSearchParams();
  const token = sp.get("t");
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const load = () => api.get(`/public/registrations/${conf}?token=${encodeURIComponent(token || "")}`).then((r) => setData(r.data)).catch(() => setNotFound(true));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [conf, token]);

  const cancel = async () => {
    if (!window.confirm("Cancel this registration? This cannot be undone.")) return;
    setCancelling(true);
    try { await api.post(`/public/registrations/${conf}/cancel`, { token }); toast.success("Registration cancelled"); load(); }
    catch (err) { toast.error(err?.response?.data?.detail || "Could not cancel"); }
    finally { setCancelling(false); }
  };

  if (notFound) return <PublicLayout><div className="max-w-lg mx-auto px-4 py-24 text-center"><h1 className="font-head text-2xl font-bold text-brand-navy">Registration not found</h1><p className="text-slate-500 mt-2">This link may be invalid or expired.</p><Button className="mt-6 rounded-full bg-brand-magenta hover:bg-brand-pink" onClick={() => navigate("/events")}>Browse Events</Button></div></PublicLayout>;
  if (!data) return <PublicLayout><Loading /></PublicLayout>;
  const { registration: r, event: e } = data;
  const cancelled = r.status === "cancelled";
  const loc = e.format === "Virtual" ? "Virtual Event" : e.venue_name || [e.city, e.state].filter(Boolean).join(", ");

  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-12">
        <div className="max-w-3xl mx-auto px-4">
          <p className="text-brand-pink text-sm font-semibold uppercase tracking-wide">Your Registration</p>
          <h1 className="font-head text-3xl font-extrabold mt-1" data-testid="manage-event-name">{e.name}</h1>
          <p className="text-white/70 mt-2 font-mono">Confirmation # {r.confirmation_number}</p>
        </div>
      </section>
      <section className="max-w-3xl mx-auto px-4 py-10 grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-2 text-sm">
            <p className="flex items-center gap-2"><Calendar size={15} className="text-brand-magenta" /> {e.date ? new Date(e.date + "T00:00").toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" }) : "Date TBA"}</p>
            {(e.start_time || e.end_time) && <p className="flex items-center gap-2"><Clock size={15} className="text-brand-magenta" /> {[e.start_time, e.end_time].filter(Boolean).join(" – ")}{e.timezone ? ` ${e.timezone}` : ""}</p>}
            <p className="flex items-center gap-2">{e.format === "Virtual" ? <Video size={15} className="text-brand-magenta" /> : <MapPin size={15} className="text-brand-magenta" />} {loc}{e.venue_address ? ` · ${e.venue_address}` : ""}</p>
            <p className="flex items-center gap-2"><Ticket size={15} className="text-brand-magenta" /> {r.ticket_category}</p>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-5 text-sm">
            <p className="font-semibold text-brand-navy mb-2">Attendee</p>
            <p className="text-slate-600">{r.name} · {r.email}</p>
            <div className="flex flex-wrap gap-2 mt-3">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cancelled ? "bg-rose-100 text-rose-700" : r.status === "waitlist" ? "bg-purple-100 text-purple-700" : "bg-emerald-100 text-emerald-700"}`} data-testid="reg-status">{cancelled ? "Cancelled" : r.status === "waitlist" ? "Waitlisted" : "Registered"}</span>
              {r.checked_in && <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">Checked In</span>}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          {!cancelled && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 text-center">
            <p className="text-xs text-slate-500 mb-2">Check-in QR code</p>
            <img src={`${API}/public/qr/${r.checkin_token}.png`} alt="Check-in QR" width={160} height={160} className="mx-auto border border-slate-100 rounded-lg" data-testid="manage-qr" />
          </div>
          )}
          {!cancelled && !r.checked_in && e.allow_cancellation && (
            <Button variant="outline" onClick={cancel} disabled={cancelling} data-testid="cancel-registration-btn" className="w-full text-rose-600 border-rose-200 hover:bg-rose-50"><XCircle size={15} className="mr-1" /> {cancelling ? "Cancelling…" : "Cancel Registration"}</Button>
          )}
          {cancelled && <p className="text-center text-sm text-slate-400 flex items-center justify-center gap-1"><XCircle size={14} /> This registration is cancelled</p>}
          {!e.allow_cancellation && !cancelled && <p className="text-center text-xs text-slate-400 flex items-center justify-center gap-1"><CheckCircle2 size={12} /> Contact AAWTA to make changes</p>}
        </div>
      </section>
    </PublicLayout>
  );
}
