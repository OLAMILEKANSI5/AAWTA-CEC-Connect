import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Mail, Eye, Send, Zap, Hand, Save } from "lucide-react";
import { api, useAuth } from "@/auth";
import { PageTitle, Loading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

const LEADERSHIP = ["super_admin", "director"];

export default function TemplateEditor() {
  const { user } = useAuth();
  const canEdit = LEADERSHIP.includes(user?.role);
  const [templates, setTemplates] = useState(null);
  const [placeholders, setPlaceholders] = useState([]);
  const [editing, setEditing] = useState(null);
  const [preview, setPreview] = useState(null);
  const [testEmail, setTestEmail] = useState("");

  const load = () => api.get("/notification-templates").then((r) => { setTemplates(r.data.templates || []); setPlaceholders(r.data.placeholders || []); }).catch(() => toast.error("Failed to load"));
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      await api.put(`/notification-templates/${editing.key}`, {
        name: editing.name, subject: editing.subject, body: editing.body, mode: editing.mode,
        enabled: editing.enabled, include_button: editing.include_button, button_label: editing.button_label, category: editing.category,
      });
      toast.success("Template saved");
      setEditing(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };

  const doPreview = async (key) => {
    try { const r = await api.post(`/notification-templates/${key}/preview`); setPreview(r.data); }
    catch { toast.error("Preview failed"); }
  };

  const testSend = async (key) => {
    if (!testEmail.trim()) { toast.error("Enter a test email"); return; }
    try { const r = await api.post(`/notification-templates/${key}/test-send`, { to: testEmail }); toast[r.data.status === "sent" ? "success" : "error"](r.data.status === "sent" ? "Test email sent" : (r.data.error || "Send failed")); }
    catch (e) { toast.error(e?.response?.data?.detail || "Send failed"); }
  };

  const insertPlaceholder = (ph) => setEditing((e) => ({ ...e, body: (e.body || "") + `{{${ph}}}` }));

  if (!templates) return <Loading />;
  const grouped = templates.reduce((acc, t) => { (acc[t.category] = acc[t.category] || []).push(t); return acc; }, {});

  return (
    <div className="space-y-6">
      <PageTitle title="Notification Templates" subtitle="Create, edit, preview and test-send the communications CEC Connect sends to applicants and members." />
      {!canEdit && <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">You can view and test-send templates. Editing is limited to Directors and Super Administrators.</div>}

      {Object.entries(grouped).map(([cat, list]) => (
        <div key={cat} className="space-y-3">
          <h3 className="font-head font-semibold text-brand-navy text-sm uppercase tracking-wide">{cat}</h3>
          <div className="grid md:grid-cols-2 gap-4">
            {list.map((t) => (
              <div key={t.key} className="bg-white border border-slate-200 rounded-xl p-4 space-y-2" data-testid={`template-card-${t.key}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-800 text-sm">{t.name}</p>
                    <p className="text-xs text-slate-400 truncate">{t.subject}</p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-1 ${t.mode === "automatic" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                      {t.mode === "automatic" ? <Zap size={10} /> : <Hand size={10} />}{t.mode === "automatic" ? "Auto" : "Manual"}
                    </span>
                    {!t.enabled && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-600">Off</span>}
                  </div>
                </div>
                <div className="flex gap-2 pt-1">
                  <Button size="sm" variant="outline" onClick={() => doPreview(t.key)} data-testid={`preview-${t.key}`}><Eye size={14} className="mr-1" /> Preview</Button>
                  <Button size="sm" onClick={() => setEditing({ ...t })} disabled={!canEdit} data-testid={`edit-${t.key}`} className="bg-brand-magenta hover:bg-brand-pink">Edit</Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Edit dialog */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editing?.name}</DialogTitle></DialogHeader>
          {editing && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-4">
                <label className="flex items-center gap-2 text-sm"><Switch checked={editing.enabled} onCheckedChange={(v) => setEditing({ ...editing, enabled: v })} data-testid="tpl-enabled" /> Enabled</label>
                <label className="flex items-center gap-2 text-sm">
                  <Switch checked={editing.mode === "automatic"} onCheckedChange={(v) => setEditing({ ...editing, mode: v ? "automatic" : "manual" })} data-testid="tpl-mode" />
                  Send automatically on trigger
                </label>
              </div>
              <div><Label className="text-xs">Subject</Label><Input value={editing.subject} onChange={(e) => setEditing({ ...editing, subject: e.target.value })} data-testid="tpl-subject" /></div>
              <div>
                <Label className="text-xs">Message body</Label>
                <Textarea rows={9} value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })} data-testid="tpl-body" />
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {placeholders.map((ph) => (
                    <button key={ph} onClick={() => insertPlaceholder(ph)} className="text-[11px] px-2 py-0.5 rounded-full bg-brand-navy/10 text-brand-navy hover:bg-brand-navy/20">{`{{${ph}}}`}</button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 text-sm"><Switch checked={editing.include_button} onCheckedChange={(v) => setEditing({ ...editing, include_button: v })} data-testid="tpl-button-toggle" /> Include portal button</label>
                {editing.include_button && <Input className="flex-1" placeholder="Button label" value={editing.button_label || ""} onChange={(e) => setEditing({ ...editing, button_label: e.target.value })} data-testid="tpl-button-label" />}
              </div>
              <div className="border-t pt-3 flex items-center gap-2">
                <Input placeholder="Send a test to…" value={testEmail} onChange={(e) => setTestEmail(e.target.value)} data-testid="tpl-test-email" className="flex-1" />
                <Button variant="outline" onClick={() => testSend(editing.key)} data-testid="tpl-test-send"><Send size={14} className="mr-1" /> Test</Button>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => doPreview(editing.key)}><Eye size={14} className="mr-1" /> Preview</Button>
            <Button onClick={save} disabled={!canEdit} data-testid="tpl-save" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Save size={15} className="mr-1" /> Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview dialog */}
      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Mail size={16} /> {preview?.subject}</DialogTitle></DialogHeader>
          <div className="border border-slate-200 rounded-lg overflow-hidden" data-testid="tpl-preview-body" dangerouslySetInnerHTML={{ __html: preview?.html || "" }} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
