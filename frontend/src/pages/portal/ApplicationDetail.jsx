import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Download, Clock, StickyNote, UserPlus, CheckCircle2 } from "lucide-react";
import { api, API, useAuth } from "@/auth";
import { PageTitle, StatusBadge, Loading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { APP_STATUSES } from "@/lib/constants";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { CommsPanel } from "@/components/CommsPanel";

const LEADERSHIP = ["super_admin", "director"];

export default function ApplicationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [a, setA] = useState(null);
  const [note, setNote] = useState("");
  const [vis, setVis] = useState("leadership");

  const load = () => api.get(`/applications/${id}`).then((r) => setA(r.data)).catch(() => toast.error("Not found"));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  const setStatus = async (status) => { await api.put(`/applications/${id}/status`, { status }); toast.success(`Status: ${status}`); load(); };
  const addNote = async () => { if (!note.trim()) return; await api.post(`/applications/${id}/notes`, { text: note, visibility: vis }); setNote(""); toast.success("Note added"); load(); };
  const convert = async () => { const r = await api.post(`/applications/${id}/convert`); toast.success("Converted to member"); navigate(`/portal/members/${r.data.id}`); };
  const approveOnboard = async () => {
    try { const r = await api.post(`/applications/${id}/approve-onboard`); toast.success("Approved & onboarding started"); navigate(`/portal/members/${r.data.member_id}`); }
    catch (e) { toast.error(e?.response?.data?.detail || "Could not onboard"); }
  };

  if (!a) return <Loading />;
  const d = a.data || {};
  const fileKeys = Object.keys(d).filter((k) => d[k] && typeof d[k] === "object" && d[k].id);

  return (
    <div className="space-y-5">
      <Button variant="ghost" onClick={() => navigate("/portal/applications")} className="text-slate-500"><ArrowLeft size={16} className="mr-1" /> Back</Button>
      <PageTitle title={a.name} subtitle={`${a.ref} · ${a.type} · ${a.email}`} action={<StatusBadge status={a.status} />} />

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-5">
          <Tabs defaultValue="answers">
            <TabsList><TabsTrigger value="answers">Answers</TabsTrigger><TabsTrigger value="files">Files ({fileKeys.length})</TabsTrigger><TabsTrigger value="notes">Notes ({a.notes?.length || 0})</TabsTrigger><TabsTrigger value="comms" data-testid="tab-comms">Communications</TabsTrigger><TabsTrigger value="timeline">Timeline</TabsTrigger></TabsList>
            <TabsContent value="answers">
              <div className="bg-white border border-slate-200 rounded-xl p-5 grid sm:grid-cols-2 gap-x-6 gap-y-3">
                {Object.entries(d).filter(([, v]) => v && typeof v !== "object").map(([k, v]) => (
                  <div key={k}><div className="text-xs uppercase text-slate-400">{k.replace(/_/g, " ")}</div><div className="text-sm text-slate-800">{String(v)}</div></div>
                ))}
                {Array.isArray(d.areas_of_interest) && d.areas_of_interest.length > 0 && (
                  <div className="sm:col-span-2"><div className="text-xs uppercase text-slate-400 mb-1">Areas of interest</div><div className="flex flex-wrap gap-1.5">{d.areas_of_interest.map((f) => <span key={f} className="text-xs px-2 py-0.5 bg-brand-magenta/10 text-brand-magenta rounded-full">{f}</span>)}</div></div>
                )}
              </div>
            </TabsContent>
            <TabsContent value="files">
              <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-2">
                {fileKeys.length === 0 ? <p className="text-sm text-slate-400">No files attached</p> : fileKeys.map((k) => (
                  <a key={k} href={`${API}/files/${d[k].id}/download`} target="_blank" rel="noreferrer" className="flex items-center justify-between p-2.5 rounded-lg border border-slate-100 hover:bg-slate-50">
                    <span className="text-sm text-slate-700">{k.replace(/_/g, " ")}: {d[k].filename}</span><Download size={16} className="text-brand-magenta" />
                  </a>
                ))}
              </div>
            </TabsContent>
            <TabsContent value="notes">
              <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
                <div className="flex gap-2">
                  <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add an internal note…" rows={2} data-testid="note-input" className="flex-1 rounded-md border border-input px-3 py-2 text-sm" />
                </div>
                <div className="flex items-center gap-2">
                  <select value={vis} onChange={(e) => setVis(e.target.value)} className="rounded-md border border-input px-2 py-1.5 text-sm"><option value="leadership">Leadership only</option><option value="shared_member">Shared with member</option><option value="shared_team">Shared with team</option></select>
                  <Button size="sm" onClick={addNote} data-testid="add-note-btn" className="bg-brand-magenta hover:bg-brand-pink">Add Note</Button>
                </div>
                <div className="space-y-2">
                  {a.notes?.map((n) => (
                    <div key={n.id} className="p-3 bg-slate-50 rounded-lg"><div className="flex items-center justify-between text-xs text-slate-400"><span>{n.author} · {n.visibility}</span><span>{new Date(n.created_at).toLocaleString()}</span></div><p className="text-sm text-slate-700 mt-1">{n.text}</p></div>
                  ))}
                </div>
              </div>
            </TabsContent>
            <TabsContent value="comms">
              <CommsPanel subjectType="application" subjectId={id} />
            </TabsContent>
            <TabsContent value="timeline">
              <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
                {a.timeline?.map((t) => (
                  <div key={t.id} className="flex gap-3"><Clock size={16} className="text-brand-magenta shrink-0 mt-0.5" /><div><p className="text-sm text-slate-700">{t.event}</p><p className="text-xs text-slate-400">{t.actor} · {new Date(t.created_at).toLocaleString()}</p></div></div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>

        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-head font-semibold text-brand-navy mb-3">Update Status</h3>
            <select data-testid="status-select" value={a.status} onChange={(e) => setStatus(e.target.value)} className="w-full rounded-md border border-input px-3 py-2 text-sm">
              {APP_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            {a.type !== "inquiry" && a.status !== "Converted to Member" && !a.member_id && LEADERSHIP.includes(user?.role) && (
              <Button onClick={approveOnboard} data-testid="approve-onboard-btn" className="w-full mt-3 rounded-full bg-brand-magenta hover:bg-brand-pink"><CheckCircle2 size={16} className="mr-1" /> Approve &amp; Onboard</Button>
            )}
            {["Approved", "Recommended"].includes(a.status) && a.type !== "inquiry" && LEADERSHIP.includes(user?.role) && (
              <Button onClick={convert} data-testid="convert-btn" className="w-full mt-3 rounded-full bg-emerald-600 hover:bg-emerald-700"><UserPlus size={16} className="mr-1" /> Convert to Member</Button>
            )}
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-head font-semibold text-brand-navy mb-3">Decision History</h3>
            {a.decision_history?.length ? a.decision_history.map((h, i) => (
              <div key={i} className="text-sm border-b last:border-0 border-slate-100 py-2"><div className="flex items-center gap-2"><CheckCircle2 size={14} className="text-brand-magenta" /> {h.status}</div><p className="text-xs text-slate-400">{h.by} · {new Date(h.at).toLocaleDateString()}</p></div>
            )) : <p className="text-sm text-slate-400">No decisions yet</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
