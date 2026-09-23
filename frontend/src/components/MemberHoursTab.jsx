import React, { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Check, X, Download, Clock } from "lucide-react";
import { api, API } from "@/auth";
import { Button } from "@/components/ui/button";

const STATUS_STYLES = { pending: "bg-amber-100 text-amber-700", approved: "bg-emerald-100 text-emerald-700", rejected: "bg-rose-100 text-rose-600", active: "bg-blue-100 text-blue-700" };

export const MemberHoursTab = ({ memberId, milestones = [] }) => {
  const [data, setData] = useState(null);
  const load = useCallback(() => api.get(`/service-hours?member_id=${memberId}`).then((r) => setData(r.data)).catch(() => setData({ entries: [], totals: {} })), [memberId]);
  useEffect(() => { load(); }, [load]);
  const act = async (id, status) => { try { await api.put(`/service-hours/${id}/status`, { status }); toast.success(status); load(); } catch { toast.error("Failed"); } };

  if (!data) return <div className="p-5 text-slate-400 text-sm">Loading…</div>;
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4" data-testid="member-hours-tab">
      <div className="flex flex-wrap items-center gap-3">
        <div><p className="text-xs text-slate-400">Approved</p><p className="text-2xl font-bold text-brand-navy font-mono-data">{data.totals?.approved ?? 0}h</p></div>
        <div><p className="text-xs text-slate-400">Pending</p><p className="text-2xl font-bold text-amber-500 font-mono-data">{data.totals?.pending ?? 0}h</p></div>
        <div className="ml-auto flex flex-wrap gap-2">
          {[20, 50, 100].map((ms) => milestones.includes(ms) && (
            <a key={ms} href={`${API}/members/${memberId}/certificate/${ms}.pdf`} target="_blank" rel="noreferrer" data-testid={`member-cert-${ms}`}>
              <Button size="sm" variant="outline" className="text-emerald-700 border-emerald-200"><Download size={13} className="mr-1" /> {ms}h</Button>
            </a>
          ))}
        </div>
      </div>
      {data.entries.length === 0 ? <p className="text-sm text-slate-400 flex items-center gap-2"><Clock size={15} /> No service hours logged.</p> : (
        <div className="space-y-1">
          {data.entries.map((e) => (
            <div key={e.id} className="flex items-center justify-between py-2 border-b border-slate-100 text-sm" data-testid={`member-hours-${e.id}`}>
              <div><p className="font-medium text-slate-800">{e.hours}h · {e.category || e.activity_type}</p><p className="text-xs text-slate-400">{e.date}{e.event_name ? ` · ${e.event_name}` : ""}</p></div>
              <div className="flex items-center gap-1">
                <span className={`text-[11px] px-2 py-0.5 rounded-full ${STATUS_STYLES[e.status]}`}>{e.status}</span>
                {e.status !== "approved" && <Button size="sm" onClick={() => act(e.id, "approved")} data-testid={`mh-approve-${e.id}`} className="h-7 px-2 bg-emerald-600 hover:bg-emerald-700"><Check size={13} /></Button>}
                {e.status !== "rejected" && <Button size="sm" variant="outline" onClick={() => act(e.id, "rejected")} data-testid={`mh-reject-${e.id}`} className="h-7 px-2 text-rose-600 border-rose-200"><X size={13} /></Button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
