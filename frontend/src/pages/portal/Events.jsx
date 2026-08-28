import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Calendar, Plus, MapPin, ExternalLink } from "lucide-react";
import { api, useAuth } from "@/auth";
import { PageTitle, Loading, EmptyState, StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { US_STATES, EVENT_STATUSES } from "@/lib/constants";

const STAFF = ["super_admin", "director", "administrator"];

export default function Events() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [events, setEvents] = useState(null);
  const [settings, setSettings] = useState({});
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({});
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => api.get("/events").then((r) => setEvents(r.data)).catch(() => setEvents([]));
  useEffect(() => { load(); api.get("/settings").then((r) => setSettings(r.data)).catch(() => {}); }, []);

  const submit = async () => { if (!f.name) { toast.error("Event name required"); return; } try { await api.post("/events", f); toast.success(isStaff ? "Event added" : "Event submitted for review"); setOpen(false); setF({}); load(); } catch { toast.error("Failed"); } };
  const setStatus = async (id, status) => { await api.put(`/events/${id}/status`, { status }); toast.success(status); load(); };

  return (
    <div className="space-y-5">
      <PageTitle title="Events & Calendar" subtitle="Community events and requests" action={
        <div className="flex gap-2">
          {settings.calendar_link && <a href={settings.calendar_link} target="_blank" rel="noreferrer"><Button variant="outline" className="rounded-full"><Calendar size={15} className="mr-1" /> AAWTA Calendar <ExternalLink size={13} className="ml-1" /></Button></a>}
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button data-testid="new-event-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> {isStaff ? "Add Event" : "Submit Event"}</Button></DialogTrigger>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader><DialogTitle>{isStaff ? "Add Event" : "Submit Event Idea"}</DialogTitle></DialogHeader>
              <div className="space-y-4">
                <Field label="Event name" name="name" value={f.name} onChange={on} required />
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Event type" name="event_type" value={f.event_type} onChange={on} />
                  <Field label="Date" name="date" type="date" value={f.date} onChange={on} />
                  <Field label="Location / virtual link" name="location" value={f.location} onChange={on} />
                  <SelectField label="State" name="state" value={f.state} onChange={on} options={US_STATES} />
                  <Field label="Target audience" name="audience" value={f.audience} onChange={on} />
                  <Field label="Estimated attendance" name="estimated_attendance" type="number" value={f.estimated_attendance} onChange={on} />
                </div>
                <Field label="Description" name="description" value={f.description} onChange={on} textarea />
                <Field label="Requested support" name="requested_support" value={f.requested_support} onChange={on} textarea />
              </div>
              <DialogFooter><Button onClick={submit} data-testid="save-event-btn" className="bg-brand-magenta hover:bg-brand-pink">{isStaff ? "Add" : "Submit"}</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      } />

      {events === null ? <Loading /> : events.length === 0 ? <EmptyState icon={Calendar} title="No events yet" /> : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {events.map((e) => (
            <div key={e.id} className="bg-white border border-slate-200 rounded-xl p-5" data-testid={`event-${e.id}`}>
              <div className="flex items-start justify-between"><div className="h-10 w-10 rounded-lg bg-brand-magenta/10 text-brand-magenta flex items-center justify-center"><Calendar size={18} /></div><StatusBadge status={e.status} /></div>
              <p className="font-head font-semibold text-brand-navy mt-3">{e.name}</p>
              <p className="text-sm text-slate-500 mt-1">{e.date ? new Date(e.date).toLocaleDateString() : "Date TBA"}</p>
              {e.location && <p className="text-xs text-slate-400 flex items-center gap-1 mt-1"><MapPin size={12} /> {e.location}</p>}
              <p className="text-xs text-slate-400 mt-2">by {e.submitted_by}</p>
              {isStaff && ["Submitted", "Under Review"].includes(e.status) && (
                <div className="flex gap-2 mt-3">
                  <Button size="sm" onClick={() => setStatus(e.id, "Approved")} data-testid={`approve-event-${e.id}`} className="bg-emerald-600 hover:bg-emerald-700 flex-1">Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => setStatus(e.id, "Declined")} className="text-rose-600 border-rose-200 flex-1">Decline</Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
