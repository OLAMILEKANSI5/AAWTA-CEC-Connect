import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Calendar, Plus, MapPin, ExternalLink, CalendarPlus, Download, Camera, Image, X, Users, Send, EyeOff, Pencil } from "lucide-react";
import { api, API, useAuth } from "@/auth";
import { PageTitle, Loading, EmptyState, StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { UploadButton } from "@/components/PortalUpload";
import { EventManage } from "@/components/EventManage";
import { GalleryReview } from "@/components/GalleryReview";
import { US_STATES, EVENT_STATUSES, EVENT_CATEGORIES, EVENT_FORMATS } from "@/lib/constants";

const STAFF = ["super_admin", "director", "administrator"];

export default function Events() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [events, setEvents] = useState(null);
  const [settings, setSettings] = useState({});
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({});
  const [reportEvent, setReportEvent] = useState(null);
  const [rep, setRep] = useState({ photos: [], files: [] });
  const [viewReports, setViewReports] = useState(null);
  const [manageEvent, setManageEvent] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [tab, setTab] = useState("all");
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const onR = (k, v) => setRep((p) => ({ ...p, [k]: v }));

  const load = () => api.get("/events").then((r) => setEvents(r.data)).catch(() => setEvents([]));
  useEffect(() => { load(); api.get("/settings").then((r) => setSettings(r.data)).catch(() => {}); }, []);

  const submit = async () => {
    if (!f.name) { toast.error("Event name required"); return; }
    try {
      const payload = { ...f, ticket_categories: f.ticket_categories ? f.ticket_categories.split(",").map((s) => s.trim()).filter(Boolean) : [] };
      delete payload.image_name;
      if (editingId) { await api.put(`/events/${editingId}`, payload); toast.success("Event updated"); }
      else { await api.post("/events", payload); toast.success(isStaff ? "Event added" : "Event submitted for review"); }
      setOpen(false); setF({}); setEditingId(null); load();
    } catch { toast.error("Failed"); }
  };
  const editEvent = (e) => {
    setEditingId(e.id);
    setF({ ...e, ticket_categories: (e.ticket_categories || []).join(", "), image_name: e.image_file_id ? "Current image attached" : undefined });
    setOpen(true);
  };
  const setStatus = async (id, status) => { await api.put(`/events/${id}/status`, { status }); toast.success(status); load(); };
  const publishToggle = async (e) => { await api.put(`/events/${e.id}/publish`, { published: !e.published }); toast.success(e.published ? "Unpublished" : "Published to public calendar"); load(); };
  const archiveEvent = async (id) => { await api.put(`/events/${id}/archive`); toast.success("Archived"); load(); };
  const submitReport = async () => {
    if (!rep.outcomes) { toast.error("Please describe the outcomes"); return; }
    try {
      await api.post(`/events/${reportEvent.id}/report`, {
        actual_attendance: rep.actual_attendance ? Number(rep.actual_attendance) : null,
        outcomes: rep.outcomes, highlights: rep.highlights,
        photo_file_ids: rep.photos.map((p) => p.id),
        photo_captions: Object.fromEntries(rep.photos.filter((p) => p.caption).map((p) => [p.id, p.caption])),
        file_ids: rep.files.map((x) => x.id),
      });
      toast.success("Post-event report submitted"); setReportEvent(null); setRep({ photos: [], files: [] }); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const openReports = async (ev) => {
    try { const { data } = await api.get(`/events/${ev.id}/reports`); setViewReports({ ev, reports: data }); }
    catch { toast.error("Could not load reports"); }
  };
  const toYmd = (dt) => dt.toISOString().slice(0, 10).replace(/-/g, "");
  const gcalUrl = (e) => {
    if (!e.date) return "#";
    const s = new Date(e.date); const en = new Date(s.getTime() + 86400000);
    const p = new URLSearchParams({ action: "TEMPLATE", text: e.name || "", details: e.description || "", location: e.location || "", dates: `${toYmd(s)}/${toYmd(en)}` });
    return `https://calendar.google.com/calendar/render?${p.toString()}`;
  };

  return (
    <div className="space-y-5">
      <PageTitle title="Events & Calendar" subtitle="Community events and requests" action={
        <div className="flex gap-2">
          {settings.calendar_link && <a href={settings.calendar_link} target="_blank" rel="noreferrer"><Button variant="outline" className="rounded-full"><Calendar size={15} className="mr-1" /> AAWTA Calendar <ExternalLink size={13} className="ml-1" /></Button></a>}
          <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) { setF({}); setEditingId(null); } }}>
            <DialogTrigger asChild><Button data-testid="new-event-btn" onClick={() => { setEditingId(null); setF({}); }} className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> {isStaff ? "Add Event" : "Submit Event"}</Button></DialogTrigger>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader><DialogTitle>{editingId ? "Edit Event" : (isStaff ? "Add Event" : "Submit Event Idea")}</DialogTitle><DialogDescription>{editingId ? "Update the details below — changes save to the existing event." : "Fill in the event details below."}</DialogDescription></DialogHeader>
              <div className="space-y-4">
                <Field label="Event name" name="name" value={f.name} onChange={on} required />
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Event type" name="event_type" value={f.event_type} onChange={on} />
                  <Field label="Date" name="date" type="date" value={f.date} onChange={on} />
                  <Field label="Start time" name="start_time" value={f.start_time} onChange={on} />
                  <Field label="End time" name="end_time" value={f.end_time} onChange={on} />
                  <Field label="Time zone (e.g. ET)" name="timezone" value={f.timezone} onChange={on} />
                  <Field label="Venue name" name="venue_name" value={f.venue_name} onChange={on} />
                  <Field label="Venue address" name="venue_address" value={f.venue_address} onChange={on} />
                  <Field label="Virtual link" name="virtual_link" value={f.virtual_link} onChange={on} />
                  <Field label="Ticket categories (comma-separated)" name="ticket_categories" value={f.ticket_categories} onChange={on} />
                  <SelectField label="Category" name="category" value={f.category} onChange={on} options={EVENT_CATEGORIES} />
                  <SelectField label="Format" name="format" value={f.format} onChange={on} options={EVENT_FORMATS} />
                  <Field label="City" name="city" value={f.city} onChange={on} />
                  <Field label="Capacity" name="capacity" type="number" value={f.capacity} onChange={on} />
                  <Field label="Location / virtual link" name="location" value={f.location} onChange={on} />
                  <SelectField label="State" name="state" value={f.state} onChange={on} options={US_STATES} />
                  <Field label="Target audience" name="audience" value={f.audience} onChange={on} />
                  <Field label="Estimated attendance" name="estimated_attendance" type="number" value={f.estimated_attendance} onChange={on} />
                </div>
                <Field label="Description" name="description" value={f.description} onChange={on} textarea />
                <div className="grid grid-cols-2 gap-4">
                  <label className="flex items-center gap-2 text-sm mt-2"><input type="checkbox" data-testid="paid-toggle" checked={!!f.is_paid} onChange={(e) => on("is_paid", e.target.checked)} className="accent-[#D6189B]" /> Paid event</label>
                  <label className="flex items-center gap-2 text-sm mt-2"><input type="checkbox" data-testid="allow-cancellation" checked={f.allow_cancellation !== false} onChange={(e) => on("allow_cancellation", e.target.checked)} className="accent-[#D6189B]" /> Allow attendees to cancel</label>
                  {f.is_paid && <Field label="Price" name="price" value={f.price} onChange={on} />}
                  <Field label="Registration URL (optional)" name="registration_url" value={f.registration_url} onChange={on} />
                  {f.is_paid && <Field label="Ticket URL (optional)" name="ticket_url" value={f.ticket_url} onChange={on} />}
                </div>
                <div>{f.image_name ? <span className="text-sm text-emerald-600">{f.image_name}</span> : <UploadButton testid="event-image-upload" category="event-image" accept="image/*" label="Event image" onUploaded={(x) => setF((p) => ({ ...p, image_file_id: x.id, image_name: x.filename }))} />}</div>
                <Field label="Requested support" name="requested_support" value={f.requested_support} onChange={on} textarea />
              </div>
              <DialogFooter><Button onClick={submit} data-testid="save-event-btn" className="bg-brand-magenta hover:bg-brand-pink">{editingId ? "Save Changes" : (isStaff ? "Add" : "Submit")}</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      } />

      {events !== null && (
        <div className="flex flex-wrap gap-1 mb-4 border-b border-slate-200" data-testid="event-subtabs">
          {[["all", "Calendar"], ["my", "My Events"], ...(isStaff ? [["allstaff", "All Events"], ["awaiting", "Awaiting Approval"], ["gallery", "Photo Gallery"]] : []), ["published", "Published"], ["archived", "Archived"]].map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)} data-testid={`subtab-${k}`} className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === k ? "border-brand-magenta text-brand-magenta" : "border-transparent text-slate-500 hover:text-brand-navy"}`}>{label}</button>
          ))}
        </div>
      )}

      {tab === "gallery" ? <GalleryReview /> : events === null ? <Loading /> : (() => {
        const filtered = (events || []).filter((e) => {
          if (tab === "my") return e.submitted_by_id === user?.user_id;
          if (tab === "awaiting") return ["Submitted", "Under Review"].includes(e.status);
          if (tab === "published") return e.published && !e.archived;
          if (tab === "archived") return e.archived;
          if (tab === "allstaff") return true;
          return !e.archived;
        });
        return filtered.length === 0 ? <EmptyState icon={Calendar} title="No events here" /> : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((e) => (
            <div key={e.id} className="bg-white border border-slate-200 rounded-xl p-5" data-testid={`event-${e.id}`}>
              <div className="flex items-start justify-between"><div className="h-10 w-10 rounded-lg bg-brand-magenta/10 text-brand-magenta flex items-center justify-center"><Calendar size={18} /></div><div className="flex flex-col items-end gap-1"><StatusBadge status={e.status} />{e.published && <span className="text-[10px] font-semibold text-emerald-600">● Published</span>}{e.archived && <span className="text-[10px] font-semibold text-slate-400">Archived</span>}</div></div>
              <p className="font-head font-semibold text-brand-navy mt-3">{e.name}</p>
              <p className="text-sm text-slate-500 mt-1">{e.date ? new Date(e.date + "T00:00").toLocaleDateString() : "Date TBA"}{e.category ? ` · ${e.category}` : ""}</p>
              {(e.city || e.location) && <p className="text-xs text-slate-400 flex items-center gap-1 mt-1"><MapPin size={12} /> {e.format === "Virtual" ? "Virtual" : (e.city ? `${e.city}, ${e.state || ""}` : e.location)}</p>}
              <p className="text-xs text-slate-400 mt-2">by {e.submitted_by}</p>
              {isStaff && ["Approved", "Scheduled", "Completed"].includes(e.status) && !e.archived && (
                <div className="flex flex-wrap gap-2 mt-3">
                  <Button size="sm" variant={e.published ? "outline" : "default"} onClick={() => publishToggle(e)} data-testid={`publish-${e.id}`} className={e.published ? "text-slate-600" : "bg-emerald-600 hover:bg-emerald-700"}>{e.published ? <><EyeOff size={13} className="mr-1" /> Unpublish</> : <><Send size={13} className="mr-1" /> Publish</>}</Button>
                  <Button size="sm" variant="outline" onClick={() => editEvent(e)} data-testid={`edit-event-${e.id}`} className="text-brand-navy border-brand-navy/30"><Pencil size={13} className="mr-1" /> Edit</Button>
                  <Button size="sm" variant="outline" onClick={() => setManageEvent(e)} data-testid={`manage-${e.id}`} className="text-brand-navy border-brand-navy/30"><Users size={13} className="mr-1" /> Registrations</Button>
                  <Button size="sm" variant="outline" onClick={() => archiveEvent(e.id)} data-testid={`archive-${e.id}`} className="text-slate-500">Archive</Button>
                </div>
              )}
              {isStaff && ["Submitted", "Under Review"].includes(e.status) && (
                <div className="flex gap-2 mt-3">
                  <Button size="sm" onClick={() => setStatus(e.id, "Approved")} data-testid={`approve-event-${e.id}`} className="bg-emerald-600 hover:bg-emerald-700 flex-1">Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => editEvent(e)} data-testid={`edit-event-${e.id}`} className="text-brand-navy border-brand-navy/30"><Pencil size={13} className="mr-1" /> Edit</Button>
                  <Button size="sm" variant="outline" onClick={() => setStatus(e.id, "Declined")} className="text-rose-600 border-rose-200 flex-1">Decline</Button>
                </div>
              )}
              {["Approved", "Scheduled", "Completed"].includes(e.status) && (
                <div className="flex flex-wrap gap-2 mt-3">
                  <a href={gcalUrl(e)} target="_blank" rel="noreferrer" data-testid={`gcal-${e.id}`}><Button size="sm" variant="outline" className="text-brand-navy border-brand-navy/30"><CalendarPlus size={14} className="mr-1" /> Add to Google</Button></a>
                  <a href={`${API}/events/${e.id}/ics`} data-testid={`ics-${e.id}`}><Button size="sm" variant="outline"><Download size={14} className="mr-1" /> .ics</Button></a>
                  {(isStaff || e.submitted_by_id === user?.user_id) && <Button size="sm" onClick={() => setReportEvent(e)} data-testid={`report-event-${e.id}`} className="bg-brand-magenta hover:bg-brand-pink"><Camera size={14} className="mr-1" /> Post-Event Report</Button>}
                  {(e.reports?.length > 0) && (isStaff || e.public || e.submitted_by_id === user?.user_id) && <Button size="sm" variant="outline" onClick={() => openReports(e)} data-testid={`view-reports-${e.id}`}><Image size={14} className="mr-1" /> Reports ({e.reports.length})</Button>}
                </div>
              )}
            </div>
          ))}
        </div>
        );
      })()}
      {manageEvent && <EventManage event={manageEvent} onClose={() => setManageEvent(null)} />}

      <Dialog open={!!reportEvent} onOpenChange={(o) => !o && setReportEvent(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Post-Event Report — {reportEvent?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <Field label="Actual attendance" name="actual_attendance" type="number" value={rep.actual_attendance} onChange={onR} />
            <Field label="Outcomes" name="outcomes" value={rep.outcomes} onChange={onR} textarea required />
            <Field label="Highlights" name="highlights" value={rep.highlights} onChange={onR} textarea />
            <div>
              <span className="text-sm text-slate-700">Photos</span>
              {rep.photos.length > 0 && <div className="space-y-2 my-2">{rep.photos.map((p, idx) => (
                <div key={p.id} className="flex items-center gap-2">
                  <span className="text-xs text-slate-600 truncate max-w-[110px]" title={p.filename}>{p.filename}</span>
                  <input value={p.caption || ""} onChange={(e) => onR("photos", rep.photos.map((x) => x.id === p.id ? { ...x, caption: e.target.value } : x))} placeholder="Add a caption…" maxLength={140} data-testid={`photo-caption-${idx}`} className="flex-1 rounded-md border border-input px-2 py-1 text-xs" />
                  <button onClick={() => onR("photos", rep.photos.filter((x) => x.id !== p.id))}><X size={14} className="text-slate-400 hover:text-rose-500" /></button>
                </div>
              ))}</div>}
              <UploadButton testid="report-photo-upload" category="event-photo" accept="image/*" label="Add photo" onUploaded={(x) => onR("photos", [...rep.photos, x])} />
            </div>
            <div>
              <span className="text-sm text-slate-700">Supporting files (flyers, reports)</span>
              {rep.files.length > 0 && <div className="flex flex-wrap gap-2 my-2">{rep.files.map((p) => (
                <span key={p.id} className="flex items-center gap-1 text-xs bg-slate-100 rounded-full px-2 py-1">{p.filename} <button onClick={() => onR("files", rep.files.filter((x) => x.id !== p.id))}><X size={12} /></button></span>
              ))}</div>}
              <UploadButton testid="report-file-upload" category="event-file" label="Add file" onUploaded={(x) => onR("files", [...rep.files, x])} />
            </div>
          </div>
          <DialogFooter><Button onClick={submitReport} data-testid="submit-event-report-btn" className="bg-brand-magenta hover:bg-brand-pink">Submit Report</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!viewReports} onOpenChange={(o) => !o && setViewReports(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Reports — {viewReports?.ev?.name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            {viewReports?.reports?.map((r) => (
              <div key={r.id} className="border border-slate-200 rounded-lg p-4">
                <p className="text-xs text-slate-400">{r.submitted_by} · {new Date(r.created_at).toLocaleDateString()}</p>
                {r.actual_attendance != null && <p className="text-sm mt-1"><b>Attendance:</b> {r.actual_attendance}</p>}
                <p className="text-sm mt-1"><b>Outcomes:</b> {r.outcomes}</p>
                {r.highlights && <p className="text-sm mt-1"><b>Highlights:</b> {r.highlights}</p>}
                {r.photos?.length > 0 && <div className="grid grid-cols-3 gap-2 mt-2">{r.photos.map((p) => (
                  <a key={p.id} href={`${API}/files/${p.id}/download`} target="_blank" rel="noreferrer" className="block">
                    <img src={`${API}/files/${p.id}/download`} alt={p.caption || ""} className="h-20 w-full object-cover rounded-md" />
                    {p.caption && <span className="block text-[10px] text-slate-500 mt-0.5 line-clamp-2">{p.caption}</span>}
                  </a>
                ))}</div>}
                {r.files?.length > 0 && <div className="mt-2 space-y-1">{r.files.map((file) => (
                  <a key={file.id} href={`${API}/files/${file.id}/download`} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-brand-navy underline"><Download size={12} /> {file.original_filename}</a>
                ))}</div>}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
