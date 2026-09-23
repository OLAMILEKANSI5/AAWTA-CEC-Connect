import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { AlertTriangle, ArrowRight, Send, ExternalLink, Clock } from "lucide-react";
import { api } from "@/auth";
import { PageTitle, Loading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STAGE_STYLES = {
  applied: "bg-slate-100 text-slate-600", under_review: "bg-amber-100 text-amber-700",
  approved: "bg-blue-100 text-blue-700", profile_incomplete: "bg-orange-100 text-orange-700",
  docs_needed: "bg-purple-100 text-purple-700", thirty_day: "bg-teal-100 text-teal-700",
  fully_onboarded: "bg-emerald-100 text-emerald-700",
};
const ROLE_LABEL = { ambassador: "Ambassador", volunteer: "Volunteer" };

export default function OnboardingDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [role, setRole] = useState("");
  const [stage, setStage] = useState("");
  const [templates, setTemplates] = useState([]);
  const [remind, setRemind] = useState(null); // entry being reminded
  const [rForm, setRForm] = useState({ template_key: "onboarding_reminder", subject: "", body: "", channel: "both", include_button: false, button_label: "" });
  const [sending, setSending] = useState(false);

  const load = useCallback(() => {
    const p = new URLSearchParams();
    if (role) p.set("role", role);
    if (stage) p.set("stage", stage);
    api.get(`/onboarding/pipeline?${p.toString()}`).then((r) => setData(r.data)).catch(() => toast.error("Failed to load"));
  }, [role, stage]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/notification-templates").then((r) => setTemplates(r.data.templates || [])).catch(() => {}); }, []);

  const openRemind = async (entry) => {
    setRemind(entry);
    const key = entry.kind === "member" ? "onboarding_reminder" : "application_received";
    try {
      const r = await api.post("/comms/preview", { subject_type: entry.kind, subject_id: entry.id, template_key: key });
      setRForm({ template_key: key, subject: r.data.subject, body: r.data.body, channel: "both", include_button: r.data.include_button, button_label: r.data.button_label });
    } catch { setRForm({ template_key: "", subject: "", body: "", channel: "both", include_button: false, button_label: "" }); }
  };

  const pickTemplate = async (key) => {
    if (!key) { setRForm((f) => ({ ...f, template_key: "" })); return; }
    try {
      const r = await api.post("/comms/preview", { subject_type: remind.kind, subject_id: remind.id, template_key: key });
      setRForm((f) => ({ ...f, template_key: key, subject: r.data.subject, body: r.data.body, include_button: r.data.include_button, button_label: r.data.button_label }));
    } catch { toast.error("Could not load template"); }
  };

  const sendReminder = async () => {
    if (!rForm.subject.trim() || !rForm.body.trim()) { toast.error("Subject and message required"); return; }
    setSending(true);
    try {
      await api.post("/comms/send", { subject_type: remind.kind, subject_id: remind.id, ...rForm });
      toast.success("Reminder sent");
      setRemind(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to send"); }
    finally { setSending(false); }
  };

  if (!data) return <Loading />;
  const order = data.stage_order;
  const labels = data.stage_labels;

  return (
    <div className="space-y-6" data-testid="onboarding-dashboard">
      <PageTitle title="Onboarding Dashboard" subtitle="Track every Ambassador and Volunteer from application through full onboarding." />

      {/* Funnel */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
        {order.map((s) => (
          <button key={s} onClick={() => setStage(stage === s ? "" : s)} data-testid={`funnel-${s}`}
            className={`text-left p-3 rounded-xl border transition-colors ${stage === s ? "border-brand-magenta ring-1 ring-brand-magenta" : "border-slate-200"} bg-white hover:border-brand-magenta`}>
            <div className="text-2xl font-bold text-brand-navy font-mono-data">{data.counts[s] ?? 0}</div>
            <div className="text-[11px] text-slate-500 leading-tight mt-1">{labels[s]}</div>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <select data-testid="role-filter" value={role} onChange={(e) => setRole(e.target.value)} className="rounded-md border border-input px-3 py-2 text-sm bg-background">
          <option value="">All roles</option><option value="ambassador">Ambassadors</option><option value="volunteer">Volunteers</option>
        </select>
        <select data-testid="stage-filter" value={stage} onChange={(e) => setStage(e.target.value)} className="rounded-md border border-input px-3 py-2 text-sm bg-background">
          <option value="">All stages</option>{order.map((s) => <option key={s} value={s}>{labels[s]}</option>)}
        </select>
        {(role || stage) && <Button variant="ghost" size="sm" onClick={() => { setRole(""); setStage(""); }}>Clear</Button>}
        <span className="text-sm text-slate-400 ml-auto">{data.entries.length} shown</span>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-xs uppercase"><tr>
            <th className="text-left p-3">Name</th><th className="text-left p-3">Role</th><th className="text-left p-3">Stage</th>
            <th className="text-left p-3">Outstanding</th><th className="text-left p-3">Approved</th><th className="text-left p-3">In stage</th>
            <th className="text-left p-3">30-day</th><th className="text-right p-3">Actions</th>
          </tr></thead>
          <tbody>
            {data.entries.length === 0 ? (
              <tr><td colSpan={8} className="p-6 text-center text-slate-400">No one in this view.</td></tr>
            ) : data.entries.map((e) => (
              <tr key={`${e.kind}-${e.id}`} data-testid={`pipeline-row-${e.id}`} className={`border-t border-slate-100 ${e.stalled ? "bg-rose-50/50" : ""}`}>
                <td className="p-3 font-medium text-slate-800">{e.name}<div className="text-xs text-slate-400">{e.email}</div></td>
                <td className="p-3">{ROLE_LABEL[e.role] || e.role}</td>
                <td className="p-3"><span className={`text-[11px] px-2 py-0.5 rounded-full ${STAGE_STYLES[e.stage]}`}>{e.stage_label}</span></td>
                <td className="p-3 text-xs text-slate-600 max-w-[220px]">
                  {e.outstanding?.length ? <ul className="space-y-0.5">{e.outstanding.slice(0, 3).map((o, i) => <li key={i}>• {o}</li>)}{e.outstanding.length > 3 && <li className="text-slate-400">+{e.outstanding.length - 3} more</li>}</ul> : <span className="text-slate-300">—</span>}
                </td>
                <td className="p-3 text-xs text-slate-500">{e.approved_at ? new Date(e.approved_at).toLocaleDateString() : "—"}</td>
                <td className="p-3">
                  <span className={`inline-flex items-center gap-1 text-xs ${e.stalled ? "text-rose-600 font-semibold" : "text-slate-500"}`}>
                    {e.stalled && <AlertTriangle size={13} />}<Clock size={12} /> {e.days_in_stage}d
                  </span>
                </td>
                <td className="p-3 w-28">{e.progress_pct != null ? <div className="flex items-center gap-2"><Progress value={e.progress_pct} className="h-1.5 w-16" /><span className="text-xs text-slate-500">{e.progress_pct}%</span></div> : <span className="text-slate-300 text-xs">—</span>}</td>
                <td className="p-3">
                  <div className="flex items-center justify-end gap-1">
                    <Button size="sm" variant="outline" onClick={() => navigate(e.link)} data-testid={`open-profile-${e.id}`} className="h-8 px-2"><ExternalLink size={14} /></Button>
                    <Button size="sm" onClick={() => openRemind(e)} data-testid={`remind-${e.id}`} className="h-8 px-2 bg-brand-magenta hover:bg-brand-pink"><Send size={14} /></Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Reminder dialog */}
      <Dialog open={!!remind} onOpenChange={(o) => !o && setRemind(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Send a reminder</DialogTitle><DialogDescription>{remind?.name} · {remind && labels[remind.stage]}</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Template</Label>
              <Select value={rForm.template_key || "none"} onValueChange={(v) => pickTemplate(v === "none" ? "" : v)}>
                <SelectTrigger data-testid="reminder-template-select"><SelectValue placeholder="Custom" /></SelectTrigger>
                <SelectContent><SelectItem value="none">Custom message</SelectItem>{templates.map((t) => <SelectItem key={t.key} value={t.key}>{t.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Subject</Label><Input value={rForm.subject} onChange={(e) => setRForm({ ...rForm, subject: e.target.value })} data-testid="reminder-subject" /></div>
            <div><Label className="text-xs">Message</Label><Textarea rows={6} value={rForm.body} onChange={(e) => setRForm({ ...rForm, body: e.target.value })} data-testid="reminder-body" /></div>
            <div>
              <Label className="text-xs">Deliver via</Label>
              <Select value={rForm.channel} onValueChange={(v) => setRForm({ ...rForm, channel: v })}>
                <SelectTrigger data-testid="reminder-channel"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="email">Email</SelectItem><SelectItem value="portal">Portal notification</SelectItem><SelectItem value="both">Email + Portal</SelectItem></SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRemind(null)}>Cancel</Button>
            <Button onClick={sendReminder} disabled={sending} data-testid="reminder-send" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Send size={15} className="mr-1" /> {sending ? "Sending…" : "Send"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
