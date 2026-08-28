import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Megaphone, Plus, CheckCircle2 } from "lucide-react";
import { api, useAuth } from "@/auth";
import { PageTitle, Loading, EmptyState, StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField, MultiChips } from "@/components/FormFields";
import { US_STATES } from "@/lib/constants";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const STAFF = ["super_admin", "director", "administrator"];

export default function Announcements() {
  const { user } = useAuth();
  const isStaff = STAFF.includes(user?.role);
  const [anns, setAnns] = useState(null);
  const [reqs, setReqs] = useState([]);
  const [open, setOpen] = useState(false);
  const [reqOpen, setReqOpen] = useState(false);
  const [f, setF] = useState({ target_roles: [], target_states: [], priority: "normal", public: false, email_notify: false });
  const [r, setR] = useState({});
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => { api.get("/announcements").then((x) => setAnns(x.data)).catch(() => setAnns([])); api.get("/announcement-requests").then((x) => setReqs(x.data)).catch(() => {}); };
  useEffect(() => { load(); }, []);

  const publish = async () => { if (!f.title || !f.message) { toast.error("Title and message required"); return; } try { await api.post("/announcements", f); toast.success("Published"); setOpen(false); setF({ target_roles: [], target_states: [], priority: "normal", public: false, email_notify: false }); load(); } catch { toast.error("Failed"); } };
  const submitReq = async () => { if (!r.title || !r.message) { toast.error("Fill all fields"); return; } try { await api.post("/announcement-requests", r); toast.success("Request submitted"); setReqOpen(false); setR({}); load(); } catch { toast.error("Failed"); } };
  const ack = async (id) => { await api.post(`/announcements/${id}/ack`); toast.success("Acknowledged"); load(); };

  return (
    <div className="space-y-5">
      <PageTitle title="Announcements" subtitle={isStaff ? "Publish and manage announcements" : "Official announcements & your requests"} action={
        isStaff ? (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button data-testid="new-announcement-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> Publish</Button></DialogTrigger>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader><DialogTitle>Publish Announcement</DialogTitle></DialogHeader>
              <div className="space-y-4">
                <Field label="Title" name="title" value={f.title} onChange={on} required />
                <Field label="Message" name="message" value={f.message} onChange={on} textarea required />
                <MultiChips label="Target roles (empty = all)" options={["ambassador", "volunteer"]} value={f.target_roles} onChange={(v) => on("target_roles", v)} />
                <SelectField label="Priority" name="priority" value={f.priority} onChange={on} options={["low", "normal", "high"]} />
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.public} onChange={(e) => on("public", e.target.checked)} className="accent-[#D6189B]" /> Public</label>
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.require_ack} onChange={(e) => on("require_ack", e.target.checked)} className="accent-[#D6189B]" /> Require acknowledgment</label>
                </div>
              </div>
              <DialogFooter><Button onClick={publish} data-testid="publish-announcement-btn" className="bg-brand-magenta hover:bg-brand-pink">Publish</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        ) : (
          <Dialog open={reqOpen} onOpenChange={setReqOpen}>
            <DialogTrigger asChild><Button data-testid="request-announcement-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> Request</Button></DialogTrigger>
            <DialogContent><DialogHeader><DialogTitle>Request an Announcement</DialogTitle></DialogHeader>
              <div className="space-y-4"><Field label="Title" name="title" value={r.title} onChange={(k, v) => setR((p) => ({ ...p, [k]: v }))} required /><Field label="Message" name="message" value={r.message} onChange={(k, v) => setR((p) => ({ ...p, [k]: v }))} textarea required /></div>
              <DialogFooter><Button onClick={submitReq} data-testid="submit-ann-request-btn" className="bg-brand-magenta hover:bg-brand-pink">Submit for Approval</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        )
      } />

      <Tabs defaultValue="published">
        <TabsList><TabsTrigger value="published">Announcements</TabsTrigger><TabsTrigger value="requests">Requests ({reqs.length})</TabsTrigger></TabsList>
        <TabsContent value="published">
          {anns === null ? <Loading /> : anns.length === 0 ? <EmptyState icon={Megaphone} title="No announcements" /> : (
            <div className="space-y-3">{anns.map((a) => (
              <div key={a.id} className="bg-white border border-slate-200 rounded-xl p-5" data-testid={`announcement-${a.id}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex gap-3"><Megaphone className="text-brand-magenta shrink-0 mt-1" size={20} /><div><p className="font-head font-semibold text-brand-navy">{a.title}</p><p className="text-sm text-slate-600 mt-1">{a.message}</p><p className="text-xs text-slate-400 mt-2">{a.author} · {new Date(a.created_at).toLocaleDateString()}{a.public ? " · Public" : ""}</p></div></div>
                  {a.priority === "high" && <StatusBadge status="Under Review" />}
                </div>
                {a.require_ack && !isStaff && (a.acked_by?.includes(user?.user_id) ? <span className="text-xs text-emerald-600 flex items-center gap-1 mt-3"><CheckCircle2 size={14} /> Acknowledged</span> : <Button size="sm" onClick={() => ack(a.id)} className="mt-3 bg-brand-navy hover:bg-brand-navy-dark">Acknowledge</Button>)}
              </div>
            ))}</div>
          )}
        </TabsContent>
        <TabsContent value="requests">
          {reqs.length === 0 ? <EmptyState icon={Megaphone} title="No requests" /> : (
            <div className="space-y-3">{reqs.map((rq) => (
              <div key={rq.id} className="bg-white border border-slate-200 rounded-xl p-4 flex items-center justify-between"><div><p className="font-medium text-slate-800">{rq.title}</p><p className="text-sm text-slate-500">{rq.message}</p><p className="text-xs text-slate-400 mt-1">by {rq.requested_by}</p></div><StatusBadge status={rq.status} /></div>
            ))}</div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
