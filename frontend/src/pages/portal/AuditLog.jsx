import React, { useEffect, useState } from "react";
import { Search, ScrollText } from "lucide-react";
import { api } from "@/auth";
import { PageTitle, Loading, EmptyState } from "@/components/shared";
import { Input } from "@/components/ui/input";

export default function AuditLog() {
  const [logs, setLogs] = useState(null);
  const [q, setQ] = useState("");
  useEffect(() => { const t = setTimeout(() => api.get(`/audit-logs${q ? `?q=${q}` : ""}`).then((r) => setLogs(r.data)).catch(() => setLogs([])), 300); return () => clearTimeout(t); }, [q]);

  return (
    <div className="space-y-5">
      <PageTitle title="Audit Log" subtitle="Complete record of system activity" />
      <div className="relative max-w-md"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><Input placeholder="Search actions or users…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" data-testid="audit-search" /></div>
      {logs === null ? <Loading /> : logs.length === 0 ? <EmptyState icon={ScrollText} title="No audit entries" /> : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
          <table className="w-full text-sm font-mono-data"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="text-left p-3">Time</th><th className="text-left p-3">User</th><th className="text-left p-3">Action</th><th className="text-left p-3">Record</th></tr></thead>
            <tbody>{logs.map((l) => (<tr key={l.id} className="border-t border-slate-100"><td className="p-3 text-slate-400 text-xs">{new Date(l.created_at).toLocaleString()}</td><td className="p-3 text-slate-700">{l.user_name || l.user_email}</td><td className="p-3 text-brand-magenta">{l.action}</td><td className="p-3 text-slate-500 text-xs">{l.related_type || "—"}</td></tr>))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
