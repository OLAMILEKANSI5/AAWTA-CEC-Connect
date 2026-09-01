import React, { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Printer, UserPlus, X } from "lucide-react";

const PRESETS = [
  { key: "4x6", label: "4 × 6 in", w: 4, h: 6 },
  { key: "3x4", label: "3 × 4 in", w: 3, h: 4 },
  { key: "2.5x3.5", label: "2.5 × 3.5 in", w: 2.5, h: 3.5 },
  { key: "4x3", label: "4 × 3 in", w: 4, h: 3 },
  { key: "custom", label: "Custom", w: 4, h: 6 },
];

const fmtDate = (s) => (s ? new Date(s + "T00:00").toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" }) : "");
const roleLabel = (st) => ({ registered: "Attendee", checked_in: "Attendee", walkin: "Walk-In", waitlist: "Waitlist", guest: "Guest", staff: "Staff", speaker: "Speaker", volunteer: "Volunteer" }[st] || "Attendee");

const badgeMarkup = (r, event, w, h) => `
  <div class="badge" style="width:${w}in;height:${h}in;">
    <div class="bar"></div>
    <div class="body">
      <div class="org">AAWTA <span class="cec">CEC</span></div>
      <div class="tag">Community Engagement Committee</div>
      <div class="nm">${(r.name || "").replace(/</g, "&lt;")}</div>
      <div class="role">${roleLabel(r.status)}</div>
      <div class="spacer"></div>
      <div class="ev">${(event.name || "").replace(/</g, "&lt;")}</div>
      <div class="dt">${fmtDate(event.date)}${event.city ? " · " + event.city : ""}</div>
    </div>
    <div class="footfoot"></div>
  </div>`;

const badgeCss = (w, h) => `
  @page { size: ${w}in ${h}in; margin: 0; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { margin: 0; font-family: 'Helvetica Neue', Arial, sans-serif; }
  .badge { box-sizing: border-box; page-break-after: always; display:flex; flex-direction:column; overflow:hidden; border:1px solid #eee; }
  .bar { height: ${Math.max(0.18 * h, 0.5)}in; background: #2E3192; flex-shrink:0; }
  .body { flex:1; display:flex; flex-direction:column; align-items:center; text-align:center; padding: 0.2in 0.18in; }
  .org { color:#2E3192; font-weight:800; letter-spacing:1px; margin-top:0.12in; font-size:${Math.max(0.16 * w, 0.5)}in; }
  .cec { color:#D6189B; }
  .tag { color:#94a3b8; font-size:${0.05 * w}in; letter-spacing:0.5px; text-transform:uppercase; margin-top:2px; }
  .nm { color:#0f172a; font-weight:800; line-height:1.05; margin-top:auto; font-size:${Math.max(0.22 * w, 0.6)}in; word-break:break-word; }
  .role { display:inline-block; margin-top:0.1in; background:#D6189B; color:#fff; font-weight:700; border-radius:999px; padding:0.03in 0.16in; font-size:${0.06 * w}in; text-transform:uppercase; letter-spacing:0.5px; }
  .spacer { flex:1; }
  .ev { color:#334155; font-weight:600; font-size:${0.075 * w}in; margin-bottom:2px; }
  .dt { color:#64748b; font-size:${0.06 * w}in; }
  .footfoot { height:${0.06 * h}in; background:#D6189B; flex-shrink:0; }`;

export const BadgeCenter = ({ event, registrations }) => {
  const [sizeKey, setSizeKey] = useState("4x6");
  const [cw, setCw] = useState(4);
  const [ch, setCh] = useState(6);
  const [selected, setSelected] = useState({});
  const [manual, setManual] = useState([]);
  const [mName, setMName] = useState("");
  const [mRole, setMRole] = useState("guest");
  const [previewId, setPreviewId] = useState(null);

  const preset = PRESETS.find((p) => p.key === sizeKey) || PRESETS[0];
  const w = sizeKey === "custom" ? Number(cw) || 4 : preset.w;
  const h = sizeKey === "custom" ? Number(ch) || 6 : preset.h;

  const all = useMemo(() => [...registrations, ...manual], [registrations, manual]);
  const selectedRegs = all.filter((r) => selected[r.id]);
  const previewReg = all.find((r) => r.id === previewId) || all[0] || { name: "Attendee Name", status: "registered" };

  const print = (regs) => {
    if (!regs.length) { toast.error("No attendees to print"); return; }
    const html = `<html><head><title>${event.name} — Badges</title><style>${badgeCss(w, h)}</style></head><body>${regs.map((r) => badgeMarkup(r, event, w, h)).join("")}</body></html>`;
    const win = window.open("", "_blank");
    if (!win) { toast.error("Popup blocked — allow popups to print badges"); return; }
    win.document.write(html); win.document.close(); win.focus();
    setTimeout(() => win.print(), 400);
  };

  const addManual = () => {
    if (!mName.trim()) { toast.error("Name required"); return; }
    const entry = { id: `manual_${Date.now()}`, name: mName.trim(), status: mRole, manual: true };
    setManual((p) => [...p, entry]);
    setPreviewId(entry.id); setMName("");
  };

  // Live preview scaled to fit ~190px wide
  const scale = 190 / (w * 96);
  const pxW = w * 96, pxH = h * 96;

  return (
    <div className="grid md:grid-cols-2 gap-5" data-testid="badge-center">
      <div>
        <p className="text-sm font-semibold text-brand-navy mb-2">Badge size</p>
        <div className="flex flex-wrap gap-2 mb-3">
          {PRESETS.map((p) => (
            <button key={p.key} onClick={() => setSizeKey(p.key)} data-testid={`badge-size-${p.key}`} className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${sizeKey === p.key ? "bg-brand-magenta text-white border-brand-magenta" : "bg-white text-slate-600 border-slate-200 hover:border-brand-magenta"}`}>{p.label}</button>
          ))}
        </div>
        {sizeKey === "custom" && (
          <div className="flex items-end gap-2 mb-3">
            <div><label className="text-xs text-slate-500">Width (in)</label><Input type="number" min="1" step="0.25" value={cw} onChange={(e) => setCw(e.target.value)} data-testid="badge-custom-w" className="h-8 w-24" /></div>
            <div><label className="text-xs text-slate-500">Height (in)</label><Input type="number" min="1" step="0.25" value={ch} onChange={(e) => setCh(e.target.value)} data-testid="badge-custom-h" className="h-8 w-24" /></div>
          </div>
        )}

        <p className="text-sm font-semibold text-brand-navy mb-2 mt-4">Add badge manually</p>
        <div className="flex items-end gap-2 mb-3">
          <div className="flex-1"><Input placeholder="Full name" value={mName} onChange={(e) => setMName(e.target.value)} data-testid="badge-manual-name" className="h-8" /></div>
          <select value={mRole} onChange={(e) => setMRole(e.target.value)} data-testid="badge-manual-role" className="h-8 rounded-md border border-input px-2 text-sm bg-background">
            {["guest", "speaker", "staff", "volunteer"].map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}
          </select>
          <Button size="sm" onClick={addManual} data-testid="badge-add-manual" className="h-8 bg-brand-navy hover:bg-brand-navy-dark"><UserPlus size={14} /></Button>
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          <Button size="sm" onClick={() => print(all)} data-testid="print-all-badges" className="bg-brand-magenta hover:bg-brand-pink"><Printer size={14} className="mr-1" /> Print All ({all.length})</Button>
          <Button size="sm" variant="outline" disabled={!selectedRegs.length} onClick={() => print(selectedRegs)} data-testid="print-selected-badges"><Printer size={14} className="mr-1" /> Print Selected ({selectedRegs.length})</Button>
        </div>

        <div className="space-y-1 max-h-56 overflow-y-auto border-t border-slate-100 pt-2">
          {all.map((r) => (
            <div key={r.id} className={`flex items-center gap-2 p-2 rounded-md text-sm cursor-pointer ${previewId === r.id ? "bg-brand-magenta/5" : ""}`} onClick={() => setPreviewId(r.id)}>
              <input type="checkbox" checked={!!selected[r.id]} onClick={(e) => e.stopPropagation()} onChange={(e) => setSelected((p) => ({ ...p, [r.id]: e.target.checked }))} className="accent-[#D6189B]" data-testid={`badge-select-${r.id}`} />
              <span className="flex-1 truncate">{r.name} <span className="text-xs text-slate-400">· {roleLabel(r.status)}</span></span>
              {r.manual && <button onClick={(e) => { e.stopPropagation(); setManual((p) => p.filter((x) => x.id !== r.id)); }}><X size={13} className="text-slate-400 hover:text-rose-500" /></button>}
              <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); print([r]); }} data-testid={`badge-${r.id}`}><Printer size={13} /></Button>
            </div>
          ))}
          {!all.length && <p className="text-sm text-slate-400 py-4 text-center">No attendees to badge yet — register attendees or add one manually.</p>}
        </div>
      </div>

      <div className="flex flex-col items-center">
        <p className="text-sm font-semibold text-brand-navy mb-3 self-start">Live preview</p>
        <div className="bg-slate-100 rounded-xl p-4 flex items-center justify-center" style={{ minHeight: 300 }} data-testid="badge-preview">
          <div style={{ width: pxW * scale, height: pxH * scale }}>
            <div style={{ width: pxW, height: pxH, transform: `scale(${scale})`, transformOrigin: "top left", boxShadow: "0 8px 30px rgba(0,0,0,0.15)", borderRadius: 8, overflow: "hidden", display: "flex", flexDirection: "column", background: "#fff" }}>
              <div style={{ height: pxH * 0.14, background: "#2E3192" }} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: pxW * 0.05 }}>
                <div style={{ color: "#2E3192", fontWeight: 800, letterSpacing: 1, fontSize: pxW * 0.11, marginTop: pxH * 0.02 }}>AAWTA <span style={{ color: "#D6189B" }}>CEC</span></div>
                <div style={{ color: "#94a3b8", fontSize: pxW * 0.04, letterSpacing: 0.5, textTransform: "uppercase", marginTop: 4 }}>Community Engagement Committee</div>
                <div style={{ color: "#0f172a", fontWeight: 800, lineHeight: 1.05, marginTop: "auto", fontSize: pxW * 0.15, wordBreak: "break-word", padding: "0 8px" }}>{previewReg.name}</div>
                <div style={{ marginTop: pxH * 0.02, background: "#D6189B", color: "#fff", fontWeight: 700, borderRadius: 999, padding: `${pxH * 0.008}px ${pxW * 0.06}px`, fontSize: pxW * 0.05, textTransform: "uppercase", letterSpacing: 0.5 }}>{roleLabel(previewReg.status)}</div>
                <div style={{ flex: 1 }} />
                <div style={{ color: "#334155", fontWeight: 600, fontSize: pxW * 0.06 }}>{event.name}</div>
                <div style={{ color: "#64748b", fontSize: pxW * 0.05, marginTop: 2 }}>{fmtDate(event.date)}{event.city ? ` · ${event.city}` : ""}</div>
              </div>
              <div style={{ height: pxH * 0.05, background: "#D6189B" }} />
            </div>
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-3">Printing at {w} × {h} in</p>
      </div>
    </div>
  );
};
