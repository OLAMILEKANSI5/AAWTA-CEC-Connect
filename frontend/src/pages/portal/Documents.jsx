import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileSignature, Plus, Download, PenLine, MoreHorizontal } from "lucide-react";
import { api, API, useAuth } from "@/auth";
import { PageTitle, StatusBadge, Loading, EmptyState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { Field, SelectField, Consent } from "@/components/FormFields";
import { UploadButton } from "@/components/PortalUpload";
import { DOC_CATEGORIES } from "@/lib/constants";

const STAFF = ["super_admin", "director", "administrator"];
const AUDIENCES = [["private_draft", "Private Draft — Not Assigned"], ["ambassadors_only", "Ambassadors only"], ["volunteers_only", "Volunteers only"], ["interns_only", "Interns only"], ["ambassadors_volunteers", "Ambassadors & Volunteers"], ["specific_members", "Specific members"], ["all_active", "All active CEC members"], ["admins_only", "Administrators only"]];
const blank = { category: "Onboarding", required: true, requires_signature: true, audience: "private_draft", status: "active", version: "1.0", assigned_to: [], assigned_roles: [], onboarding_profiles: [] };

export default function Documents() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [docs, setDocs] = useState(null);
  const [members, setMembers] = useState([]);
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [f, setF] = useState(blank);
  const [signDoc, setSignDoc] = useState(null);
  const [legalName, setLegalName] = useState("");
  const [consent, setConsent] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [signers, setSigners] = useState(null);
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => api.get("/documents").then((r) => setDocs(r.data)).catch(() => setDocs([]));
  useEffect(() => { load(); if (isStaff) api.get("/members").then((r) => setMembers(r.data)).catch(() => {}); }, [isStaff]);

  const openNew = () => { setEditId(null); setF(blank); setOpen(true); };
  const openEdit = (d) => { setEditId(d.id); setF({ ...blank, ...d }); setOpen(true); };
  const save = async () => {
    if (!f.title) { toast.error("Title required"); return; }
    try {
      if (editId) { await api.put(`/documents/${editId}`, f); toast.success("Document updated"); }
      else { await api.post("/documents", f); toast.success("Document created"); }
      setOpen(false); setF(blank); setEditId(null); load();
    } catch { toast.error("Failed"); }
  };
  const assignAll = async (d) => { try { await api.post(`/documents/${d.id}/assign`, { audience: "all_active", notify: true }); toast.success("Assigned to all active members"); load(); } catch { toast.error("Failed"); } };
  const archive = async (d) => { try { await api.put(`/documents/${d.id}/archive`, { archived: d.status !== "archived" }); toast.success(d.status === "archived" ? "Restored" : "Archived"); load(); } catch { toast.error("Failed"); } };
  const del = async (d) => { if (!window.confirm(`Delete "${d.title}"? Only unassigned drafts can be deleted.`)) return; try { await api.delete(`/documents/${d.id}`); toast.success("Deleted"); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Cannot delete"); } };
  const sign = async () => {
    if (!consent || !legalName) { toast.error("Enter your legal name and consent"); return; }
    try { await api.post(`/documents/${signDoc.id}/sign`, { legal_name: legalName, consent: true }); toast.success("Document signed"); setSignDoc(null); setLegalName(""); setConsent(false); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const audLabel = (a) => (AUDIENCES.find((x) => x[0] === (a || "private_draft")) || ["private_draft", "Private Draft"])[1];
  const openSigners = async (d) => { try { const { data } = await api.get(`/documents/${d.id}/signers`); setSigners({ ...data, doc: d }); } catch { toast.error("Failed to load signers"); } };

  return (
    <div className="space-y-5">
      <PageTitle title="Documents" subtitle="Forms, policies & signatures" action={isStaff && (
        <Button onClick={openNew} data-testid="new-document-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> New Document</Button>
      )} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editId ? "Edit Document" : "Create Document"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <Field label="Title" name="title" value={f.title} onChange={on} required />
            <Field label="Description" name="description" value={f.description} onChange={on} textarea />
            <div className="grid grid-cols-2 gap-4">
              <SelectField label="Category" name="category" value={f.category} onChange={on} options={DOC_CATEGORIES} />
              <Field label="Version" name="version" value={f.version || "1.0"} onChange={on} />
            </div>
            <div><span className="text-sm text-slate-700">Attach file</span><div className="mt-1">{f.file_name || f.file_id ? <span className="text-sm text-emerald-600">{f.file_name || "File attached"} · <button className="text-brand-magenta underline" onClick={() => on("file_id", null) || on("file_name", null)}>replace</button></span> : <UploadButton testid="upload-doc" category="document" label="Upload document" onUploaded={(x) => setF((p) => ({ ...p, file_id: x.id, file_name: x.filename }))} />}</div></div>
            <div><label className="text-sm text-slate-700">Audience / visibility</label>
              <select value={f.audience} onChange={(e) => on("audience", e.target.value)} data-testid="doc-audience" className="w-full mt-1 rounded-md border border-input p-2 text-sm">{AUDIENCES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            </div>
            {f.audience === "specific_members" && (
              <div><span className="text-sm text-slate-700">Assign to members</span>
                <select multiple value={f.assigned_to} onChange={(e) => on("assigned_to", Array.from(e.target.selectedOptions).map((o) => o.value))} className="w-full mt-1 rounded-md border border-input p-2 text-sm h-24">
                  {members.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.role})</option>)}
                </select>
              </div>
            )}
            <Consent label="Requires signature" name="requires_signature" checked={f.requires_signature} onChange={on} />
            <Consent label="Required (vs optional)" name="required" checked={f.required} onChange={on} />
            <Consent label="Auto-assign on approval (onboarding)" name="auto_onboarding" checked={f.auto_onboarding} onChange={on} />
            {f.auto_onboarding && (
              <div><span className="text-sm text-slate-700">Assign automatically to approved…</span>
                <div className="flex gap-3 mt-1">{["ambassador", "volunteer", "intern"].map((r) => (
                  <label key={r} className="flex items-center gap-1.5 text-sm capitalize"><input type="checkbox" checked={(f.onboarding_profiles || []).includes(r)} onChange={(e) => on("onboarding_profiles", e.target.checked ? [...(f.onboarding_profiles || []), r] : (f.onboarding_profiles || []).filter((x) => x !== r))} className="accent-[#D6189B]" /> {r}s</label>
                ))}</div>
              </div>
            )}
          </div>
          <DialogFooter><Button onClick={save} data-testid="save-document-btn" className="bg-brand-magenta hover:bg-brand-pink">{editId ? "Save Changes" : "Create"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {docs === null ? <Loading /> : docs.length === 0 ? <EmptyState icon={FileSignature} title="No documents yet" /> : (
        <div className="space-y-3">
          {docs.map((d) => (
            <div key={d.id} className={`bg-white border border-slate-200 rounded-xl p-4 ${d.status === "archived" ? "opacity-60" : ""}`} data-testid={`doc-${d.id}`}>
              <div className="flex flex-wrap items-start gap-4">
                <div className="h-10 w-10 rounded-lg bg-brand-magenta/10 text-brand-magenta flex items-center justify-center shrink-0"><FileSignature size={18} /></div>
                <div className="flex-1 min-w-[200px]">
                  <p className="font-medium text-slate-800">{d.title} <span className="text-xs text-slate-400">v{d.version}</span>{d.status === "archived" && <span className="text-xs text-slate-400"> · Archived</span>}</p>
                  {d.description && <p className="text-sm text-slate-500 mt-0.5" style={expanded[d.id] ? {} : { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }} data-testid={`doc-desc-${d.id}`}>{d.description}{!expanded[d.id] && d.description.length > 120 ? <button className="text-brand-magenta ml-1" onClick={() => setExpanded((p) => ({ ...p, [d.id]: true }))}>Read more</button> : null}</p>}
                  <p className="text-xs text-slate-400 mt-1">{d.category} · {d.required ? "Required" : "Optional"}{isStaff && <> · {audLabel(d.audience)} · {d.assigned_count || 0} assigned · <button onClick={() => openSigners(d)} data-testid={`signed-count-${d.id}`} className="text-brand-magenta underline font-medium">{d.signatures_count} signed</button></>}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {d.file_id && <a href={`${API}/files/${d.file_id}/download`} target="_blank" rel="noreferrer"><Button variant="outline" size="sm"><Download size={14} className="mr-1" /> View</Button></a>}
                  {d.requires_signature && (d.signed_by_me ? (
                    <a href={`${API}/signatures/${d.signature_id}/pdf`} target="_blank" rel="noreferrer" data-testid={`download-signed-${d.id}`}><Button variant="outline" size="sm"><Download size={14} className="mr-1" /> Signed PDF</Button></a>
                  ) : (!isStaff && <Button size="sm" onClick={() => setSignDoc(d)} data-testid={`sign-${d.id}`} className="bg-brand-navy hover:bg-brand-navy-dark"><PenLine size={14} className="mr-1" /> Sign</Button>))}
                  {isStaff && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild><Button size="sm" variant="ghost" data-testid={`doc-actions-${d.id}`}><MoreHorizontal size={16} /></Button></DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openEdit(d)} data-testid={`doc-edit-${d.id}`}>Edit</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => assignAll(d)}>Assign to all active</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => archive(d)} data-testid={`doc-archive-${d.id}`}>{d.status === "archived" ? "Restore" : "Archive"}</DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => del(d)} className="text-rose-600" data-testid={`doc-delete-${d.id}`}>Delete</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
              </div>
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
      <Dialog open={!!signers} onOpenChange={(o) => !o && setSigners(null)}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto" data-testid="signers-dialog">
          <DialogHeader><DialogTitle>Signatures — {signers?.title}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wide mb-2">Signed ({signers?.signed?.length || 0})</p>
              {signers?.signed?.length ? signers.signed.map((s, i) => (
                <div key={i} className="flex items-center justify-between gap-2 py-2 border-b border-slate-100 text-sm" data-testid="signer-row">
                  <div className="min-w-0"><p className="font-medium text-slate-800 truncate">{s.name} <span className="text-xs text-slate-400 capitalize">{s.role}</span></p><p className="text-xs text-slate-400">Signed {new Date(s.signed_at).toLocaleString()} · as "{s.legal_name}"</p></div>
                  <a href={`${API}/signatures/${s.signature_id}/pdf`} target="_blank" rel="noreferrer" data-testid={`signer-pdf-${i}`}><Button size="sm" variant="outline"><Download size={13} className="mr-1" /> PDF</Button></a>
                </div>
              )) : <p className="text-sm text-slate-400">No signatures yet.</p>}
            </div>
            <div>
              <p className="text-xs font-semibold text-amber-600 uppercase tracking-wide mb-2">Pending ({signers?.pending?.length || 0})</p>
              {signers?.pending?.length ? signers.pending.map((s, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 text-sm" data-testid="pending-row"><span className="text-slate-700">{s.name} <span className="text-xs text-slate-400 capitalize">{s.role}</span></span><span className="text-xs text-amber-600">Awaiting signature</span></div>
              )) : <p className="text-sm text-slate-400">Everyone assigned has signed.</p>}
            </div>
            {signers?.doc?.file_id && <a href={`${API}/files/${signers.doc.file_id}/download`} target="_blank" rel="noreferrer"><Button variant="outline" size="sm" className="w-full" data-testid="preview-doc-btn"><Download size={14} className="mr-1" /> Preview document</Button></a>}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
