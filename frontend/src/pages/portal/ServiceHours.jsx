import React, { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Clock, Play, Square, Plus, Award, Download, Check, X, FileDown } from "lucide-react";
import { api, API, useAuth } from "@/auth";
import { PageTitle, Loading, EmptyState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";

const STAFF = ["super_admin", "director", "administrator"];
const ACTIVITY = ["event", "project", "committee", "remote", "other"];
const STATUS_STYLES = { pending: "bg-amber-100 text-amber-700", approved: "bg-emerald-100 text-emerald-700", rejected: "bg-rose-100 text-rose-600", active: "bg-blue-100 text-blue-700" };

const StatusPill = ({ s }) => <span className={`text-[11px] px-2 py-0.5 rounded-full ${STATUS_STYLES[s] || "bg-slate-100"}`}>{s}</span>;

// ---------- Member (volunteer) view ----------
const MemberHours = () => {
  const [data, setData] = useState(null);
  const [manual, setManual] = useState(false);
  const [clockForm, setClockForm] = useState({ activity_type: "event", category: "", description: "", event_id: "" });
  const [mForm, setMForm] = useState({ date: new Date().toISOString().slice(0, 10), hours: "", activity_type: "remote", category: "", description: "" });
  const load = useCallback(() => api.get("/service-hours/me").then((r) => setData(r.data)).catch(() => setData({ entries: [], summary: {} })), []);
  useEffect(() => { load(); }, [load]);

  if (!data) return <Loading />;
  const s = data.summary || {};
  const active = s.active;

  const clockIn = async () => { try { await api.post("/service-hours/clock-in", clockForm); toast.success("Clocked in"); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } };
  const clockOut = async () => { try { const r = await api.post("/service-hours/clock-out"); toast.success(`Clocked out — ${r.data.hours}h submitted`); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } };
  const submitManual = async () => { if (!mForm.hours) { toast.error("Enter hours"); return; } try { await api.post("/service-hours", { ...mForm, hours: Number(mForm.hours) }); toast.success("Hours submitted for review"); setManual(false); setMForm({ ...mForm, hours: "", description: "" }); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } };
  const remove = async (id) => { try { await api.delete(`/service-hours/${id}`); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } };

  return (
    <div className="space-y-5" data-testid="member-hours">
      <div className="grid sm:grid-cols-3 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl p-4"><p className="text-xs text-slate-400">Approved hours</p><p className="text-3xl font-bold text-brand-navy font-mono-data">{s.approved ?? 0}</p></div>
        <div className="bg-white border border-slate-200 rounded-xl p-4"><p className="text-xs text-slate-400">Pending review</p><p className="text-3xl font-bold text-amber-500 font-mono-data">{s.pending ?? 0}</p></div>
        <div className="bg-white border border-slate-200 rounded-xl p-4"><p className="text-xs text-slate-400">Milestones</p><p className="text-3xl font-bold text-brand-magenta font-mono-data">{(s.earned_milestones || []).length}</p></div>
      </div>

      {/* Milestones + certificates */}
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <p className="font-head font-semibold text-brand-navy mb-3 flex items-center gap-2"><Award size={17} /> Recognition</p>
        <div className="flex flex-wrap gap-2">
          {(data.milestones_available || [20, 50, 100]).map((ms) => {
            const earned = (s.earned_milestones || []).includes(ms);
            return earned ? (
              <a key={ms} href={`${API}/members/${data.member_id}/certificate/${ms}.pdf`} target="_blank" rel="noreferrer" data-testid={`cert-${ms}`}>
                <Button size="sm" variant="outline" className="text-emerald-700 border-emerald-200"><Download size={14} className="mr-1" /> {ms}h Certificate</Button>
              </a>
            ) : <span key={ms} className="text-xs px-3 py-2 rounded-full bg-slate-100 text-slate-400">{ms}h locked</span>;
          })}
        </div>
      </div>

      {/* Clock */}
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        {active ? (
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div><p className="text-sm text-blue-600 font-medium flex items-center gap-1"><Clock size={15} /> Clocked in since {new Date(active.clock_in).toLocaleTimeString()}</p><p className="text-xs text-slate-400">{active.category || active.activity_type}</p></div>
            <Button onClick={clockOut} data-testid="clock-out-btn" className="bg-rose-600 hover:bg-rose-700"><Square size={15} className="mr-1" /> Clock Out</Button>
          </div>
        ) : (
          <div className="grid sm:grid-cols-4 gap-2 items-end">
            <div><Label className="text-xs">Activity</Label><select value={clockForm.activity_type} onChange={(e) => setClockForm({ ...clockForm, activity_type: e.target.value })} data-testid="clock-activity" className="w-full h-10 rounded-md border border-input px-2 text-sm">{ACTIVITY.map((a) => <option key={a} value={a}>{a}</option>)}</select></div>
            <div><Label className="text-xs">Project / Committee</Label><Input value={clockForm.category} onChange={(e) => setClockForm({ ...clockForm, category: e.target.value })} data-testid="clock-category" /></div>
            <div className="sm:col-span-1"><Label className="text-xs">Notes</Label><Input value={clockForm.description} onChange={(e) => setClockForm({ ...clockForm, description: e.target.value })} data-testid="clock-notes" /></div>
            <div className="flex gap-2"><Button onClick={clockIn} data-testid="clock-in-btn" className="bg-emerald-600 hover:bg-emerald-700 flex-1"><Play size={15} className="mr-1" /> Clock In</Button><Button variant="outline" onClick={() => setManual(true)} data-testid="add-manual-btn"><Plus size={15} /></Button></div>
          </div>
        )}
      </div>

      {/* History */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-xs uppercase"><tr><th className="text-left p-3">Date</th><th className="text-left p-3">Activity</th><th className="text-left p-3">Hours</th><th className="text-left p-3">Status</th><th className="text-right p-3"></th></tr></thead>
          <tbody>
            {data.entries.length === 0 ? <tr><td colSpan={5} className="p-6 text-center text-slate-400">No hours logged yet.</td></tr> : data.entries.map((e) => (
              <tr key={e.id} className="border-t border-slate-100" data-testid={`hours-row-${e.id}`}>
                <td className="p-3">{e.date}</td>
                <td className="p-3">{e.category || e.activity_type}{e.event_name ? ` · ${e.event_name}` : ""}{e.description ? <span className="block text-xs text-slate-400">{e.description}</span> : null}</td>
                <td className="p-3 font-mono-data">{e.hours}</td>
                <td className="p-3"><StatusPill s={e.status} /></td>
                <td className="p-3 text-right">{["pending", "active"].includes(e.status) && <button onClick={() => remove(e.id)} data-testid={`delete-hours-${e.id}`} className="text-slate-400 hover:text-rose-500"><X size={15} /></button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={manual} onOpenChange={setManual}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Submit hours manually</DialogTitle><DialogDescription>For approved remote or off-site activity.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Date</Label><Input type="date" value={mForm.date} onChange={(e) => setMForm({ ...mForm, date: e.target.value })} data-testid="manual-date" /></div>
              <div><Label className="text-xs">Hours</Label><Input type="number" step="0.25" value={mForm.hours} onChange={(e) => setMForm({ ...mForm, hours: e.target.value })} data-testid="manual-hours" /></div>
            </div>
            <div><Label className="text-xs">Activity</Label><select value={mForm.activity_type} onChange={(e) => setMForm({ ...mForm, activity_type: e.target.value })} className="w-full h-10 rounded-md border border-input px-2 text-sm">{ACTIVITY.map((a) => <option key={a} value={a}>{a}</option>)}</select></div>
            <div><Label className="text-xs">Project / Committee / Activity</Label><Input value={mForm.category} onChange={(e) => setMForm({ ...mForm, category: e.target.value })} data-testid="manual-category" /></div>
            <div><Label className="text-xs">Description</Label><Textarea rows={3} value={mForm.description} onChange={(e) => setMForm({ ...mForm, description: e.target.value })} data-testid="manual-desc" /></div>
          </div>
          <DialogFooter><Button onClick={submitManual} data-testid="manual-submit-btn" className="bg-brand-magenta hover:bg-brand-pink">Submit for review</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// ---------- Admin view ----------
const AdminHours = () => {
  const [tab, setTab] = useState("pending");
  const [data, setData] = useState(null);
  const [summary, setSummary] = useState([]);
  const [month, setMonth] = useState("");
  const [edit, setEdit] = useState(null);

  const load = useCallback(() => {
    const p = new URLSearchParams({ status: tab });
    if (month) p.set("month", month);
    setData(null);
    api.get(`/service-hours?${p}`).then((r) => setData(r.data)).catch(() => setData({ entries: [], counts: {}, totals: {} }));
  }, [tab, month]);
  const loadSummary = useCallback(() => { const p = month ? `?month=${month}` : ""; api.get(`/service-hours/summary${p}`).then((r) => setSummary(r.data.rows)).catch(() => {}); }, [month]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadSummary(); }, [loadSummary]);

  const act = async (id, status) => { try { await api.put(`/service-hours/${id}/status`, { status }); toast.success(status); load(); loadSummary(); } catch { toast.error("Failed"); } };
  const saveEdit = async () => { try { await api.put(`/service-hours/${edit.id}`, { hours: Number(edit.hours), description: edit.description, category: edit.category }); toast.success("Updated"); setEdit(null); load(); loadSummary(); } catch { toast.error("Failed"); } };
  const exportCsv = () => { const p = new URLSearchParams(); if (tab) p.set("status", tab); if (month) p.set("month", month); window.open(`${API}/service-hours/export.csv?${p}`, "_blank"); };

  return (
    <div className="space-y-5" data-testid="admin-hours">
      <div className="flex flex-wrap items-center gap-2">
        {["pending", "approved", "rejected", "active"].map((k) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`hours-tab-${k}`} className={`px-3 py-1.5 rounded-full text-sm font-medium ${tab === k ? "bg-brand-magenta text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {k}{data?.counts?.[k] != null && <span className="ml-1.5 opacity-80">({data.counts[k]})</span>}
          </button>
        ))}
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} data-testid="hours-month" className="ml-auto rounded-md border border-input px-3 py-1.5 text-sm" />
        <Button variant="outline" size="sm" onClick={exportCsv} data-testid="hours-export"><FileDown size={14} className="mr-1" /> Export CSV</Button>
      </div>

      {/* Totals by volunteer */}
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <p className="font-head font-semibold text-brand-navy mb-2 text-sm">Total hours by volunteer{month ? ` · ${month}` : ""}</p>
        {summary.length === 0 ? <p className="text-sm text-slate-400">No hours yet.</p> : (
          <div className="flex flex-wrap gap-2" data-testid="hours-summary">
            {summary.map((r) => (
              <div key={r.member_id} className="px-3 py-2 rounded-lg bg-slate-50 text-sm"><span className="font-medium text-brand-navy">{r.member_name}</span> <span className="text-emerald-600 font-mono-data">{r.approved}h</span>{r.pending > 0 && <span className="text-amber-500 font-mono-data"> +{r.pending}p</span>}</div>
            ))}
          </div>
        )}
      </div>

      {/* Entries */}
      {data === null ? <Loading /> : data.entries.length === 0 ? <EmptyState icon={Clock} title="No hours here" /> : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase"><tr><th className="text-left p-3">Date</th><th className="text-left p-3">Volunteer</th><th className="text-left p-3">Activity</th><th className="text-left p-3">Hours</th><th className="text-right p-3">Actions</th></tr></thead>
            <tbody>
              {data.entries.map((e) => (
                <tr key={e.id} className="border-t border-slate-100" data-testid={`admin-hours-row-${e.id}`}>
                  <td className="p-3">{e.date}</td>
                  <td className="p-3 font-medium text-slate-800">{e.member_name}<span className="block text-xs text-slate-400">{e.role}</span></td>
                  <td className="p-3">{e.category || e.activity_type}{e.event_name ? ` · ${e.event_name}` : ""}{e.description ? <span className="block text-xs text-slate-400">{e.description}</span> : null}</td>
                  <td className="p-3 font-mono-data">{e.hours}</td>
                  <td className="p-3">
                    <div className="flex items-center justify-end gap-1">
                      {e.status !== "approved" && <Button size="sm" onClick={() => act(e.id, "approved")} data-testid={`approve-hours-${e.id}`} className="h-8 bg-emerald-600 hover:bg-emerald-700"><Check size={14} /></Button>}
                      {e.status !== "rejected" && <Button size="sm" variant="outline" onClick={() => act(e.id, "rejected")} data-testid={`reject-hours-${e.id}`} className="h-8 text-rose-600 border-rose-200"><X size={14} /></Button>}
                      <Button size="sm" variant="ghost" onClick={() => setEdit({ ...e })} data-testid={`edit-hours-${e.id}`} className="h-8 px-2 text-slate-500">Edit</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Edit hours</DialogTitle><DialogDescription>{edit?.member_name}</DialogDescription></DialogHeader>
          {edit && <div className="space-y-3">
            <div><Label className="text-xs">Hours</Label><Input type="number" step="0.25" value={edit.hours} onChange={(e) => setEdit({ ...edit, hours: e.target.value })} data-testid="edit-hours-input" /></div>
            <div><Label className="text-xs">Category</Label><Input value={edit.category || ""} onChange={(e) => setEdit({ ...edit, category: e.target.value })} /></div>
            <div><Label className="text-xs">Description</Label><Textarea rows={3} value={edit.description || ""} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></div>
          </div>}
          <DialogFooter><Button onClick={saveEdit} data-testid="save-hours-edit" className="bg-brand-magenta hover:bg-brand-pink">Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default function ServiceHours() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  return (
    <div className="space-y-6">
      <PageTitle title="Service Hours" subtitle={isStaff ? "Review, approve and report volunteer & intern service hours." : "Track your service hours, submit time, and earn recognition."} />
      {isStaff ? <AdminHours /> : <MemberHours />}
    </div>
  );
}
