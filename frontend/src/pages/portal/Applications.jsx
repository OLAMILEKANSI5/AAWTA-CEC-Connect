import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search, FileText } from "lucide-react";
import { api } from "@/auth";
import { PageTitle, StatusBadge, Loading, EmptyState } from "@/components/shared";
import { Input } from "@/components/ui/input";
import { APP_STATUSES } from "@/lib/constants";

export default function Applications() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [apps, setApps] = useState(null);
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState(params.get("status") || "");

  const load = () => {
    const p = new URLSearchParams();
    if (q) p.set("q", q); if (type) p.set("type", type); if (status) p.set("status", status);
    api.get(`/applications?${p.toString()}`).then((r) => setApps(r.data)).catch(() => setApps([]));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [q, type, status]);

  return (
    <div className="space-y-5">
      <PageTitle title="Applications & Inquiries" subtitle="Review, filter, and process all submissions" />
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input data-testid="app-search" placeholder="Search name, email, ref…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
        <select data-testid="app-filter-type" value={type} onChange={(e) => setType(e.target.value)} className="rounded-md border border-input px-3 text-sm bg-background">
          <option value="">All Types</option><option value="ambassador">Ambassador</option><option value="volunteer">Volunteer</option><option value="inquiry">Inquiry</option>
        </select>
        <select data-testid="app-filter-status" value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-md border border-input px-3 text-sm bg-background">
          <option value="">All Statuses</option>{APP_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      {apps === null ? <Loading /> : apps.length === 0 ? <EmptyState icon={FileText} title="No applications found" /> : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
          <table className="w-full text-sm" data-testid="applications-table">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase"><tr>
              <th className="text-left p-3">Ref</th><th className="text-left p-3">Name</th><th className="text-left p-3">Type</th><th className="text-left p-3">State</th><th className="text-left p-3">Status</th><th className="text-left p-3">Submitted</th>
            </tr></thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.id} onClick={() => navigate(`/portal/applications/${a.id}`)} data-testid={`app-row-${a.id}`} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer">
                  <td className="p-3 font-mono-data text-xs text-brand-magenta">{a.ref}{a.possible_duplicate && <span className="ml-1 text-amber-500" title="Possible duplicate">⚠</span>}</td>
                  <td className="p-3 font-medium text-slate-800">{a.name}<div className="text-xs text-slate-400">{a.email}</div></td>
                  <td className="p-3 capitalize">{a.type}</td>
                  <td className="p-3">{a.state || "—"}</td>
                  <td className="p-3"><StatusBadge status={a.status} /></td>
                  <td className="p-3 text-slate-400 text-xs">{new Date(a.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
