import React, { useState } from "react";
import { toast } from "sonner";
import { MessageSquarePlus, History, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/auth";
import { StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { GOAL_STATUSES } from "@/lib/constants";

const fmt = (d) => new Date(d).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export const GoalCard = ({ goal: g, onChange, canEdit = true }) => {
  const [drag, setDrag] = useState(g.progress ?? 0);
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [form, setForm] = useState({ status: g.status, progress: g.progress ?? 0, note: "" });
  const notes = [...(g.notes || [])].reverse();
  const history = g.history || [];

  const quick = async (upd) => { try { await api.put(`/goals/${g.id}`, upd); onChange?.(); } catch { toast.error("Update failed"); } };

  const openDialog = () => { setForm({ status: g.status, progress: g.progress ?? 0, note: "" }); setOpen(true); };

  const submit = async () => {
    if (!form.note.trim() && form.status === g.status && Number(form.progress) === (g.progress ?? 0)) {
      toast.error("Add a note or change status/progress"); return;
    }
    try {
      await api.post(`/goals/${g.id}/notes`, { note: form.note, status: form.status, progress: Number(form.progress) });
      toast.success("Progress note saved");
      setOpen(false); onChange?.();
    } catch { toast.error("Failed to save note"); }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5" data-testid={`goal-${g.id}`}>
      <div className="flex items-start justify-between gap-3">
        <div><p className="font-head font-semibold text-brand-navy">{g.title}</p><p className="text-xs text-slate-400">{g.category}{g.target ? ` · Target: ${g.target}` : ""}</p></div>
        <StatusBadge status={g.status} />
      </div>
      {g.description && <p className="text-sm text-slate-600 mt-2">{g.description}</p>}
      <div className="mt-3"><Progress value={g.progress || 0} className="h-2" /><p className="text-xs text-slate-400 mt-1">{g.progress || 0}% complete{g.due_date ? ` · due ${new Date(g.due_date).toLocaleDateString()}` : ""}</p></div>

      {canEdit && (
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          <input type="range" min="0" max="100" value={drag} onChange={(e) => setDrag(Number(e.target.value))} onMouseUp={(e) => quick({ progress: Number(e.target.value) })} onTouchEnd={(e) => quick({ progress: Number(e.target.value) })} className="flex-1 min-w-[120px] accent-[#D6189B]" data-testid={`goal-progress-${g.id}`} />
          <select value={g.status} onChange={(e) => quick({ status: e.target.value })} className="rounded-md border border-input px-2 py-1 text-xs" data-testid={`goal-status-${g.id}`}>{GOAL_STATUSES.map((s) => <option key={s}>{s}</option>)}</select>
        </div>
      )}

      <div className="flex items-center gap-2 mt-3">
        {canEdit && <Button size="sm" variant="outline" onClick={openDialog} className="rounded-full text-xs" data-testid={`goal-add-note-${g.id}`}><MessageSquarePlus size={14} className="mr-1" /> Update / Add Note</Button>}
        <Button size="sm" variant="ghost" onClick={() => setExpanded((v) => !v)} className="rounded-full text-xs text-slate-500" data-testid={`goal-toggle-history-${g.id}`}>
          <History size={14} className="mr-1" /> Notes & History ({notes.length}){expanded ? <ChevronUp size={14} className="ml-1" /> : <ChevronDown size={14} className="ml-1" />}
        </Button>
      </div>

      {expanded && (
        <div className="mt-3 space-y-4" data-testid={`goal-history-panel-${g.id}`}>
          <div>
            <p className="text-xs font-semibold uppercase text-slate-400 mb-2">Progress Notes</p>
            {notes.length ? (
              <div className="space-y-2">{notes.map((n) => (
                <div key={n.id} className="bg-slate-50 rounded-lg p-3" data-testid={`goal-note-${n.id}`}>
                  <p className="text-sm text-slate-700">{n.text}</p>
                  <p className="text-xs text-slate-400 mt-1">{n.author_name} · {fmt(n.created_at)}{n.status ? ` · ${n.status} · ${n.progress}%` : ""}</p>
                </div>
              ))}</div>
            ) : <p className="text-sm text-slate-400">No notes yet.</p>}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-slate-400 mb-2">Activity History</p>
            <div className="space-y-1.5">{history.map((h) => (
              <div key={h.id} className="flex gap-2 text-xs text-slate-500"><span className="text-brand-magenta font-medium shrink-0">{new Date(h.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span><span>— {h.event}{h.actor ? ` · ${h.actor}` : ""}</span></div>
            ))}</div>
          </div>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent><DialogHeader><DialogTitle>Update Goal · {g.title}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <SelectField label="Status" name="status" value={form.status} onChange={(k, v) => setForm((p) => ({ ...p, status: v }))} options={GOAL_STATUSES} />
              <Field label="Progress %" name="progress" type="number" value={form.progress} onChange={(k, v) => setForm((p) => ({ ...p, progress: v }))} />
            </div>
            <Field label="Progress note (why is it at this status?)" name="note" value={form.note} onChange={(k, v) => setForm((p) => ({ ...p, note: v }))} textarea placeholder="e.g. Waiting for confirmation from the community partner before scheduling the outreach event." />
          </div>
          <DialogFooter><Button onClick={submit} data-testid={`goal-save-note-${g.id}`} className="bg-brand-magenta hover:bg-brand-pink">Save Note</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
