import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/auth";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Search, UserPlus, CheckCircle2, Printer, Users } from "lucide-react";

export const EventManage = ({ event, onClose }) => {
  const [data, setData] = useState({ registrations: [], total: 0, checked_in: 0 });
  const [q, setQ] = useState("");
  const [walkin, setWalkin] = useState({ name: "", email: "" });
  const [selected, setSelected] = useState({});

  const load = () => api.get(`/events/${event.id}/registrations${q ? `?q=${q}` : ""}`).then((r) => setData(r.data)).catch(() => {});
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); /* eslint-disable-next-line */ }, [q]);

  const checkin = async (r, val) => { await api.put(`/registrations/${r.id}/checkin`, { checked_in: val }); load(); };
  const addWalkin = async () => { if (!walkin.name) { toast.error("Name required"); return; } await api.post(`/events/${event.id}/registrations`, walkin); setWalkin({ name: "", email: "" }); toast.success("Walk-in checked in"); load(); };

  const printBadges = (regs, size = "4x6") => {
    const dims = { "4x6": "4in 6in", "3x4": "3in 4in", "2.5x3.5": "2.5in 3.5in" }[size] || "4in 6in";
    const html = `<html><head><title>Badges</title><style>
      @page{size:${dims};margin:0}
      .b{width:${dims.split(" ")[0]};height:${dims.split(" ")[1]};box-sizing:border-box;padding:24px;text-align:center;page-break-after:always;display:flex;flex-direction:column;justify-content:center;font-family:Arial}
      .org{color:#2E3192;font-weight:bold;font-size:16px}.cec{color:#D6189B;font-weight:bold}
      .nm{font-size:28px;font-weight:800;margin:16px 0 6px;color:#111}.ev{color:#555;font-size:13px}.st{margin-top:14px;font-size:11px;color:#888}
    </style></head><body>${regs.map((r) => `<div class="b"><div class="org">AAWTA <span class="cec">CEC</span></div><div class="nm">${r.name || ""}</div><div class="ev">${event.name}</div><div class="st">${r.status || "attendee"}</div></div>`).join("")}</body></html>`;
    const w = window.open("", "_blank"); w.document.write(html); w.document.close(); w.focus(); setTimeout(() => w.print(), 400);
  };
  const selectedRegs = data.registrations.filter((r) => selected[r.id]);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Manage — {event.name}</DialogTitle></DialogHeader>
        <div className="flex gap-4 text-sm text-slate-500 mb-2"><span className="flex items-center gap-1"><Users size={14} /> {data.total} registered</span><span className="flex items-center gap-1"><CheckCircle2 size={14} /> {data.checked_in} checked in</span></div>
        <Tabs defaultValue="registrations">
          <TabsList><TabsTrigger value="registrations">Registrations</TabsTrigger><TabsTrigger value="checkin">Check-In</TabsTrigger><TabsTrigger value="badges">Badge Center</TabsTrigger></TabsList>

          <TabsContent value="registrations">
            <div className="relative mb-3"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><Input placeholder="Search attendees…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" data-testid="reg-search" /></div>
            <div className="space-y-1 max-h-72 overflow-y-auto">
              {data.registrations.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-2 border-b border-slate-100 text-sm">
                  <div><p className="font-medium text-slate-800">{r.name}</p><p className="text-xs text-slate-400">{r.email} · {r.status}</p></div>
                  {r.checked_in ? <span className="text-xs text-emerald-600 flex items-center gap-1"><CheckCircle2 size={13} /> In</span> : null}
                </div>
              ))}
              {!data.registrations.length && <p className="text-sm text-slate-400 py-4 text-center">No registrations yet</p>}
            </div>
          </TabsContent>

          <TabsContent value="checkin">
            <div className="bg-slate-50 rounded-lg p-3 mb-3 flex gap-2 items-end">
              <div className="flex-1"><Input placeholder="Walk-in name" value={walkin.name} onChange={(e) => setWalkin((p) => ({ ...p, name: e.target.value }))} data-testid="walkin-name" /></div>
              <div className="flex-1"><Input placeholder="Email (optional)" value={walkin.email} onChange={(e) => setWalkin((p) => ({ ...p, email: e.target.value }))} /></div>
              <Button size="sm" onClick={addWalkin} data-testid="add-walkin-btn" className="bg-brand-navy hover:bg-brand-navy-dark"><UserPlus size={14} className="mr-1" /> Walk-in</Button>
            </div>
            <div className="relative mb-2"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><Input placeholder="Search attendee to check in…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" /></div>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {data.registrations.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-2 border-b border-slate-100 text-sm">
                  <div><p className="font-medium text-slate-800">{r.name}</p><p className="text-xs text-slate-400">{r.status}</p></div>
                  <Button size="sm" variant={r.checked_in ? "outline" : "default"} onClick={() => checkin(r, !r.checked_in)} data-testid={`checkin-${r.id}`} className={r.checked_in ? "text-emerald-600 border-emerald-200" : "bg-brand-magenta hover:bg-brand-pink"}>{r.checked_in ? "Checked In ✓" : "Check In"}</Button>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="badges">
            <p className="text-sm text-slate-500 mb-3">Select attendees to print badges, or print all. Standard 4×6 with preset and custom sizes.</p>
            <div className="flex flex-wrap gap-2 mb-3">
              <Button size="sm" onClick={() => printBadges(data.registrations, "4x6")} data-testid="print-all-badges" className="bg-brand-magenta hover:bg-brand-pink"><Printer size={14} className="mr-1" /> Print All (4×6)</Button>
              <Button size="sm" variant="outline" onClick={() => printBadges(selectedRegs.length ? selectedRegs : data.registrations, "3x4")}><Printer size={14} className="mr-1" /> 3×4</Button>
              <Button size="sm" variant="outline" onClick={() => printBadges(selectedRegs.length ? selectedRegs : data.registrations, "2.5x3.5")}><Printer size={14} className="mr-1" /> 2.5×3.5</Button>
            </div>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {data.registrations.map((r) => (
                <label key={r.id} className="flex items-center gap-2 p-2 border-b border-slate-100 text-sm cursor-pointer">
                  <input type="checkbox" checked={!!selected[r.id]} onChange={(e) => setSelected((p) => ({ ...p, [r.id]: e.target.checked }))} className="accent-[#D6189B]" />
                  <span className="flex-1">{r.name}</span>
                  <Button size="sm" variant="ghost" onClick={(e) => { e.preventDefault(); printBadges([r]); }} data-testid={`badge-${r.id}`}><Printer size={13} /></Button>
                </label>
              ))}
              {!data.registrations.length && <p className="text-sm text-slate-400 py-4 text-center">No attendees to badge yet</p>}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};
