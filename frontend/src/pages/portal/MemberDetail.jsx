import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Clock } from "lucide-react";
import { api } from "@/auth";
import { PageTitle, StatusBadge, Loading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ROLE_LABELS } from "@/lib/constants";

export default function MemberDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [m, setM] = useState(null);
  const [goals, setGoals] = useState([]);

  const load = () => api.get(`/members/${id}`).then((r) => setM(r.data)).catch(() => toast.error("Not found"));
  useEffect(() => { load(); api.get(`/goals?member_id=${id}`).then((r) => setGoals(r.data)).catch(() => {}); /* eslint-disable-next-line */ }, [id]);

  const setStatus = async (status) => { await api.put(`/members/${id}/status`, { status }); toast.success(`Account ${status}`); load(); };
  const togglePublic = async () => { await api.put(`/members/${id}`, { public_profile: !m.public_profile }); toast.success("Directory visibility updated"); load(); };

  if (!m) return <Loading />;
  const done = (m.onboarding || []).filter((o) => o.done).length;
  const pct = m.onboarding?.length ? Math.round((done / m.onboarding.length) * 100) : 0;

  return (
    <div className="space-y-5">
      <Button variant="ghost" onClick={() => navigate("/portal/members")} className="text-slate-500"><ArrowLeft size={16} className="mr-1" /> Back</Button>
      <PageTitle title={m.name} subtitle={`${ROLE_LABELS[m.role]} · ${m.state || "No state"}`} action={<StatusBadge status={m.account_status} />} />

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-5">
          <Tabs defaultValue="profile">
            <TabsList><TabsTrigger value="profile">Profile</TabsTrigger><TabsTrigger value="onboarding">Onboarding</TabsTrigger><TabsTrigger value="goals">Goals</TabsTrigger><TabsTrigger value="timeline">Timeline</TabsTrigger></TabsList>
            <TabsContent value="profile">
              <div className="bg-white border border-slate-200 rounded-xl p-5 grid sm:grid-cols-2 gap-x-6 gap-y-3">
                {[["Email", m.email], ["Login email", m.login_email], ["Phone", m.phone], ["City", m.city], ["County", m.county], ["Company", m.company], ["Job title", m.job_title], ["Region", m.region], ["Assigned Director", m.assigned_director], ["Membership", m.membership_status], ["Start date", m.start_date && new Date(m.start_date).toLocaleDateString()]].map(([k, v]) => (
                  <div key={k}><div className="text-xs uppercase text-slate-400">{k}</div><div className="text-sm text-slate-800">{v || "—"}</div></div>
                ))}
                <div className="sm:col-span-2"><div className="text-xs uppercase text-slate-400">Bio</div><div className="text-sm text-slate-800">{m.bio || "—"}</div></div>
                {m.focus_areas?.length > 0 && <div className="sm:col-span-2"><div className="text-xs uppercase text-slate-400 mb-1">Focus areas</div><div className="flex flex-wrap gap-1.5">{m.focus_areas.map((f) => <span key={f} className="text-xs px-2 py-0.5 bg-brand-magenta/10 text-brand-magenta rounded-full">{f}</span>)}</div></div>}
                {m.internal_notes && <div className="sm:col-span-2 bg-amber-50 p-3 rounded-lg"><div className="text-xs uppercase text-amber-600">Internal notes</div><div className="text-sm text-slate-700">{m.internal_notes}</div></div>}
              </div>
            </TabsContent>
            <TabsContent value="onboarding">
              <div className="bg-white border border-slate-200 rounded-xl p-5">
                <div className="flex items-center justify-between mb-2"><span className="font-head font-semibold text-brand-navy">Progress</span><span className="font-mono-data text-brand-magenta font-bold">{pct}%</span></div>
                <Progress value={pct} className="h-2 mb-4" />
                {(m.onboarding || []).map((o) => (<div key={o.step} className="flex items-center gap-2 py-1.5 text-sm"><span className={`h-2 w-2 rounded-full ${o.done ? "bg-emerald-500" : "bg-slate-300"}`} /><span className={o.done ? "text-slate-800" : "text-slate-400"}>{o.step}</span></div>))}
              </div>
            </TabsContent>
            <TabsContent value="goals">
              <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-2">
                {goals.length ? goals.map((g) => (<div key={g.id} className="flex items-center justify-between p-2.5 border-b last:border-0 border-slate-100"><div><p className="text-sm font-medium">{g.title}</p><p className="text-xs text-slate-400">{g.category}</p></div><StatusBadge status={g.status} /></div>)) : <p className="text-sm text-slate-400">No goals assigned</p>}
              </div>
            </TabsContent>
            <TabsContent value="timeline">
              <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
                {m.timeline?.map((t) => (<div key={t.id} className="flex gap-3"><Clock size={16} className="text-brand-magenta shrink-0 mt-0.5" /><div><p className="text-sm text-slate-700">{t.event}</p><p className="text-xs text-slate-400">{t.actor} · {new Date(t.created_at).toLocaleString()}</p></div></div>))}
              </div>
            </TabsContent>
          </Tabs>
        </div>
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
            <h3 className="font-head font-semibold text-brand-navy">Account Actions</h3>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={m.public_profile} onChange={togglePublic} className="accent-[#D6189B]" data-testid="public-profile-toggle" /> Show in public directory</label>
            <div className="flex flex-col gap-2 pt-2">
              {m.account_status === "active" ? <Button variant="outline" onClick={() => setStatus("suspended")} className="text-rose-600 border-rose-200" data-testid="suspend-btn">Suspend Account</Button> : <Button variant="outline" onClick={() => setStatus("active")} className="text-emerald-600 border-emerald-200" data-testid="restore-btn">Restore Account</Button>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
