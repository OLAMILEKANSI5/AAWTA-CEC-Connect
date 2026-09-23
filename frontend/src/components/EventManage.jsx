import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/auth";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Search, UserPlus, CheckCircle2, Users } from "lucide-react";
import { BadgeCenter } from "@/components/BadgeCenter";
import { RegistrationTable } from "@/components/RegistrationTable";
import { US_STATES_TERRITORIES } from "@/lib/constants";

export const EventManage = ({ event, onClose }) => {
  const [data, setData] = useState({ registrations: [], total: 0, checked_in: 0 });
  const [q, setQ] = useState("");
  const [walkin, setWalkin] = useState({ first_name: "", last_name: "", email: "", phone: "", state: "", member_status: "Unknown", ticket_category: "General Admission" });

  const load = () => api.get(`/events/${event.id}/registrations${q ? `?q=${q}` : ""}`).then((r) => setData(r.data)).catch(() => {});
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); /* eslint-disable-next-line */ }, [q]);

  const checkin = async (r, val) => { await api.put(`/registrations/${r.id}/checkin`, { checked_in: val }); load(); };
  const [assignable, setAssignable] = useState([]);
  const [assigned, setAssigned] = useState(new Set(event.checkin_assignees || []));
  const [assignQ, setAssignQ] = useState("");
  useEffect(() => { api.get("/checkin-assignable").then((r) => setAssignable(r.data)).catch(() => {}); }, []);
  const toggleAssign = (uid) => setAssigned((prev) => { const n = new Set(prev); n.has(uid) ? n.delete(uid) : n.add(uid); return n; });
  const saveAssignees = async () => { try { await api.put(`/events/${event.id}/checkin-assignees`, { user_ids: [...assigned] }); toast.success("Check-in volunteers updated"); } catch { toast.error("Failed"); } };
  const addWalkin = async () => { if (!walkin.first_name) { toast.error("First name required"); return; } if (!walkin.email && !walkin.phone) { toast.error("Email or phone required"); return; } try { const { data: r } = await api.post(`/events/${event.id}/registrations`, walkin); setWalkin({ first_name: "", last_name: "", email: "", phone: "", state: "", member_status: "Unknown", ticket_category: "General Admission" }); toast.success("Walk-in checked in"); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-6xl max-h-[92vh] overflow-y-auto overflow-x-hidden">
        <DialogHeader><DialogTitle>Manage — {event.name}</DialogTitle></DialogHeader>
        <div className="flex gap-4 text-sm text-slate-500 mb-2"><span className="flex items-center gap-1"><Users size={14} /> {data.total} registered</span><span className="flex items-center gap-1"><CheckCircle2 size={14} /> {data.checked_in} checked in</span></div>
        <Tabs defaultValue="registrations" className="min-w-0 w-full">
          <TabsList><TabsTrigger value="registrations">Registrations</TabsTrigger><TabsTrigger value="checkin">Check-In</TabsTrigger><TabsTrigger value="volunteers" data-testid="tab-volunteers">Volunteers</TabsTrigger><TabsTrigger value="badges">Badge Center</TabsTrigger></TabsList>

          <TabsContent value="registrations" className="min-w-0">
            <RegistrationTable event={event} onMutate={load} />
          </TabsContent>

          <TabsContent value="checkin">
            <a href={`/portal/events/${event.id}/checkin`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-brand-magenta font-medium mb-3" data-testid="open-checkin-center">Open full Check-In Center →</a>
            <div className="bg-slate-50 rounded-lg p-3 mb-3">
              <p className="text-xs font-semibold text-slate-500 mb-2">Register Walk-In</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 items-end">
                <Input placeholder="First name *" value={walkin.first_name} onChange={(e) => setWalkin((p) => ({ ...p, first_name: e.target.value }))} data-testid="walkin-first" />
                <Input placeholder="Last name" value={walkin.last_name} onChange={(e) => setWalkin((p) => ({ ...p, last_name: e.target.value }))} data-testid="walkin-last" />
                <Input placeholder="Email or phone *" value={walkin.email} onChange={(e) => setWalkin((p) => ({ ...p, email: e.target.value }))} data-testid="walkin-email" />
                <select value={walkin.state} onChange={(e) => setWalkin((p) => ({ ...p, state: e.target.value }))} className="h-10 rounded-md border border-input bg-background px-2 text-sm"><option value="">State…</option>{US_STATES_TERRITORIES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
                <select value={walkin.member_status} onChange={(e) => setWalkin((p) => ({ ...p, member_status: e.target.value }))} className="h-10 rounded-md border border-input bg-background px-2 text-sm">{["Unknown", "Yes", "No"].map((s) => <option key={s} value={s}>{`Member: ${s}`}</option>)}</select>
                <Button size="sm" onClick={addWalkin} data-testid="add-walkin-btn" className="bg-brand-navy hover:bg-brand-navy-dark h-10"><UserPlus size={14} className="mr-1" /> Register & Check In</Button>
              </div>
            </div>
            <div className="relative mb-2"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><Input placeholder="Search attendee to check in…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" /></div>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {data.registrations.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-2 border-b border-slate-100 text-sm">
                  <div><p className="font-medium text-slate-800">{r.name}</p><p className="text-xs text-slate-400">{r.status}</p></div>
                  <Button size="sm" variant={r.checked_in ? "outline" : "default"} onClick={() => checkin(r, !r.checked_in)} data-testid={`checkin-${r.id}`} className={r.checked_in ? "text-emerald-600 border-emerald-200" : "bg-brand-magenta hover:bg-brand-pink"}>{r.checked_in ? "Checked In ✓" : "Check In"}</Button>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="volunteers" className="min-w-0" data-testid="volunteers-panel">
            <p className="text-sm text-slate-500 mb-2">Assign volunteers or staff to run check-in for this event. They'll get access to the Check-In Center and it appears on their profile.</p>
            <div className="relative mb-2"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><Input placeholder="Search people…" value={assignQ} onChange={(e) => setAssignQ(e.target.value)} className="pl-9" data-testid="assignee-search" /></div>
            <div className="space-y-1 max-h-72 overflow-y-auto border border-slate-100 rounded-lg p-2">
              {assignable.filter((u) => !assignQ || (u.name || "").toLowerCase().includes(assignQ.toLowerCase())).map((u) => (
                <label key={u.user_id} className="flex items-center gap-2 p-2 rounded hover:bg-slate-50 cursor-pointer text-sm" data-testid={`assignee-${u.user_id}`}>
                  <input type="checkbox" checked={assigned.has(u.user_id)} onChange={() => toggleAssign(u.user_id)} className="accent-[#D6189B]" />
                  <span className="font-medium text-slate-800">{u.name}</span>
                  <span className="text-xs text-slate-400">{u.role}</span>
                </label>
              ))}
              {assignable.length === 0 && <p className="text-sm text-slate-400 p-2">No assignable users found.</p>}
            </div>
            <div className="flex items-center justify-between mt-3">
              <span className="text-xs text-slate-500">{assigned.size} assigned</span>
              <Button size="sm" onClick={saveAssignees} data-testid="save-assignees-btn" className="bg-brand-magenta hover:bg-brand-pink">Save assignments</Button>
            </div>
          </TabsContent>

          <TabsContent value="badges">
            <BadgeCenter event={event} registrations={data.registrations} />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};
