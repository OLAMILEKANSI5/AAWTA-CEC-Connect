import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Target, Plus, Clock } from "lucide-react";
import { api, useAuth } from "@/auth";
import { PageTitle, Loading, EmptyState, StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { GOAL_CATEGORIES, GOAL_STATUSES } from "@/lib/constants";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const STAFF = ["super_admin", "director", "administrator"];

export default function Goals() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [goals, setGoals] = useState(null);
  const [reports, setReports] = useState([]);
  const [members, setMembers] = useState([]);
  const [open, setOpen] = useState(false);
  const [repOpen, setRepOpen] = useState(false);
  const [f, setF] = useState({ category: "Community outreach" });
  const [rep, setRep] = useState({});
  const [drag, setDrag] = useState({});
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => { api.get("/goals").then((r) => setGoals(r.data)).catch(() => setGoals([])); api.get("/activity-reports").then((r) => setReports(r.data)).catch(() => {}); };
  useEffect(() => { load(); if (isStaff) api.get("/members").then((r) => setMembers(r.data)).catch(() => {}); }, [isStaff]);

  const create = async () => { if (!f.title) { toast.error("Title required"); return; } try { await api.post("/goals", f); toast.success(isStaff ? "Goal assigned" : "Goal proposed"); setOpen(false); setF({ category: "Community outreach" }); load(); } catch { toast.error("Failed"); } };
  const updateGoal = async (id, upd) => { await api.put(`/goals/${id}`, upd); load(); };
  const submitReport = async () => { if (!rep.month || !rep.summary) { toast.error("Month and summary required"); return; } try { await api.post("/activity-reports", { ...rep, hours: rep.hours ? Number(rep.hours) : null }); toast.success("Report submitted"); setRepOpen(false); setRep({}); load(); } catch { toast.error("Failed"); } };

  return (
    <div className="space-y-5">
      <PageTitle title="Goals & Activity" subtitle="Monthly goals and activity reports" action={
        <div className="flex gap-2">
          {!isStaff && <Dialog open={repOpen} onOpenChange={setRepOpen}>
            <DialogTrigger asChild><Button variant="outline" className="rounded-full" data-testid="new-report-btn"><Plus size={16} className="mr-1" /> Activity Report</Button></DialogTrigger>
            <DialogContent><DialogHeader><DialogTitle>Submit Monthly Activity Report</DialogTitle></DialogHeader>
              <div className="space-y-4"><Field label="Month" name="month" value={rep.month} onChange={(k, v) => setRep((p) => ({ ...p, [k]: v }))} placeholder="e.g. June 2026" required /><Field label="Summary" name="summary" value={rep.summary} onChange={(k, v) => setRep((p) => ({ ...p, [k]: v }))} textarea required /><div className="grid grid-cols-2 gap-3"><Field label="Volunteer hours" name="hours" type="number" value={rep.hours} onChange={(k, v) => setRep((p) => ({ ...p, [k]: v }))} /><Field label="Events supported" name="events_supported" type="number" value={rep.events_supported} onChange={(k, v) => setRep((p) => ({ ...p, [k]: v }))} /></div></div>
              <DialogFooter><Button onClick={submitReport} data-testid="submit-report-btn" className="bg-brand-magenta hover:bg-brand-pink">Submit</Button></DialogFooter>
            </DialogContent>
          </Dialog>}
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button data-testid="new-goal-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> {isStaff ? "Assign Goal" : "Propose Goal"}</Button></DialogTrigger>
            <DialogContent><DialogHeader><DialogTitle>{isStaff ? "Assign Goal" : "Propose a Goal"}</DialogTitle></DialogHeader>
              <div className="space-y-4">
                <Field label="Goal title" name="title" value={f.title} onChange={on} required />
                <Field label="Description" name="description" value={f.description} onChange={on} textarea />
                <div className="grid grid-cols-2 gap-3"><SelectField label="Category" name="category" value={f.category} onChange={on} options={GOAL_CATEGORIES} /><Field label="Target" name="target" value={f.target} onChange={on} /></div>
                <Field label="Due date" name="due_date" type="date" value={f.due_date} onChange={on} />
                {isStaff && <select value={f.member_id || ""} onChange={(e) => on("member_id", e.target.value)} className="w-full rounded-md border border-input px-3 py-2 text-sm" data-testid="goal-member-select"><option value="">Select member…</option>{members.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.role})</option>)}</select>}
              </div>
              <DialogFooter><Button onClick={create} data-testid="save-goal-btn" className="bg-brand-magenta hover:bg-brand-pink">{isStaff ? "Assign" : "Propose"}</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      } />

      <Tabs defaultValue="goals">
        <TabsList><TabsTrigger value="goals">Goals</TabsTrigger><TabsTrigger value="reports">Activity Reports ({reports.length})</TabsTrigger></TabsList>
        <TabsContent value="goals">
          {goals === null ? <Loading /> : goals.length === 0 ? <EmptyState icon={Target} title="No goals yet" /> : (
            <div className="grid md:grid-cols-2 gap-4">{goals.map((g) => (
              <div key={g.id} className="bg-white border border-slate-200 rounded-xl p-5" data-testid={`goal-${g.id}`}>
                <div className="flex items-start justify-between"><div><p className="font-head font-semibold text-brand-navy">{g.title}</p><p className="text-xs text-slate-400">{g.category}{g.target ? ` · Target: ${g.target}` : ""}</p></div><StatusBadge status={g.status} /></div>
                {g.description && <p className="text-sm text-slate-600 mt-2">{g.description}</p>}
                <div className="mt-3"><Progress value={g.progress || 0} className="h-2" /><p className="text-xs text-slate-400 mt-1">{g.progress || 0}% complete{g.due_date ? ` · due ${new Date(g.due_date).toLocaleDateString()}` : ""}</p></div>
                <div className="flex items-center gap-2 mt-3">
                  <input type="range" min="0" max="100" value={drag[g.id] ?? g.progress ?? 0} onChange={(e) => setDrag((p) => ({ ...p, [g.id]: Number(e.target.value) }))} onMouseUp={(e) => updateGoal(g.id, { progress: Number(e.target.value) })} onTouchEnd={(e) => updateGoal(g.id, { progress: Number(e.target.value) })} className="flex-1 accent-[#D6189B]" data-testid={`goal-progress-${g.id}`} />
                  <select value={g.status} onChange={(e) => updateGoal(g.id, { status: e.target.value })} className="rounded-md border border-input px-2 py-1 text-xs" data-testid={`goal-status-${g.id}`}>{GOAL_STATUSES.map((s) => <option key={s}>{s}</option>)}</select>
                </div>
              </div>
            ))}</div>
          )}
        </TabsContent>
        <TabsContent value="reports">
          {reports.length === 0 ? <EmptyState icon={Clock} title="No activity reports" /> : (
            <div className="space-y-3">{reports.map((r) => (<div key={r.id} className="bg-white border border-slate-200 rounded-xl p-4"><div className="flex justify-between"><p className="font-medium text-slate-800">{r.member_name} · {r.month}</p><span className="text-xs text-slate-400">{r.hours ? `${r.hours} hrs` : ""}</span></div><p className="text-sm text-slate-600 mt-1">{r.summary}</p></div>))}</div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
