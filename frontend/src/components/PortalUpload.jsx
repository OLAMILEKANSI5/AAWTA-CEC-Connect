import React, { useState } from "react";
import { toast } from "sonner";
import { Loader2, Upload } from "lucide-react";
import { api } from "@/auth";

// Authenticated portal upload. onDone receives { id, filename }
export const usePortalUpload = () => {
  const [busy, setBusy] = useState(false);
  const upload = async (file, category = "general") => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("category", category);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      return { id: data.id, filename: data.original_filename };
    } catch { toast.error("Upload failed"); return null; }
    finally { setBusy(false); }
  };
  return { upload, busy };
};

export const UploadButton = ({ onUploaded, category = "general", accept, label = "Upload file", testid }) => {
  const { upload, busy } = usePortalUpload();
  return (
    <label data-testid={testid} className="inline-flex items-center gap-2 rounded-full border border-dashed border-slate-300 px-4 py-2 text-sm text-slate-600 cursor-pointer hover:border-brand-magenta">
      {busy ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />} {busy ? "Uploading…" : label}
      <input type="file" className="hidden" accept={accept} disabled={busy} onChange={async (e) => { const f = e.target.files?.[0]; if (f) { const r = await upload(f, category); if (r) onUploaded(r); } }} />
    </label>
  );
};
