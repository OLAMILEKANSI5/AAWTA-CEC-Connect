import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageSquare, Send, Plus } from "lucide-react";
import { api, useAuth } from "@/auth";
import { PageTitle, Loading, EmptyState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { US_STATES } from "@/lib/constants";

const STAFF = ["super_admin", "director", "administrator"];

export default function Messages() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [msgs, setMsgs] = useState(null);
  const [members, setMembers] = useState([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ recipient_ids: [] });
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => api.get("/messages").then((r) => setMsgs(r.data)).catch(() => setMsgs([]));
  useEffect(() => { load(); api.get(isStaff ? "/members" : "/users").then((r) => setMembers(isStaff ? r.data : [])).catch(() => {}); }, [isStaff]);

  const send = async () => {
    if (!f.subject || !f.body) { toast.error("Subject and message required"); return; }
    if (!isStaff && !f.recipient_ids.length) { toast.error("Select recipients"); return; }
    try { await api.post("/messages", f); toast.success("Message sent"); setOpen(false); setF({ recipient_ids: [] }); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="space-y-5">
      <PageTitle title="Messages" subtitle="Communicate with your team" action={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="new-message-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> New Message</Button></DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle>Send Message</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <Field label="Subject" name="subject" value={f.subject} onChange={on} required />
              <Field label="Message" name="body" value={f.body} onChange={on} textarea required />
              {isStaff ? (<>
                <div className="grid grid-cols-2 gap-3">
                  <SelectField label="Target role" name="target_role" value={f.target_role} onChange={on} options={["ambassador", "volunteer"]} />
                  <SelectField label="Target state" name="target_state" value={f.target_state} onChange={on} options={US_STATES} />
                </div>
                <div><span className="text-sm text-slate-700">Or specific members</span>
                  <select multiple value={f.recipient_ids} onChange={(e) => on("recipient_ids", Array.from(e.target.selectedOptions).map((o) => o.value))} className="w-full mt-1 rounded-md border border-input p-2 text-sm h-24">
                    {members.filter((m) => m.user_id).map((m) => <option key={m.id} value={m.user_id}>{m.name}</option>)}
                  </select>
                </div>
              </>) : <p className="text-xs text-slate-500">Your message will be sent to CEC leadership.</p>}
            </div>
            <DialogFooter><Button onClick={send} data-testid="send-message-btn" className="bg-brand-magenta hover:bg-brand-pink"><Send size={15} className="mr-1" /> Send</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      } />
      {msgs === null ? <Loading /> : msgs.length === 0 ? <EmptyState icon={MessageSquare} title="No messages yet" /> : (
        <div className="space-y-3">
          {msgs.map((m) => (
            <div key={m.id} className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="flex items-center justify-between"><p className="font-medium text-slate-800">{m.subject}</p><span className="text-xs text-slate-400">{new Date(m.created_at).toLocaleString()}</span></div>
              <p className="text-xs text-brand-magenta mt-0.5">From {m.from_name} {m.from_id === user?.user_id ? "(you)" : ""}</p>
              <p className="text-sm text-slate-600 mt-2">{m.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
