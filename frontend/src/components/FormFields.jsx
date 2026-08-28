import React, { useState } from "react";
import { toast } from "sonner";
import { Loader2, Upload, X, FileCheck2 } from "lucide-react";
import { api } from "@/auth";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

// Text/textarea field
export const Field = ({ label, name, value, onChange, type = "text", required, textarea, placeholder }) => (
  <div className="space-y-1.5">
    <Label className="text-sm text-slate-700">{label}{required && <span className="text-brand-magenta"> *</span>}</Label>
    {textarea ? (
      <textarea data-testid={`field-${name}`} value={value || ""} required={required} placeholder={placeholder}
        onChange={(e) => onChange(name, e.target.value)} rows={4}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40" />
    ) : (
      <Input data-testid={`field-${name}`} type={type} value={value || ""} required={required} placeholder={placeholder}
        onChange={(e) => onChange(name, e.target.value)} />
    )}
  </div>
);

// Select
export const SelectField = ({ label, name, value, onChange, options, required }) => (
  <div className="space-y-1.5">
    <Label className="text-sm text-slate-700">{label}{required && <span className="text-brand-magenta"> *</span>}</Label>
    <select data-testid={`field-${name}`} value={value || ""} required={required} onChange={(e) => onChange(name, e.target.value)}
      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40">
      <option value="">Select…</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  </div>
);

// Multi-select chips
export const MultiChips = ({ label, options, value = [], onChange }) => (
  <div className="space-y-2">
    <Label className="text-sm text-slate-700">{label}</Label>
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const active = value.includes(o);
        return (
          <button type="button" key={o} data-testid={`chip-${o.toLowerCase().replace(/[^a-z]/g, "-")}`}
            onClick={() => onChange(active ? value.filter((v) => v !== o) : [...value, o])}
            className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${active ? "bg-brand-magenta text-white border-brand-magenta" : "bg-white text-slate-600 border-slate-300 hover:border-brand-magenta"}`}>
            {o}
          </button>
        );
      })}
    </div>
  </div>
);

// Checkbox consent
export const Consent = ({ label, name, checked, onChange }) => (
  <label className="flex items-start gap-2.5 cursor-pointer">
    <input type="checkbox" data-testid={`field-${name}`} checked={!!checked} onChange={(e) => onChange(name, e.target.checked)}
      className="mt-1 h-4 w-4 accent-[#D6189B]" />
    <span className="text-sm text-slate-600">{label}</span>
  </label>
);

// Public file upload
export const FileField = ({ label, name, value, onChange, accept }) => {
  const [busy, setBusy] = useState(false);
  const handle = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/public/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      onChange(name, { id: data.id, filename: data.original_filename });
      toast.success(`${file.name} uploaded`);
    } catch { toast.error("Upload failed"); }
    setBusy(false);
  };
  return (
    <div className="space-y-1.5">
      <Label className="text-sm text-slate-700">{label}</Label>
      {value ? (
        <div className="flex items-center justify-between rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm">
          <span className="flex items-center gap-2 text-emerald-700 truncate"><FileCheck2 size={16} /> {value.filename}</span>
          <button type="button" onClick={() => onChange(name, null)}><X size={16} className="text-slate-400 hover:text-rose-500" /></button>
        </div>
      ) : (
        <label data-testid={`upload-${name}`} className="flex items-center gap-2 rounded-md border border-dashed border-slate-300 px-3 py-2.5 text-sm text-slate-500 cursor-pointer hover:border-brand-magenta">
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />} {busy ? "Uploading…" : "Choose file"}
          <input type="file" className="hidden" accept={accept} onChange={handle} disabled={busy} />
        </label>
      )}
    </div>
  );
};
