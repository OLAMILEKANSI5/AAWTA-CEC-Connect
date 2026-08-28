import React, { useState } from "react";
import { toast } from "sonner";
import { BarChart3, Download, FileText } from "lucide-react";
import { api, API } from "@/auth";
import { PageTitle } from "@/components/shared";
import { Button } from "@/components/ui/button";

const REPORTS = [
  { key: "applications", label: "Applications", desc: "All applications & inquiries" },
  { key: "ambassadors", label: "Ambassadors by State", desc: "Active State Ambassadors" },
  { key: "volunteers", label: "Volunteers", desc: "All volunteers" },
  { key: "goals", label: "Monthly Goals", desc: "Goal progress & status" },
  { key: "volunteer_hours", label: "Volunteer Hours", desc: "Activity report hours" },
  { key: "events", label: "Events & Attendance", desc: "All events" },
];

export default function Reports() {
  const [preview, setPreview] = useState(null);
  const [active, setActive] = useState(null);

  const view = async (key) => {
    setActive(key);
    try { const { data } = await api.get(`/reports/${key}`); setPreview(data); } catch { toast.error("Failed"); }
  };
  const exportCsv = (key) => { window.open(`${API}/reports/${key}?format=csv`, "_blank"); };
  const exportPdf = (key) => { window.open(`${API}/reports/${key}?format=pdf`, "_blank"); };

  return (
    <div className="space-y-5">
      <PageTitle title="Reports" subtitle="Generate and export data" />
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORTS.map((r) => (
          <div key={r.key} className="bg-white border border-slate-200 rounded-xl p-5" data-testid={`report-${r.key}`}>
            <div className="h-10 w-10 rounded-lg bg-brand-magenta/10 text-brand-magenta flex items-center justify-center mb-3"><BarChart3 size={18} /></div>
            <p className="font-head font-semibold text-brand-navy">{r.label}</p>
            <p className="text-sm text-slate-500 mt-1">{r.desc}</p>
            <div className="flex flex-wrap gap-2 mt-4">
              <Button size="sm" variant="outline" onClick={() => view(r.key)} data-testid={`view-report-${r.key}`}><FileText size={14} className="mr-1" /> Preview</Button>
              <Button size="sm" onClick={() => exportCsv(r.key)} data-testid={`export-report-${r.key}`} className="bg-brand-navy hover:bg-brand-navy-dark"><Download size={14} className="mr-1" /> CSV</Button>
              <Button size="sm" onClick={() => exportPdf(r.key)} data-testid={`export-pdf-${r.key}`} className="bg-brand-magenta hover:bg-brand-pink"><Download size={14} className="mr-1" /> PDF</Button>
            </div>
          </div>
        ))}
      </div>
      {preview && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 overflow-x-auto">
          <h3 className="font-head font-semibold text-brand-navy mb-3">{active} — {preview.count} rows</h3>
          {preview.rows.length === 0 ? <p className="text-sm text-slate-400">No data</p> : (
            <table className="w-full text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{Object.keys(preview.rows[0]).map((k) => <th key={k} className="text-left p-2">{k}</th>)}</tr></thead>
              <tbody>{preview.rows.slice(0, 50).map((row, i) => <tr key={i} className="border-t border-slate-100">{Object.values(row).map((v, j) => <td key={j} className="p-2 text-slate-700">{String(v ?? "—")}</td>)}</tr>)}</tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
