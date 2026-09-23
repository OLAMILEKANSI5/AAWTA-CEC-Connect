import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageSquarePlus, Mail, Bell, Send, Clock } from "lucide-react";
import { api } from "@/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STATUS_STYLES = {
  sent: "bg-blue-100 text-blue-700", delivered: "bg-emerald-100 text-emerald-700",
  opened: "bg-emerald-100 text-emerald-700", bounced: "bg-rose-100 text-rose-700",
  failed: "bg-rose-100 text-rose-700", portal_only: "bg-slate-100 text-slate-600",
};
const STATUS_LABELS = {
  sent: "Sent", delivered: "Delivered", opened: "Opened", bounced: "Bounced",
  failed: "Failed", portal_only: "Portal only",
};
const CHANNEL_LABELS = { email: "Email", portal: "Portal notification", both: "Email + Portal" };

const EMPTY = { template_key: "", subject: "", body: "", channel: "email", include_button: false, button_label: "" };

export const CommsPanel = ({ subjectType, subjectId }) => {
  const [comms, setComms] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [sending, setSending] = useState(false);

  const loadComms = useCallback(() => {
    api.get(`/comms?subject_type=${subjectType}&subject_id=${subjectId}`).then((r) => setComms(r.data)).catch(() => {});
  }, [subjectType, subjectId]);

  useEffect(() => {
    loadComms();
    api.get("/notification-templates").then((r) => setTemplates(r.data.templates || [])).catch(() => {});
  }, [loadComms]);

  const pickTemplate = async (key) => {
    if (!key) { setForm((f) => ({ ...f, template_key: "" })); return; }
    try {
      const r = await api.post("/comms/preview", { subject_type: subjectType, subject_id: subjectId, template_key: key });
      setForm((f) => ({ ...f, template_key: key, subject: r.data.subject, body: r.data.body, include_button: r.data.include_button, button_label: r.data.button_label }));
    } catch { toast.error("Could not load template"); }
  };

  const send = async () => {
    if (!form.subject.trim() || !form.body.trim()) { toast.error("Subject and message are required"); return; }
    setSending(true);
    try {
      await api.post("/comms/send", { subject_type: subjectType, subject_id: subjectId, ...form });
      toast.success("Message sent");
      setOpen(false); setForm(EMPTY); loadComms();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to send");
    } finally { setSending(false); }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4" data-testid="comms-panel">
      <div className="flex items-center justify-between">
        <h3 className="font-head font-semibold text-brand-navy">Communication History</h3>
        <Button size="sm" onClick={() => { setForm(EMPTY); setOpen(true); }} data-testid="send-message-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink">
          <MessageSquarePlus size={16} className="mr-1" /> Send Message
        </Button>
      </div>

      {comms.length === 0 ? (
        <p className="text-sm text-slate-400">No communications yet.</p>
      ) : (
        <div className="space-y-2">
          {comms.map((c) => (
            <div key={c.id} className="p-3 border border-slate-100 rounded-lg" data-testid="comm-row">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{c.subject}</p>
                  <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1.5 flex-wrap">
                    <Clock size={12} /> {new Date(c.created_at).toLocaleString()} · {c.sent_by_name}
                    {c.template_name && <span className="px-1.5 py-0.5 rounded-full bg-brand-navy/10 text-brand-navy">{c.template_name}</span>}
                    <span className="px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500">{CHANNEL_LABELS[c.channel] || c.channel}</span>
                  </p>
                </div>
                <span className={`text-[11px] px-2 py-0.5 rounded-full shrink-0 ${STATUS_STYLES[c.status] || "bg-slate-100 text-slate-600"}`}>{STATUS_LABELS[c.status] || c.status}</span>
              </div>
              <p className="text-sm text-slate-600 mt-2 whitespace-pre-line line-clamp-4">{c.body}</p>
              {c.error && <p className="text-xs text-rose-500 mt-1">{c.error}</p>}
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Send Message</DialogTitle><DialogDescription>Compose a message to this recipient. Placeholders are filled in automatically.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Template (optional)</Label>
              <Select value={form.template_key || "none"} onValueChange={(v) => pickTemplate(v === "none" ? "" : v)}>
                <SelectTrigger data-testid="comm-template-select"><SelectValue placeholder="Custom message" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Custom message</SelectItem>
                  {templates.map((t) => <SelectItem key={t.key} value={t.key}>{t.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Subject</Label>
              <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} data-testid="comm-subject-input" />
            </div>
            <div>
              <Label className="text-xs">Message</Label>
              <Textarea rows={7} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} data-testid="comm-body-input" />
              <p className="text-[11px] text-slate-400 mt-1">Placeholders like {"{{first_name}}"} are filled in automatically for this recipient.</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <Label className="text-xs">Deliver via</Label>
                <Select value={form.channel} onValueChange={(v) => setForm({ ...form, channel: v })}>
                  <SelectTrigger data-testid="comm-channel-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="email"><span className="flex items-center gap-1.5"><Mail size={13} /> Email</span></SelectItem>
                    <SelectItem value="portal"><span className="flex items-center gap-1.5"><Bell size={13} /> Portal notification</span></SelectItem>
                    <SelectItem value="both">Email + Portal</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <label className="flex items-center gap-2 text-sm pt-5">
                <Switch checked={form.include_button} onCheckedChange={(v) => setForm({ ...form, include_button: v })} data-testid="comm-button-toggle" />
                Include portal button
              </label>
            </div>
            {form.include_button && (
              <Input placeholder="Button label" value={form.button_label} onChange={(e) => setForm({ ...form, button_label: e.target.value })} data-testid="comm-button-label" />
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={send} disabled={sending} data-testid="comm-send-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink">
              <Send size={15} className="mr-1" /> {sending ? "Sending…" : "Send"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
