import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileSignature, Plus, Download, PenLine } from "lucide-react";
import { api, API, useAuth } from "@/auth";
import { PageTitle, StatusBadge, Loading, EmptyState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { UploadButton } from "@/components/PortalUpload";
import { DOC_CATEGORIES } from "@/lib/constants";

const STAFF = ["super_admin", "director", "administrator"];

export default function Documents() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [docs, setDocs] = useState(null);
  const [members, setMembers] = useState([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ category: "Onboarding", required: true, requires_signature: true, assigned_to: [], assigned_roles: [] });
  const [signDoc, setSignDoc] = useState(null);
  const [legalName, setLegalName] = useState("");
  const [consent, setConsent] = useState(false);
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => api.get("/documents").then((r) => setDocs(r.data)).catch(() => setDocs([]));
  useEffect(() => { load(); if (isStaff) api.get("/members").then((r) => setMembers(r.data)).catch(() => {}); }, [isStaff]);

  const create = async () => {
    if (!f.title) { toast.error("Title required"); return; }
    try { await api.post("/documents", f); toast.success("Document created"); setOpen(false); setF({ category: "Onboarding", required: true, requires_signature: true, assigned_to: [], assigned_roles: [] }); load(); }
    catch { toast.error("Failed"); }
  };
  const sign = async () => {
    if (!consent || !legalName) { toast.error("Enter your legal name and consent"); return; }
    try { await api.post(`/documents/${signDoc.id}/sign`, { legal_name: legalName, consent: true }); toast.success("Document signed"); setSignDoc(null); setLegalName(""); setConsent(false); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-5">
      <PageTitle title="Documents" subtitle="Forms, policies & signatures" action={isStaff && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="new-document-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> New Document</Button></DialogTrigger>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>Create Document</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <Field label="Title" name="title" value={f.title} onChange={on} required />
              <Field label="Description" name="description" value={f.description} onChange={on} textarea />
              <div className="grid grid-cols-2 gap-4">
                <SelectField label="Category" name="category" value={f.category} onChange={on} options={DOC_CATEGORIES} />
                <Field label="Version" name="version" value={f.version || "1.0"} onChange={on} />
              </div>
              <div><span className="text-sm text-slate-700">Attach file</span><div className="mt-1">{f.file_name ? <span className="text-sm text-emerald-600">{f.file_name}</span> : <UploadButton testid="upload-doc" category="document" label="Upload document" onUploaded={(x) => setF((p) => ({ ...p, file_id: x.id, file_name: x.filename }))} />}</div></div>
              <SelectField label="Assign to role" name="assign_role" value={(f.assigned_roles || [])[0] || ""} onChange={(k, v) => on("assigned_roles", v ? [v] : [])} options={["ambassador", "volunteer"]} />
              <div><span className="text-sm text-slate-700">Assign to members</span>
                <select multiple value={f.assigned_to} onChange={(e) => on("assigned_to", Array.from(e.target.selectedOptions).map((o) => o.value))} className="w-full mt-1 rounded-md border border-input p-2 text-sm h-28">
                  {members.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.role})</option>)}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.requires_signature} onChange={(e) => on("requires_signature", e.target.checked)} className="accent-[#D6189B]" /> Requires signature</label>
            </div>
            <DialogFooter><Button onClick={create} data-testid="save-document-btn" className="bg-brand-magenta hover:bg-brand-pink">Create</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      )} />

      {docs === null ? <Loading /> : docs.length === 0 ? <EmptyState icon={FileSignature} title="No documents yet" /> : (
        <div className="space-y-3">
          {docs.map((d) => (
            <div key={d.id} className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap items-center gap-4" data-testid={`doc-${d.id}`}>
              <div className="h-10 w-10 rounded-lg bg-brand-magenta/10 text-brand-magenta flex items-center justify-center"><FileSignature size={18} /></div>
              <div className="flex-1 min-w-[180px]"><p className="font-medium text-slate-800">{d.title} <span className="text-xs text-slate-400">v{d.version}</span></p><p className="text-xs text-slate-400">{d.category}{d.required ? " · Required" : ""}</p></div>
              {isStaff && <span className="text-xs text-slate-500">{d.signatures_count} signed</span>}
              {d.file_id && <a href={`${API}/files/${d.file_id}/download`} target="_blank" rel="noreferrer"><Button variant="outline" size="sm"><Download size={14} className="mr-1" /> View</Button></a>}
              {d.requires_signature && (d.signed_by_me ? (
                <div className="flex items-center gap-2">
                  <StatusBadge status="Achieved" />
                  <a href={`${API}/signatures/${d.signature_id}/pdf`} target="_blank" rel="noreferrer" data-testid={`download-signed-${d.id}`}><Button variant="outline" size="sm"><Download size={14} className="mr-1" /> Signed PDF</Button></a>
                </div>
              ) : <Button size="sm" onClick={() => setSignDoc(d)} data-testid={`sign-${d.id}`} className="bg-brand-navy hover:bg-brand-navy-dark"><PenLine size={14} className="mr-1" /> Sign</Button>)}
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!signDoc} onOpenChange={(o) => !o && setSignDoc(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Sign: {signDoc?.title}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-slate-500">By signing, you agree to the terms of this document (version {signDoc?.version}). Signed documents cannot be overwritten.</p>
            <div><label className="text-sm">Typed legal name</label><input value={legalName} onChange={(e) => setLegalName(e.target.value)} data-testid="sign-legal-name" className="w-full mt-1 rounded-md border border-input px-3 py-2 text-sm font-mono-data" placeholder="Your full legal name" /></div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="accent-[#D6189B]" data-testid="sign-consent" /> I consent to sign this document electronically.</label>
          </div>
          <DialogFooter><Button onClick={sign} data-testid="submit-signature-btn" className="bg-brand-magenta hover:bg-brand-pink">Sign Document</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
