import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { MessageSquare, Send, Plus, ArrowLeft, Paperclip, FileText, X } from "lucide-react";
import { api, API, useAuth } from "@/auth";
import { PageTitle, Loading, EmptyState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { UploadButton } from "@/components/PortalUpload";
import { US_STATES } from "@/lib/constants";

const STAFF = ["super_admin", "director", "administrator"];

export default function Messages() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [msgs, setMsgs] = useState(null);
  const [members, setMembers] = useState([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ recipient_ids: [], file_ids: [] });
  const [attachments, setAttachments] = useState([]);
  const [thread, setThread] = useState(null);
  const [replyText, setReplyText] = useState("");
  const [replyFiles, setReplyFiles] = useState([]);
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => api.get("/messages").then((r) => setMsgs(r.data)).catch(() => setMsgs([]));
  useEffect(() => { load(); if (isStaff) api.get("/members").then((r) => setMembers(r.data)).catch(() => {}); }, [isStaff]);

  // group into threads (latest message per thread_id)
  const threads = Object.values((msgs || []).reduce((acc, m) => {
    const t = m.thread_id || m.id;
    if (!acc[t] || new Date(m.created_at) > new Date(acc[t].created_at)) acc[t] = m;
    return acc;
  }, {})).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const send = async () => {
    if (!f.subject || !f.body) { toast.error("Subject and message required"); return; }
    if (!isStaff && !f.recipient_ids.length) { toast.error("Select recipients"); return; }
    try { await api.post("/messages", { ...f, file_ids: attachments.map((a) => a.id) }); toast.success("Message sent"); setOpen(false); setF({ recipient_ids: [], file_ids: [] }); setAttachments([]); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const openThread = async (tid) => {
    try { const { data } = await api.get(`/messages/${tid}/thread`); setThread(data); load(); }
    catch { toast.error("Could not open thread"); }
  };

  const sendReply = async () => {
    if (!replyText.trim()) { toast.error("Write a reply"); return; }
    try {
      await api.post(`/messages/${thread.thread_id}/reply`, { body: replyText, file_ids: replyFiles.map((a) => a.id) });
      setReplyText(""); setReplyFiles([]);
      const { data } = await api.get(`/messages/${thread.thread_id}/thread`); setThread(data); load();
      toast.success("Reply sent");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  if (thread) {
    return (
      <div className="space-y-4 max-w-3xl">
        <Button variant="ghost" onClick={() => setThread(null)} className="text-slate-500"><ArrowLeft size={16} className="mr-1" /> Back to messages</Button>
        <h1 className="font-head text-2xl font-extrabold text-brand-navy">{thread.subject}</h1>
        <div className="space-y-3" data-testid="thread-messages">
          {thread.messages.map((m) => {
            const mine = m.from_id === user?.user_id;
            return (
              <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl p-4 ${mine ? "bg-brand-magenta text-white" : "bg-white border border-slate-200"}`}>
                  <div className={`text-xs mb-1 ${mine ? "text-white/80" : "text-brand-magenta"}`}>{m.from_name}{mine ? " (you)" : ""} · {new Date(m.created_at).toLocaleString()}</div>
                  <p className={`text-sm whitespace-pre-wrap ${mine ? "text-white" : "text-slate-700"}`}>{m.body}</p>
                  {m.files?.length > 0 && <div className="mt-2 space-y-1">{m.files.map((file) => (
                    <a key={file.id} href={`${API}/files/${file.id}/download`} target="_blank" rel="noreferrer" className={`flex items-center gap-1 text-xs underline ${mine ? "text-white/90" : "text-brand-navy"}`}><FileText size={12} /> {file.original_filename}</a>
                  ))}</div>}
                </div>
              </div>
            );
          })}
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
          <textarea value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="Write a reply…" rows={3} data-testid="reply-input" className="w-full rounded-md border border-input px-3 py-2 text-sm" />
          {replyFiles.length > 0 && <div className="flex flex-wrap gap-2">{replyFiles.map((a) => (
            <span key={a.id} className="flex items-center gap-1 text-xs bg-slate-100 rounded-full px-2 py-1"><Paperclip size={12} /> {a.filename} <button onClick={() => setReplyFiles((p) => p.filter((x) => x.id !== a.id))}><X size={12} /></button></span>
          ))}</div>}
          <div className="flex items-center justify-between">
            <UploadButton testid="reply-attach" category="message" label="Attach file" onUploaded={(x) => setReplyFiles((p) => [...p, x])} />
            <Button onClick={sendReply} data-testid="send-reply-btn" className="bg-brand-magenta hover:bg-brand-pink"><Send size={15} className="mr-1" /> Reply</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageTitle title="Messages" subtitle="Threaded conversations with your team" action={
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
              {attachments.length > 0 && <div className="flex flex-wrap gap-2">{attachments.map((a) => (
                <span key={a.id} className="flex items-center gap-1 text-xs bg-slate-100 rounded-full px-2 py-1"><Paperclip size={12} /> {a.filename} <button onClick={() => setAttachments((p) => p.filter((x) => x.id !== a.id))}><X size={12} /></button></span>
              ))}</div>}
              <UploadButton testid="message-attach" category="message" label="Attach file" onUploaded={(x) => setAttachments((p) => [...p, x])} />
            </div>
            <DialogFooter><Button onClick={send} data-testid="send-message-btn" className="bg-brand-magenta hover:bg-brand-pink"><Send size={15} className="mr-1" /> Send</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      } />
      {msgs === null ? <Loading /> : threads.length === 0 ? <EmptyState icon={MessageSquare} title="No messages yet" /> : (
        <div className="space-y-3">
          {threads.map((m) => {
            const unread = !m.read_by?.includes(user?.user_id) && m.from_id !== user?.user_id;
            return (
              <div key={m.thread_id} onClick={() => openThread(m.thread_id)} data-testid={`thread-${m.thread_id}`} className={`bg-white border rounded-xl p-4 cursor-pointer hover:shadow-md transition-shadow ${unread ? "border-brand-magenta/40 bg-brand-magenta/5" : "border-slate-200"}`}>
                <div className="flex items-center justify-between">
                  <p className="font-medium text-slate-800 flex items-center gap-2">{unread && <span className="h-2 w-2 rounded-full bg-brand-magenta" />}{m.subject}</p>
                  <span className="text-xs text-slate-400">{new Date(m.created_at).toLocaleString()}</span>
                </div>
                <p className="text-xs text-brand-magenta mt-0.5">{m.from_id === user?.user_id ? "You" : m.from_name}</p>
                <p className="text-sm text-slate-600 mt-1 line-clamp-1">{m.body}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
