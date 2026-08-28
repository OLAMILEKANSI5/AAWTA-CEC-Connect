import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Circle } from "lucide-react";
import { api } from "@/auth";
import { PageTitle, Loading } from "@/components/shared";
import { Progress } from "@/components/ui/progress";

export default function Onboarding() {
  const [m, setM] = useState(null);
  const load = () => api.get("/members/me").then((r) => setM(r.data)).catch(() => setM(false));
  useEffect(() => { load(); }, []);

  const toggle = async (step, done) => { await api.put(`/members/${m.id}/onboarding`, { step, done: !done }); load(); toast.success("Updated"); };

  if (m === null) return <Loading />;
  if (m === false) return <div className="text-slate-500">No member profile linked yet.</div>;
  const done = (m.onboarding || []).filter((o) => o.done).length;
  const total = m.onboarding?.length || 0;
  const pct = total ? Math.round((done / total) * 100) : 0;

  return (
    <div className="space-y-5 max-w-3xl">
      <PageTitle title="Onboarding Center" subtitle="Complete each step to finish your onboarding" />
      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <div className="flex items-center justify-between mb-2"><span className="font-head font-semibold text-brand-navy">Overall progress</span><span className="font-mono-data font-bold text-brand-magenta">{pct}%</span></div>
        <Progress value={pct} className="h-3" />
        <p className="text-sm text-slate-500 mt-2">{done} of {total} steps complete · {total - done} remaining</p>
      </div>
      <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100" data-testid="onboarding-list">
        {(m.onboarding || []).map((o) => (
          <button key={o.step} onClick={() => toggle(o.step, o.done)} data-testid={`onboarding-${o.step.toLowerCase().replace(/[^a-z]/g, "-")}`} className="w-full flex items-center gap-3 p-4 text-left hover:bg-slate-50">
            {o.done ? <CheckCircle2 className="text-emerald-500 shrink-0" size={22} /> : <Circle className="text-slate-300 shrink-0" size={22} />}
            <span className={`font-medium ${o.done ? "text-slate-800 line-through" : "text-slate-700"}`}>{o.step}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
