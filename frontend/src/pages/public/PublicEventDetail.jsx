import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PublicLayout } from "@/components/PublicLayout";
import { Loading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { api, API } from "@/auth";
import { EVENT_CAT_COLORS, US_STATES_TERRITORIES } from "@/lib/constants";
import { Calendar, MapPin, Clock, ArrowLeft, Users, Ticket, Video, CheckCircle2 } from "lucide-react";
import { regLabel } from "@/components/EventCard";

export default function PublicEventDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [e, setE] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ newsletter_opt_in: false, events_opt_in: false });
  const [done, setDone] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => { api.get(`/public/events/${id}`).then((r) => setE(r.data)).catch(() => setNotFound(true)); }, [id]);

  const cats = (e?.ticket_categories && e.ticket_categories.length) ? e.ticket_categories : ["General Admission"];
  useEffect(() => { if (e && !f.ticket_category) on("ticket_category", cats[0]); /* eslint-disable-next-line */ }, [e]);

  const register = async () => {
    if (f.company_website) return; // honeypot
    for (const [k, label] of [["first_name", "First name"], ["last_name", "Last name"], ["email", "Email"], ["phone", "Phone"], ["state", "State"], ["ticket_category", "Registration category"]]) {
      if (!f[k]) { toast.error(`${label} is required`); return; }
    }
    if (f.is_member === undefined || f.is_member === "") { toast.error("Please tell us if you are an AAWTA member"); return; }
    setSubmitting(true);
    try {
      const payload = {
        first_name: f.first_name, last_name: f.last_name, email: f.email, phone: f.phone, state: f.state,
        is_member: f.is_member === "Yes", ticket_category: f.ticket_category,
        business_name: f.business_name || null, business_website: f.business_website || null,
        job_title: f.job_title || null, city: f.city || null, zip_code: f.zip_code || null,
        dietary: f.dietary || null, accessibility: f.accessibility || null,
        newsletter_opt_in: !!f.newsletter_opt_in, events_opt_in: !!f.events_opt_in,
        honeypot: f.company_website || "",
      };
      const { data } = await api.post(`/public/events/${id}/register`, payload);
      setDone(data); setOpen(false);
    } catch (err) { toast.error(err?.response?.data?.detail || "Registration failed"); }
    finally { setSubmitting(false); }
  };

  if (notFound) return <PublicLayout><div className="max-w-lg mx-auto px-4 py-24 text-center"><h1 className="font-head text-2xl font-bold text-brand-navy">Event not available</h1><p className="text-slate-500 mt-2">This event may be unpublished, cancelled or private.</p><Button className="mt-6 rounded-full bg-brand-magenta hover:bg-brand-pink" onClick={() => navigate("/events")}>Back to Calendar</Button></div></PublicLayout>;
  if (!e) return <PublicLayout><Loading /></PublicLayout>;
  const reg = regLabel(e);
  const loc = e.format === "Virtual" ? "Virtual Event" : e.venue_name || [e.city, e.state].filter(Boolean).join(", ") || e.location;
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
          <h1 className="font-head text-3xl md:text-4xl font-extrabold" data-testid="event-detail-name">{e.name}</h1>
          <div className="flex flex-wrap gap-5 mt-4 text-white/80 text-sm">
            <span className="flex items-center gap-1.5"><Calendar size={15} className="text-brand-pink" /> {e.date ? new Date(e.date + "T00:00").toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" }) : "Date TBA"}</span>
            {(e.start_time || e.end_time) && <span className="flex items-center gap-1.5"><Clock size={15} className="text-brand-pink" /> {[e.start_time, e.end_time].filter(Boolean).join(" – ")}{e.timezone ? ` ${e.timezone}` : ""}</span>}
            <span className="flex items-center gap-1.5">{e.format === "Virtual" ? <Video size={15} className="text-brand-pink" /> : <MapPin size={15} className="text-brand-pink" />} {loc}</span>
          </div>
        </div>
      </section>
      <section className="max-w-4xl mx-auto px-4 py-10 grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2">
          <h2 className="font-head font-bold text-brand-navy text-xl mb-3">About this event</h2>
          <p className="text-slate-600 whitespace-pre-wrap leading-relaxed">{e.description || "Details coming soon."}</p>
          {e.venue_address && e.format !== "Virtual" && <p className="text-sm text-slate-500 mt-4 flex items-center gap-1.5"><MapPin size={15} className="text-brand-magenta" /> {e.venue_address}</p>}
        </div>
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            {e.capacity ? <p className="text-sm text-slate-500 flex items-center gap-1.5 mb-3"><Users size={15} /> {e.registered_count || 0}{e.capacity ? ` / ${e.capacity}` : ""} registered</p> : null}
            {done ? (
              <div className="text-center py-2" data-testid="registration-success"><CheckCircle2 className="mx-auto text-emerald-500 mb-2" size={32} /><p className="font-semibold text-brand-navy">{done.status === "waitlist" ? "You're on the waitlist!" : "You're registered!"}</p><p className="text-xs text-slate-500 mt-1">Confirmation # <span className="font-mono font-semibold text-brand-navy" data-testid="confirmation-number">{done.confirmation_number}</span></p><p className="text-xs text-slate-500 mt-1">Check your email for your confirmation and QR code.</p></div>
            ) : externalUrl ? (
              <a href={externalUrl} target="_blank" rel="noopener noreferrer"><Button data-testid="external-register-btn" disabled={reg.disabled} className="w-full bg-brand-magenta hover:bg-brand-pink rounded-full"><Ticket size={16} className="mr-1" /> {reg.label}</Button></a>
            ) : (
              <Button data-testid="open-register-btn" disabled={reg.disabled} onClick={() => setOpen(true)} className="w-full bg-brand-magenta hover:bg-brand-pink rounded-full"><Ticket size={16} className="mr-1" /> {reg.label}</Button>
            )}
          </div>
        </div>
      </section>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{reg.label} — {e.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <input type="text" value={f.company_website || ""} onChange={(ev) => on("company_website", ev.target.value)} className="hidden" tabIndex={-1} autoComplete="off" />
            <div className="grid grid-cols-2 gap-4">
              <Field label="First name" name="first_name" value={f.first_name} onChange={on} required />
              <Field label="Last name" name="last_name" value={f.last_name} onChange={on} required />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Email" name="email" type="email" value={f.email} onChange={on} required />
              <Field label="Phone" name="phone" value={f.phone} onChange={on} required />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <SelectField label="State / Territory" name="state" value={f.state} onChange={on} options={US_STATES_TERRITORIES} required />
              <SelectField label="AAWTA member?" name="is_member" value={f.is_member} onChange={on} options={["Yes", "No"]} required />
            </div>
            <SelectField label="Registration category" name="ticket_category" value={f.ticket_category} onChange={on} options={cats} required />
            <div className="pt-1 text-xs font-semibold text-slate-400 uppercase tracking-wide">Optional details</div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Business / organization" name="business_name" value={f.business_name} onChange={on} />
              <Field label="Business website" name="business_website" value={f.business_website} onChange={on} />
              <Field label="Job title" name="job_title" value={f.job_title} onChange={on} />
              <Field label="City" name="city" value={f.city} onChange={on} />
              <Field label="ZIP code" name="zip_code" value={f.zip_code} onChange={on} />
            </div>
            <Field label="Dietary restrictions" name="dietary" value={f.dietary} onChange={on} />
            <Field label="Accessibility requests" name="accessibility" value={f.accessibility} onChange={on} />
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <label className="flex items-start gap-2 text-sm text-slate-600 cursor-pointer"><input type="checkbox" data-testid="opt-newsletter" checked={!!f.newsletter_opt_in} onChange={(ev) => on("newsletter_opt_in", ev.target.checked)} className="accent-[#D6189B] mt-0.5" /> Yes, I would like to receive the AAWTA newsletter.</label>
              <label className="flex items-start gap-2 text-sm text-slate-600 cursor-pointer"><input type="checkbox" data-testid="opt-events" checked={!!f.events_opt_in} onChange={(ev) => on("events_opt_in", ev.target.checked)} className="accent-[#D6189B] mt-0.5" /> Yes, I would like to receive information about upcoming AAWTA events, programs and opportunities.</label>
            </div>
            <p className="text-xs text-slate-500 pt-2" data-testid="register-legal-ack">By submitting, you acknowledge AAWTA's <a href="https://aawta.org/terms-and-conditions" target="_blank" rel="noreferrer" className="text-brand-magenta underline underline-offset-2">Terms &amp; Conditions</a> and <a href="https://aawta.org/privacy-policy" target="_blank" rel="noreferrer" className="text-brand-magenta underline underline-offset-2">Privacy Policy</a>.</p>
          </div>
          <DialogFooter><Button onClick={register} disabled={submitting} data-testid="submit-register-btn" className="bg-brand-magenta hover:bg-brand-pink">{submitting ? "Submitting…" : "Confirm Registration"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </PublicLayout>
  );
}
