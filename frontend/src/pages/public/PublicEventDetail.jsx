import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PublicLayout } from "@/components/PublicLayout";
import { Loading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/components/FormFields";
import { api, API } from "@/auth";
import { EVENT_CAT_COLORS } from "@/lib/constants";
import { Calendar, MapPin, Clock, ArrowLeft, Users, Ticket, Video, CheckCircle2 } from "lucide-react";
import { regLabel } from "@/components/EventCard";

export default function PublicEventDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [e, setE] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({});
  const [done, setDone] = useState(null);

  useEffect(() => { api.get(`/public/events/${id}`).then((r) => setE(r.data)).catch(() => setNotFound(true)); }, [id]);

  const register = async () => {
    if (f.company_website) return;
    if (!f.name || !f.email) { toast.error("Name and email required"); return; }
    try { const { data } = await api.post(`/public/events/${id}/register`, { ...f, honeypot: f.company_website || "" }); setDone(data.status); setOpen(false); }
    catch (err) { toast.error(err?.response?.data?.detail || "Registration failed"); }
  };

  if (notFound) return <PublicLayout><div className="max-w-lg mx-auto px-4 py-24 text-center"><h1 className="font-head text-2xl font-bold text-brand-navy">Event not available</h1><p className="text-slate-500 mt-2">This event may be unpublished, cancelled or private.</p><Button className="mt-6 rounded-full bg-brand-magenta hover:bg-brand-pink" onClick={() => navigate("/events")}>Back to Calendar</Button></div></PublicLayout>;
  if (!e) return <PublicLayout><Loading /></PublicLayout>;
  const reg = regLabel(e);
  const loc = e.format === "Virtual" ? "Virtual Event" : [e.city, e.state].filter(Boolean).join(", ") || e.location;
  const externalUrl = e.is_paid ? e.ticket_url : e.registration_url;

  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white">
        {e.image_file_id && <div className="h-56 w-full relative"><img src={`${API}/public/files/${e.image_file_id}`} alt={e.name} className="w-full h-full object-cover opacity-40" onError={(ev) => { ev.currentTarget.style.display = "none"; }} /></div>}
        <div className="max-w-4xl mx-auto px-4 py-10">
          <button onClick={() => navigate("/events")} className="text-white/70 hover:text-white flex items-center gap-1 text-sm mb-4"><ArrowLeft size={15} /> All events</button>
          <div className="flex flex-wrap gap-2 mb-3">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${EVENT_CAT_COLORS[e.category] || "bg-white/10"}`}>{e.category}</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${e.is_paid ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{e.is_paid ? (e.price || "Paid") : "Free"}</span>
          </div>
          <h1 className="font-head text-3xl md:text-4xl font-extrabold">{e.name}</h1>
          <div className="flex flex-wrap gap-5 mt-4 text-white/80 text-sm">
            <span className="flex items-center gap-1.5"><Calendar size={15} className="text-brand-pink" /> {e.date ? new Date(e.date + "T00:00").toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" }) : "Date TBA"}</span>
            {e.start_time && <span className="flex items-center gap-1.5"><Clock size={15} className="text-brand-pink" /> {e.start_time}</span>}
            <span className="flex items-center gap-1.5">{e.format === "Virtual" ? <Video size={15} className="text-brand-pink" /> : <MapPin size={15} className="text-brand-pink" />} {loc}</span>
          </div>
        </div>
      </section>
      <section className="max-w-4xl mx-auto px-4 py-10 grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2">
          <h2 className="font-head font-bold text-brand-navy text-xl mb-3">About this event</h2>
          <p className="text-slate-600 whitespace-pre-wrap leading-relaxed">{e.description || "Details coming soon."}</p>
        </div>
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            {e.capacity ? <p className="text-sm text-slate-500 flex items-center gap-1.5 mb-3"><Users size={15} /> {e.registered_count || 0}{e.capacity ? ` / ${e.capacity}` : ""} registered</p> : null}
            {done ? (
              <div className="text-center py-2" data-testid="registration-success"><CheckCircle2 className="mx-auto text-emerald-500 mb-2" size={32} /><p className="font-semibold text-brand-navy">{done === "waitlist" ? "You're on the waitlist!" : "You're registered!"}</p><p className="text-xs text-slate-500 mt-1">Check your email for confirmation.</p></div>
            ) : externalUrl ? (
              <a href={externalUrl} target="_blank" rel="noopener noreferrer"><Button data-testid="external-register-btn" disabled={reg.disabled} className="w-full bg-brand-magenta hover:bg-brand-pink rounded-full"><Ticket size={16} className="mr-1" /> {reg.label}</Button></a>
            ) : (
              <Button data-testid="open-register-btn" disabled={reg.disabled} onClick={() => setOpen(true)} className="w-full bg-brand-magenta hover:bg-brand-pink rounded-full"><Ticket size={16} className="mr-1" /> {reg.label}</Button>
            )}
          </div>
        </div>
      </section>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{reg.label} — {e.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <input type="text" value={f.company_website || ""} onChange={(ev) => setF((p) => ({ ...p, company_website: ev.target.value }))} className="hidden" tabIndex={-1} autoComplete="off" />
            <Field label="Full name" name="name" value={f.name} onChange={(k, v) => setF((p) => ({ ...p, [k]: v }))} required />
            <Field label="Email" name="email" type="email" value={f.email} onChange={(k, v) => setF((p) => ({ ...p, [k]: v }))} required />
            <Field label="Phone" name="phone" value={f.phone} onChange={(k, v) => setF((p) => ({ ...p, [k]: v }))} />
          </div>
          <DialogFooter><Button onClick={register} data-testid="submit-register-btn" className="bg-brand-magenta hover:bg-brand-pink">Confirm Registration</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </PublicLayout>
  );
}
