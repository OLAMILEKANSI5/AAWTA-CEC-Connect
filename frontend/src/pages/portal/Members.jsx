import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { UserPlus, Users, Search } from "lucide-react";
import { api } from "@/auth";
import { PageTitle, StatusBadge, Loading, EmptyState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField, MultiChips } from "@/components/FormFields";
import { US_STATES, FOCUS_AREAS, ROLE_LABELS } from "@/lib/constants";

export default function Members() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [members, setMembers] = useState(null);
  const [role, setRole] = useState(params.get("role") || "");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ role: "ambassador", focus_areas: [], send_invite: true });
  const [busy, setBusy] = useState(false);
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => {
    const p = new URLSearchParams(); if (role) p.set("role", role); if (q) p.set("q", q);
    api.get(`/members?${p.toString()}`).then((r) => setMembers(r.data)).catch(() => setMembers([]));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [role, q]);

  const add = async () => {
    if (!f.name || !f.email || !f.login_email) { toast.error("Name, email, and login email required"); return; }
    setBusy(true);
    try { await api.post("/members/manual", f); toast.success("Member added" + (f.send_invite ? " & invited" : "")); setOpen(false); setF({ role: "ambassador", focus_areas: [], send_invite: true }); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(false);
  };

  return (
    <div className="space-y-5">
      <PageTitle title="Members" subtitle="State Ambassadors & Volunteers" action={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="add-member-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><UserPlus size={16} className="mr-1" /> Add Member</Button></DialogTrigger>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>Add Member Manually</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <Field label="Full name" name="name" value={f.name} onChange={on} required />
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Contact email" name="email" type="email" value={f.email} onChange={on} required />
                <Field label="Google login email" name="login_email" type="email" value={f.login_email} onChange={on} required />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <SelectField label="Role" name="role" value={f.role} onChange={on} options={["ambassador", "volunteer"]} required />
                <SelectField label="State" name="state" value={f.state} onChange={on} options={US_STATES} />
                <Field label="Region" name="region" value={f.region} onChange={on} />
                <Field label="Assigned Director" name="assigned_director" value={f.assigned_director} onChange={on} />
              </div>
              <MultiChips label="Focus areas" options={FOCUS_AREAS} value={f.focus_areas} onChange={(v) => on("focus_areas", v)} />
              <Field label="Internal notes" name="internal_notes" value={f.internal_notes} onChange={on} textarea />
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.send_invite} onChange={(e) => on("send_invite", e.target.checked)} className="accent-[#D6189B]" data-testid="send-invite-check" /> Send portal invitation email</label>
            </div>
            <DialogFooter><Button onClick={add} disabled={busy} data-testid="save-member-btn" className="bg-brand-magenta hover:bg-brand-pink">{busy ? "Saving…" : "Add & Invite"}</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      } />

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><Input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" data-testid="member-search" /></div>
        <select value={role} onChange={(e) => setRole(e.target.value)} className="rounded-md border border-input px-3 text-sm bg-background"><option value="">All Roles</option><option value="ambassador">Ambassadors</option><option value="volunteer">Volunteers</option></select>
      </div>

      {members === null ? <Loading /> : members.length === 0 ? <EmptyState icon={Users} title="No members yet" subtitle="Approve applications or add members manually." /> : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {members.map((m) => (
            <div key={m.id} onClick={() => navigate(`/portal/members/${m.id}`)} data-testid={`member-card-${m.id}`} className="bg-white border border-slate-200 rounded-xl p-5 cursor-pointer hover:-translate-y-1 hover:shadow-md transition-all">
              <div className="flex items-start justify-between">
                <div><h3 className="font-head font-bold text-brand-navy">{m.name}</h3><p className="text-xs text-brand-magenta font-semibold">{ROLE_LABELS[m.role]}</p></div>
                <StatusBadge status={m.account_status} />
              </div>
              <p className="text-sm text-slate-500 mt-2">{m.state || "No state"} {m.region ? `· ${m.region}` : ""}</p>
              <p className="text-xs text-slate-400 mt-1">{m.email}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
