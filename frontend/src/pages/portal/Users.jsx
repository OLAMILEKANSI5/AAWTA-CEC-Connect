import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { ShieldCheck, Plus } from "lucide-react";
import { api, useAuth } from "@/auth";
import { PageTitle, Loading, StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Field, SelectField } from "@/components/FormFields";
import { ROLE_LABELS } from "@/lib/constants";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export default function Users() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ role: "administrator", notify_directors: false });
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = () => api.get("/users").then((r) => setData(r.data)).catch(() => setData({ users: [], authorized: [] }));
  useEffect(() => { load(); }, []);

  const authorize = async () => { if (!f.email) { toast.error("Email required"); return; } try { await api.post("/authorized-emails", f); toast.success("Email authorized"); setOpen(false); setF({ role: "administrator", notify_directors: false }); load(); } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } };
  const setStatus = async (email, status) => { await api.put(`/authorized-emails/${encodeURIComponent(email)}/status`, { status }); toast.success(status); load(); };
  const setRole = async (uid, role) => { await api.put(`/users/${uid}/role`, { role }); toast.success("Role updated"); load(); };

  if (data === null) return <Loading />;
  const canManageRoles = user?.role === "super_admin";

  return (
    <div className="space-y-5">
      <PageTitle title="User Management" subtitle="Authorized accounts, roles & permissions" action={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="authorize-email-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink"><Plus size={16} className="mr-1" /> Authorize Email</Button></DialogTrigger>
          <DialogContent><DialogHeader><DialogTitle>Authorize a Google Account</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <Field label="Google email" name="email" type="email" value={f.email} onChange={on} required />
              <SelectField label="Role" name="role" value={f.role} onChange={on} options={["director", "administrator", "ambassador", "volunteer"]} />
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.notify_directors} onChange={(e) => on("notify_directors", e.target.checked)} className="accent-[#D6189B]" /> Receive Director-level notifications</label>
            </div>
            <DialogFooter><Button onClick={authorize} data-testid="save-authorize-btn" className="bg-brand-magenta hover:bg-brand-pink">Authorize</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      } />

      <Tabs defaultValue="authorized">
        <TabsList><TabsTrigger value="authorized">Authorized Emails ({data.authorized.length})</TabsTrigger><TabsTrigger value="active">Active Users ({data.users.length})</TabsTrigger></TabsList>
        <TabsContent value="authorized">
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
            <table className="w-full text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="text-left p-3">Email</th><th className="text-left p-3">Role</th><th className="text-left p-3">Status</th><th className="text-left p-3">Actions</th></tr></thead>
              <tbody>{data.authorized.map((a) => (
                <tr key={a.email} className="border-t border-slate-100" data-testid={`auth-row-${a.email}`}>
                  <td className="p-3 text-slate-700">{a.email}</td><td className="p-3">{ROLE_LABELS[a.role]}</td><td className="p-3"><StatusBadge status={a.status} /></td>
                  <td className="p-3">{a.email !== user?.email && (a.status === "active" ? <Button size="sm" variant="outline" className="text-rose-600 border-rose-200" onClick={() => setStatus(a.email, "suspended")}>Suspend</Button> : <Button size="sm" variant="outline" className="text-emerald-600 border-emerald-200" onClick={() => setStatus(a.email, "active")}>Restore</Button>)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </TabsContent>
        <TabsContent value="active">
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden overflow-x-auto">
            <table className="w-full text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="text-left p-3">Name</th><th className="text-left p-3">Email</th><th className="text-left p-3">Role</th><th className="text-left p-3">Last login</th></tr></thead>
              <tbody>{data.users.map((u) => (
                <tr key={u.user_id} className="border-t border-slate-100"><td className="p-3 text-slate-700">{u.name}</td><td className="p-3 text-slate-500">{u.email}</td>
                  <td className="p-3">{canManageRoles && u.email !== user?.email ? <select value={u.role} onChange={(e) => setRole(u.user_id, e.target.value)} className="rounded-md border border-input px-2 py-1 text-xs" data-testid={`role-select-${u.user_id}`}>{Object.keys(ROLE_LABELS).map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}</select> : ROLE_LABELS[u.role]}</td>
                  <td className="p-3 text-slate-400 text-xs">{u.last_login ? new Date(u.last_login).toLocaleString() : "—"}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
