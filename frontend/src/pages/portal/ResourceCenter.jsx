import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { BookOpen, Plus, ExternalLink, Trash2, Globe, Calendar, MessageSquare, FileText, Pencil } from "lucide-react";
import { api, API, useAuth } from "@/auth";
import { PageTitle, Loading, EmptyState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { UploadButton } from "@/components/PortalUpload";

const STAFF = ["super_admin", "director", "administrator"];

export default function ResourceCenter() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [res, setRes] = useState(null);
  const [settings, setSettings] = useState({});
  const [open, setOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [linkForm, setLinkForm] = useState({});
  const [f, setF] = useState({ category: "General", access_roles: [] });
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const onL = (k, v) => setLinkForm((p) => ({ ...p, [k]: v }));

  const load = () => api.get("/resources").then((r) => setRes(r.data)).catch(() => setRes([]));
  useEffect(() => { load(); api.get("/settings").then((r) => setSettings(r.data)).catch(() => {}); }, []);

  const create = async () => { if (!f.title) { toast.error("Title required"); return; } try { await api.post("/resources", f); toast.success("Resource added"); setOpen(false); setF({ category: "General", access_roles: [] }); load(); } catch { toast.error("Failed"); } };
  const del = async (id) => { await api.delete(`/resources/${id}`); toast.success("Removed"); load(); };
  const saveLinks = async () => { try { const { data } = await api.put("/settings", linkForm); setSettings(data); toast.success("Quick links updated"); setEditOpen(false); } catch { toast.error("Failed to save"); } };

  const quick = [
    { i: Globe, t: "AAWTA Website", url: settings.website }, { i: Calendar, t: "AAWTA Calendar", url: settings.calendar_link },
    { i: MessageSquare, t: "Access CEC Slack Workspace", url: settings.slack_link }, { i: FileText, t: "AAWTA Membership", url: settings.membership_link },
  ];

  return (
    <div className="space-y-5">
      <PageTitle title="Resource Center" subtitle="Quick links, documents & tools" action={isStaff && (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="rounded-full" data-testid="edit-links-btn" onClick={() => { setLinkForm({ website: settings.website, calendar_link: settings.calendar_link, slack_link: settings.slack_link, membership_link: settings.membership_link }); setEditOpen(true); }}><Pencil size={15} className="mr-1" /> Edit Quick Links</Button>
          <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="new-resource-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> Add Resource</Button></DialogTrigger>
          <DialogContent><DialogHeader><DialogTitle>Add Resource</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <Field label="Title" name="title" value={f.title} onChange={on} required />
              <Field label="Description" name="description" value={f.description} onChange={on} />
              <Field label="URL" name="url" value={f.url} onChange={on} placeholder="https://…" />
              <div>{f.file_name ? <span className="text-sm text-emerald-600">{f.file_name}</span> : <UploadButton testid="upload-resource" category="resource" label="Or upload a file" onUploaded={(x) => setF((p) => ({ ...p, file_id: x.id, file_name: x.filename }))} />}</div>
              <SelectField label="Category" name="category" value={f.category} onChange={on} options={["General", "Training", "Marketing", "Events", "Forms", "Reports", "Leadership"]} />
            </div>
            <DialogFooter><Button onClick={create} data-testid="save-resource-btn" className="bg-brand-magenta hover:bg-brand-pink">Add</Button></DialogFooter>
          </DialogContent>
        </Dialog>
        </div>
      )} />

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent><DialogHeader><DialogTitle>Edit Quick Links</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <Field label="AAWTA Website" name="website" value={linkForm.website} onChange={onL} placeholder="https://…" />
            <Field label="AAWTA Calendar" name="calendar_link" value={linkForm.calendar_link} onChange={onL} placeholder="https://…" />
            <Field label="CEC Slack Workspace" name="slack_link" value={linkForm.slack_link} onChange={onL} placeholder="https://…" />
            <Field label="AAWTA Membership" name="membership_link" value={linkForm.membership_link} onChange={onL} placeholder="https://…" />
          </div>
          <DialogFooter><Button onClick={saveLinks} data-testid="save-links-btn" className="bg-brand-magenta hover:bg-brand-pink">Save Links</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {quick.map((q, i) => (
          <a key={i} href={q.url || "#"} target="_blank" rel="noopener noreferrer" data-testid={`quick-resource-${i}`} className="bg-brand-navy text-white rounded-xl p-5 hover:-translate-y-1 transition-transform">
            <q.i size={22} className="text-brand-pink mb-3" /><p className="font-head font-semibold flex items-center gap-1">{q.t} <ExternalLink size={13} /></p>
          </a>
        ))}
      </div>

      {res === null ? <Loading /> : res.length === 0 ? <EmptyState icon={BookOpen} title="No custom resources yet" subtitle={isStaff ? "Add links and files for your members." : "Resources shared by leadership will appear here."} /> : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {res.map((r) => (
            <div key={r.id} className="bg-white border border-slate-200 rounded-xl p-5 flex flex-col" data-testid={`resource-${r.id}`}>
              <div className="flex items-start justify-between"><div className="h-10 w-10 rounded-lg bg-brand-magenta/10 text-brand-magenta flex items-center justify-center"><BookOpen size={18} /></div>{isStaff && <button onClick={() => del(r.id)} className="text-slate-300 hover:text-rose-500"><Trash2 size={16} /></button>}</div>
              <p className="font-head font-semibold text-brand-navy mt-3">{r.title}</p>
              <p className="text-sm text-slate-500 mt-1 flex-1">{r.description}</p>
              <a href={r.url || `${API}/files/${r.file_id}/download`} target="_blank" rel="noopener noreferrer" className="text-sm text-brand-magenta font-medium mt-3 flex items-center gap-1">Open <ExternalLink size={13} /></a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
