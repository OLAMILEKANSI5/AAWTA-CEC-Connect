import React, { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { printBadges } from "@/components/BadgeCenter";
import { US_STATES_TERRITORIES } from "@/lib/constants";
import { ArrowLeft, Camera, Search, UserPlus, CheckCircle2, Printer, X, QrCode } from "lucide-react";

export default function CheckInCenter() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [event, setEvent] = useState(null);
  const [totals, setTotals] = useState({ total: 0, checked_in: 0 });
  const [q, setQ] = useState("");
  const [rows, setRows] = useState([]);
  const [token, setToken] = useState("");
  const [found, setFound] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [walkinOpen, setWalkinOpen] = useState(false);
  const scannerRef = useRef(null);

  const loadTotals = useCallback(() => {
    api.get(`/events/${id}/registrations`).then((r) => { setTotals({ total: r.data.total, checked_in: r.data.checked_in }); }).catch(() => {});
  }, [id]);
  useEffect(() => { api.get(`/events/${id}`).then((r) => setEvent(r.data)).catch(() => {}); loadTotals(); const t = setInterval(loadTotals, 8000); return () => clearInterval(t); }, [id, loadTotals]);

  useEffect(() => {
    if (!q) { setRows([]); return; }
    const t = setTimeout(() => api.get(`/events/${id}/registrations?q=${encodeURIComponent(q)}`).then((r) => setRows(r.data.registrations)).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [q, id]);

  const resolveToken = async (tok) => {
    try { const { data } = await api.get(`/registrations/lookup?token=${encodeURIComponent(tok)}`); setFound(data); setToken(""); }
    catch (e) { toast.error(e?.response?.data?.detail || "Not found"); }
  };
  const doCheckin = async (regId) => { await api.put(`/registrations/${regId}/checkin`, { checked_in: true, method: "qr" }); toast.success("Checked in"); setFound(null); loadTotals(); if (q) setQ((x) => x); };
  const checkinRow = async (r) => {
    if (r.checked_in) { setFound({ registration: r, already_checked_in: true, checked_in_at: r.checked_in_at, checked_in_by: r.checked_in_by }); return; }
    await api.put(`/registrations/${r.id}/checkin`, { checked_in: true, method: "manual" }); toast.success(`${r.name} checked in`); loadTotals();
    api.get(`/events/${id}/registrations?q=${encodeURIComponent(q)}`).then((res) => setRows(res.data.registrations));
  };
  const printBadge = (r) => printBadges(r, event, { w: 4, h: 6 });

  const startScan = async () => {
    setScanning(true);
    try {
      const { Html5Qrcode } = await import("html5-qrcode");
      const scanner = new Html5Qrcode("qr-reader"); scannerRef.current = scanner;
      await scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 220 }, (text) => { scanner.stop().then(() => { scannerRef.current = null; setScanning(false); resolveToken(text); }); });
    } catch { toast.error("Camera unavailable — use the token field or search"); setScanning(false); }
  };
  const stopScan = async () => { try { await scannerRef.current?.stop(); } catch { /* noop */ } scannerRef.current = null; setScanning(false); };
  useEffect(() => () => { scannerRef.current?.stop?.().catch(() => {}); }, []);

  if (!event) return null;
  const pct = totals.total ? Math.round((totals.checked_in / totals.total) * 100) : 0;

  return (
    <div className="min-h-screen bg-slate-50 pb-24" data-testid="checkin-center">
      <div className="bg-brand-navy-dark text-white px-4 py-4 sticky top-0 z-20">
        <button onClick={() => navigate("/portal/events")} className="text-white/60 text-sm flex items-center gap-1 mb-1"><ArrowLeft size={14} /> Events</button>
        <h1 className="font-head text-xl font-bold truncate">{event.name}</h1>
        <div className="flex items-center gap-4 mt-2">
          <div className="text-2xl font-extrabold text-brand-pink" data-testid="checkin-total">{totals.checked_in}<span className="text-sm text-white/60 font-normal"> / {totals.total} checked in</span></div>
          <div className="flex-1 h-2 bg-white/15 rounded-full overflow-hidden"><div className="h-full bg-brand-pink" style={{ width: `${pct}%` }} /></div>
          <span className="text-sm text-white/70">{pct}%</span>
        </div>
      </div>

      <div className="max-w-md mx-auto px-4 space-y-4 mt-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          {scanning ? (
            <div><div id="qr-reader" className="rounded-lg overflow-hidden" /><Button variant="outline" className="w-full mt-2" onClick={stopScan}><X size={14} className="mr-1" /> Stop camera</Button></div>
          ) : (
            <Button onClick={startScan} data-testid="start-scan-btn" className="w-full bg-brand-magenta hover:bg-brand-pink"><Camera size={16} className="mr-1" /> Scan QR Code</Button>
          )}
          <div className="flex items-center gap-2 mt-3">
            <QrCode size={16} className="text-slate-400" />
            <Input placeholder="Or enter/scan code" value={token} onChange={(e) => setToken(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && token.trim()) resolveToken(token.trim()); }} data-testid="token-input" />
          </div>
        </div>

        <div className="relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><Input placeholder="Search name, email, phone, business, confirmation #" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9 bg-white" data-testid="checkin-search" /></div>

        {rows.map((r) => (
          <div key={r.id} className="bg-white rounded-lg border border-slate-200 p-3 flex items-center justify-between gap-2" data-testid={`checkin-result-${r.id}`}>
            <div className="min-w-0"><p className="font-semibold text-slate-800 truncate">{r.name}</p><p className="text-xs text-slate-400 truncate">{r.email || r.phone || ""} · {r.ticket_category}</p></div>
            <div className="flex items-center gap-1.5 shrink-0">
              <Button size="sm" variant="ghost" onClick={() => printBadge(r)} className="text-brand-navy px-2"><Printer size={15} /></Button>
              {r.checked_in ? <Button size="sm" variant="outline" onClick={() => checkinRow(r)} data-testid={`checkin-btn-${r.id}`} className="text-emerald-600 border-emerald-200"><CheckCircle2 size={14} className="mr-1" /> In</Button>
                : <Button size="sm" onClick={() => checkinRow(r)} data-testid={`checkin-btn-${r.id}`} className="bg-brand-magenta hover:bg-brand-pink">Check In</Button>}
            </div>
          </div>
        ))}
        {q && !rows.length && <p className="text-center text-sm text-slate-400">No matches</p>}

        <Button variant="outline" className="w-full" onClick={() => setWalkinOpen(true)} data-testid="open-walkin-btn"><UserPlus size={15} className="mr-1" /> Register Walk-In</Button>
      </div>

      {found && <FoundDialog data={found} onClose={() => setFound(null)} onCheckin={doCheckin} onPrint={printBadge} />}
      {walkinOpen && <WalkinDialog eventId={id} event={event} onClose={() => setWalkinOpen(false)} onDone={loadTotals} onPrint={printBadge} />}
    </div>
  );
}

const FoundDialog = ({ data, onClose, onCheckin, onPrint }) => {
  const r = data.registration;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm" data-testid="found-dialog">
        <DialogHeader><DialogTitle>{r.name}</DialogTitle></DialogHeader>
        <div className="text-sm text-slate-600 space-y-1">
          <p>{r.email || r.phone} · {r.ticket_category}</p>
          <p className="font-mono text-xs">{r.confirmation_number}</p>
          {data.already_checked_in && (
            <div className="mt-2 bg-amber-50 border border-amber-200 rounded-md p-2 text-amber-700 text-xs" data-testid="already-checked-in">
              <strong>Already Checked In</strong><br />
              {data.checked_in_at ? new Date(data.checked_in_at).toLocaleString() : ""}{data.checked_in_by ? ` · by ${data.checked_in_by}` : ""}
            </div>
          )}
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onPrint(r)}><Printer size={14} className="mr-1" /> Badge</Button>
          {data.already_checked_in
            ? <Button onClick={() => onCheckin(r.id)} data-testid="confirm-recheckin" className="bg-amber-600 hover:bg-amber-700">Check In Again</Button>
            : <Button onClick={() => onCheckin(r.id)} data-testid="confirm-checkin" className="bg-brand-magenta hover:bg-brand-pink">Check In</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const WalkinDialog = ({ eventId, event, onClose, onDone, onPrint }) => {
  const [f, setF] = useState({ member_status: "Unknown", ticket_category: (event.ticket_categories || ["General Admission"])[0] });
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    if (!f.first_name) { toast.error("First name required"); return; }
    if (!f.email && !f.phone) { toast.error("Email or phone required"); return; }
    try { const { data } = await api.post(`/events/${eventId}/registrations`, f); toast.success("Walk-in checked in"); onDone(); onClose(); onPrint(data); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm" data-testid="walkin-dialog">
        <DialogHeader><DialogTitle>Register Walk-In</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-2">
          <Input placeholder="First name *" value={f.first_name || ""} onChange={(e) => on("first_name", e.target.value)} data-testid="wi-first" />
          <Input placeholder="Last name" value={f.last_name || ""} onChange={(e) => on("last_name", e.target.value)} data-testid="wi-last" />
          <Input placeholder="Email" value={f.email || ""} onChange={(e) => on("email", e.target.value)} data-testid="wi-email" />
          <Input placeholder="Phone" value={f.phone || ""} onChange={(e) => on("phone", e.target.value)} data-testid="wi-phone" />
          <select value={f.state || ""} onChange={(e) => on("state", e.target.value)} className="h-10 rounded-md border border-input bg-background px-2 text-sm"><option value="">State…</option>{US_STATES_TERRITORIES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
          <select value={f.member_status} onChange={(e) => on("member_status", e.target.value)} className="h-10 rounded-md border border-input bg-background px-2 text-sm">{["Unknown", "Yes", "No"].map((s) => <option key={s} value={s}>{`Member: ${s}`}</option>)}</select>
        </div>
        <DialogFooter><Button onClick={save} data-testid="wi-save" className="bg-brand-magenta hover:bg-brand-pink">Register & Check In</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
