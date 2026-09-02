import React, { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { api, API } from "@/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { Field, SelectField, Consent } from "@/components/FormFields";
import { printBadges } from "@/components/BadgeCenter";
import { PAYMENT_STATUSES, PAYMENT_LABELS, PAYMENT_COLORS, BADGE_CATEGORIES, US_STATES_TERRITORIES } from "@/lib/constants";
import { Search, MoreHorizontal, UserPlus, Printer, RefreshCw, X, Filter, Upload, Download } from "lucide-react";

const SOURCES = ["online", "Manual Entry", "Walk-In", "Bulk Import"];
const IMPORT_FIELDS = ["first_name", "last_name", "email", "phone", "state", "city", "zip_code", "member_status", "business_name", "business_website", "job_title", "ticket_category", "payment_status", "badge_category", "newsletter_opt_in", "events_opt_in", "internal_notes", "confirmation_number"];
const EXPORT_FIELDS = ["name", "email", "phone", "state", "city", "member_status", "business_name", "business_website", "job_title", "ticket_category", "source", "confirmation_number", "payment_status", "confirmation_status", "checked_in", "checked_in_at", "badge_status", "newsletter_opt_in", "events_opt_in", "created_at"];
const SEGMENTS = [["all", "All registrations"], ["checked_in", "Checked-in"], ["not_checked_in", "Not checked-in"], ["walkins", "Walk-ins"], ["manual", "Manual"], ["online", "Online"], ["imported", "Imported"], ["members", "Members"], ["nonmembers", "Non-members"], ["newsletter", "Newsletter subscribers"], ["events", "Event subscribers"]];
const BULK = [["send_confirmation", "Send Confirmation", true], ["resend_confirmation", "Resend Confirmation", true], ["change_category", "Change Category"], ["assign_badge_category", "Assign Badge Category"], ["mark_complimentary", "Mark Complimentary"], ["update_payment", "Update Payment Status"], ["checkin", "Check In"], ["cancel", "Cancel Registrations"], ["archive", "Archive Registrations"], ["__print", "Generate / Print Badges"], ["__export", "Export Selected"]];
const confColor = (s) => ({ sent: "text-emerald-600", delivered: "text-emerald-600", opened: "text-emerald-600", failed: "text-rose-600", bounced: "text-rose-600", pending: "text-amber-600", unsubscribed: "text-slate-400" }[s] || "text-slate-400");
const cell = "px-2.5 py-2 whitespace-nowrap";

export const RegistrationTable = ({ event, onMutate }) => {
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({ total: 0, filtered: 0, checked_in: 0 });
  const [q, setQ] = useState("");
  const [flt, setFlt] = useState({});
  const [showFilters, setShowFilters] = useState(false);
  const [sel, setSel] = useState({});
  const [manual, setManual] = useState(false);
  const [edit, setEdit] = useState(null);
  const [view, setView] = useState(null);
  const [history, setHistory] = useState(null);
  const [cat, setCat] = useState(null);
  const [imp, setImp] = useState(false);
  const [exp, setExp] = useState(null);
  const [bulk, setBulk] = useState(null);

  const load = useCallback(() => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    Object.entries(flt).forEach(([k, v]) => { if (v) p.set(k, v); });
    api.get(`/events/${event.id}/registrations?${p}`).then((r) => { setRows(r.data.registrations); setCounts(r.data); }).catch(() => {});
  }, [q, flt, event.id]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const refresh = () => { load(); onMutate && onMutate(); };
  const cats = (event.ticket_categories && event.ticket_categories.length) ? event.ticket_categories : ["General Admission"];

  const doCheckin = async (r, val) => { try { await api.put(`/registrations/${r.id}/checkin`, { checked_in: val }); toast.success(val ? "Checked in" : "Check-in undone"); refresh(); } catch { toast.error("Failed"); } };
  const doResend = async (r) => { try { const { data } = await api.post(`/registrations/${r.id}/resend-confirmation`); (["failed", "bounced"].includes(data.status) ? toast.error(`Confirmation ${data.status}`) : toast.success(`Confirmation ${data.status}`)); refresh(); } catch { toast.error("Resend failed"); } };
  const doSend = async (r) => { try { const { data } = await api.post(`/registrations/${r.id}/send-confirmation`); (["failed", "bounced"].includes(data.status) ? toast.error(`Confirmation ${data.status}`) : toast.success(`Confirmation ${data.status}`)); refresh(); } catch { toast.error("Send failed"); } };
  const doPayment = async (r, ps) => { try { await api.put(`/registrations/${r.id}/payment`, { payment_status: ps }); toast.success("Payment updated"); refresh(); } catch { toast.error("Failed"); } };
  const doCancel = async (r) => { if (!window.confirm(`Cancel registration for ${r.name}?`)) return; try { await api.post(`/registrations/${r.id}/cancel`); toast.success("Cancelled"); refresh(); } catch { toast.error("Failed"); } };
  const doArchive = async (r) => { try { await api.put(`/registrations/${r.id}/archive`, { archived: !r.archived }); toast.success(r.archived ? "Unarchived" : "Archived"); refresh(); } catch { toast.error("Failed"); } };
  const doPrint = async (r) => { if (printBadges(r, event, { w: 4, h: 6 })) { await api.post(`/registrations/${r.id}/badge-printed`).catch(() => {}); refresh(); } };
  const runBulk = async (action, value) => {
    const ids = Object.keys(sel).filter((k) => sel[k]);
    if (action === "__print") { printBadges(rows.filter((r) => sel[r.id]), event, { w: 4, h: 6 }); setBulk(null); return; }
    if (action === "__export") { setExp({ ids }); setBulk(null); return; }
    try { const { data } = await api.post(`/events/${event.id}/bulk`, { action, ids, value }); toast.success(`${data.affected} updated`); setSel({}); setBulk(null); refresh(); } catch { toast.error("Bulk action failed"); }
  };

  const selIds = Object.keys(sel).filter((k) => sel[k]);
  const allChecked = rows.length > 0 && rows.every((r) => sel[r.id]);

  return (
    <div data-testid="registration-table" className="min-w-0 w-full">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="relative flex-1 min-w-[200px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><Input placeholder="Search name, email, phone, business, confirmation #…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" data-testid="reg-search" /></div>
        <Button size="sm" variant="outline" onClick={() => setShowFilters((s) => !s)} data-testid="toggle-filters"><Filter size={14} className="mr-1" /> Filters</Button>
        <Button size="sm" variant="outline" onClick={() => setImp(true)} data-testid="import-btn"><Upload size={14} className="mr-1" /> Import</Button>
        <Button size="sm" variant="outline" onClick={() => setExp({})} data-testid="export-btn"><Download size={14} className="mr-1" /> Export</Button>
        <Button size="sm" onClick={() => setManual(true)} data-testid="add-manual-btn" className="bg-brand-navy hover:bg-brand-navy-dark"><UserPlus size={14} className="mr-1" /> Add Manual Registration</Button>
      </div>
      {showFilters && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3 bg-slate-50 rounded-lg p-3">
          <FS label="State" v={flt.state} on={(v) => setFlt((p) => ({ ...p, state: v }))} opts={US_STATES_TERRITORIES} />
          <FS label="Member" v={flt.member} on={(v) => setFlt((p) => ({ ...p, member: v }))} opts={[["yes", "Member"], ["no", "Non-member"]]} />
          <FS label="Category" v={flt.category} on={(v) => setFlt((p) => ({ ...p, category: v }))} opts={cats} />
          <FS label="Source" v={flt.source} on={(v) => setFlt((p) => ({ ...p, source: v }))} opts={SOURCES.map((s) => [s, s === "online" ? "Online" : s])} />
          <FS label="Payment" v={flt.payment} on={(v) => setFlt((p) => ({ ...p, payment: v }))} opts={PAYMENT_STATUSES.map((s) => [s, PAYMENT_LABELS[s]])} />
          <FS label="Confirmation" v={flt.confirmation} on={(v) => setFlt((p) => ({ ...p, confirmation: v }))} opts={[["sent", "Sent"], ["delivered", "Delivered"], ["opened", "Opened"], ["failed", "Failed"], ["bounced", "Bounced"], ["not_sent", "Not sent"]]} />
          <FS label="Check-in" v={flt.checkin} on={(v) => setFlt((p) => ({ ...p, checkin: v }))} opts={[["in", "Checked in"], ["out", "Not checked in"]]} />
          <FS label="Badge" v={flt.badge} on={(v) => setFlt((p) => ({ ...p, badge: v }))} opts={[["printed", "Printed"]]} />
          <label className="flex items-center gap-2 text-xs text-slate-600 self-end cursor-pointer"><input type="checkbox" checked={flt.include_archived === "true"} onChange={(e) => setFlt((p) => ({ ...p, include_archived: e.target.checked ? "true" : "" }))} data-testid="show-archived" className="accent-[#D6189B]" /> Show archived</label>
          <button className="text-xs text-brand-magenta self-end" onClick={() => { setFlt({}); }} data-testid="clear-filters">Clear all</button>
        </div>
      )}
      <p className="text-xs text-slate-400 mb-2">{counts.filtered} of {counts.total} · {counts.checked_in} checked in{selIds.length ? ` · ${selIds.length} selected` : ""}</p>
      {selIds.length > 0 && (
        <div className="flex items-center gap-2 mb-2 bg-brand-magenta/5 border border-brand-magenta/20 rounded-lg px-3 py-2" data-testid="bulk-bar">
          <span className="text-sm font-medium text-brand-navy">{selIds.length} selected</span>
          <select onChange={(e) => { if (e.target.value) { setBulk(e.target.value); e.target.value = ""; } }} data-testid="bulk-action-select" className="h-8 rounded-md border border-input bg-background px-2 text-sm ml-auto">
            <option value="">Bulk action…</option>
            {BULK.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <button onClick={() => setSel({})} className="text-xs text-slate-400 hover:text-slate-600">Clear</button>
        </div>
      )}

      <div className="overflow-x-auto border border-slate-100 rounded-lg max-h-[55vh] overflow-y-auto">
        <table className="min-w-[1400px] w-full text-xs">
          <thead className="bg-slate-50 sticky top-0 z-10 text-slate-500 text-left">
            <tr>
              <th className={cell}><input type="checkbox" checked={allChecked} onChange={(e) => setSel(e.target.checked ? Object.fromEntries(rows.map((r) => [r.id, true])) : {})} data-testid="select-all" /></th>
              {["Name", "Member", "State", "Business", "Website", "Email", "Phone", "Category", "Source", "Confirmation #", "Payment", "Confirmation", "Check-in", "Check-in time", "Badge", "Print", "Actions"].map((h) => <th key={h} className={cell}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className={`border-t border-slate-100 ${r.status === "cancelled" ? "opacity-50" : ""} ${r.archived ? "bg-slate-50" : ""}`} data-testid={`reg-row-${r.id}`}>
                <td className={cell}><input type="checkbox" checked={!!sel[r.id]} onChange={(e) => setSel((p) => ({ ...p, [r.id]: e.target.checked }))} data-testid={`select-${r.id}`} /></td>
                <td className={`${cell} font-medium text-slate-800`}>{r.name}{r.status === "cancelled" && <span className="ml-1 text-rose-500">(cancelled)</span>}</td>
                <td className={cell}>{r.is_member ? "Member" : (r.member_status || "No")}</td>
                <td className={cell}>{r.state || "—"}</td>
                <td className={cell}>{r.business_name || "—"}</td>
                <td className={cell}>{r.business_website ? <a href={r.business_website} target="_blank" rel="noopener noreferrer" className="text-brand-magenta underline">link</a> : "—"}</td>
                <td className={cell}>{r.email || "—"}</td>
                <td className={cell}>{r.phone || "—"}</td>
                <td className={cell}>{r.ticket_category || "—"}</td>
                <td className={cell}>{r.source === "online" ? "Online" : (r.source || "Online")}</td>
                <td className={`${cell} font-mono`}>{r.confirmation_number || "—"}</td>
                <td className={cell}>
                  <select value={r.payment_status || "not_applicable"} onChange={(e) => doPayment(r, e.target.value)} data-testid={`payment-${r.id}`} className={`rounded-full px-2 py-0.5 border-0 font-semibold ${PAYMENT_COLORS[r.payment_status] || "bg-slate-100 text-slate-600"}`}>
                    {PAYMENT_STATUSES.map((s) => <option key={s} value={s}>{PAYMENT_LABELS[s]}</option>)}
                  </select>
                </td>
                <td className={`${cell} ${confColor(r.confirmation_status)}`}>{r.confirmation_status || "not sent"}{r.resend_count ? ` (${r.resend_count})` : ""}</td>
                <td className={cell}>{r.checked_in ? <span className="text-emerald-600 font-semibold">In</span> : <span className="text-slate-400">—</span>}</td>
                <td className={cell}>{r.checked_in_at ? new Date(r.checked_in_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</td>
                <td className={cell}>{r.badge_status === "printed" ? `Printed${r.badge_print_count ? ` ×${r.badge_print_count}` : ""}` : "—"}</td>
                <td className={cell}><Button size="sm" variant="ghost" onClick={() => doPrint(r)} data-testid={`print-badge-${r.id}`} className="h-6 px-1.5 text-brand-navy"><Printer size={13} /></Button></td>
                <td className={cell}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild><Button size="sm" variant="ghost" data-testid={`actions-${r.id}`} className="h-6 px-1.5"><MoreHorizontal size={15} /></Button></DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-52">
                      <DropdownMenuItem onClick={() => setView(r)} data-testid={`view-${r.id}`}>View Registration</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setEdit({ ...r })} data-testid={`edit-${r.id}`}>Edit Registration</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => doSend(r)}>Send Confirmation</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => doResend(r)}>Resend Confirmation</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => doCheckin(r, !r.checked_in)}>{r.checked_in ? "Undo Check-In" : "Check In"}</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setCat({ id: r.id, ticket_category: r.ticket_category || cats[0] })}>Change Category</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => doPrint(r)}>Print Badge</DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => doCancel(r)} className="text-rose-600">Cancel Registration</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => doArchive(r)}>{r.archived ? "Unarchive" : "Archive"} Registration</DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setHistory(r)} data-testid={`history-${r.id}`}>View Activity History</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={18} className="text-center text-slate-400 py-6">No registrations match</td></tr>}
          </tbody>
        </table>
      </div>

      {manual && <ManualDialog event={event} cats={cats} onClose={() => setManual(false)} onDone={refresh} />}
      {edit && <EditDialog reg={edit} cats={cats} onClose={() => setEdit(null)} onDone={refresh} />}
      {cat && <CategoryDialog data={cat} cats={cats} onClose={() => setCat(null)} onDone={refresh} />}
      {view && <ViewDialog reg={view} onClose={() => setView(null)} />}
      {history && <HistoryDialog reg={history} onClose={() => setHistory(null)} />}
      {imp && <ImportDialog event={event} onClose={() => setImp(false)} onDone={refresh} />}
      {exp && <ExportDialog event={event} ids={exp.ids} onClose={() => setExp(null)} />}
      {bulk && <BulkConfirmDialog actionKey={bulk} count={selIds.length} event={event} cats={cats} onClose={() => setBulk(null)} onConfirm={runBulk} />}
    </div>
  );
};

const FS = ({ label, v, on, opts }) => (
  <div>
    <label className="text-[11px] text-slate-500">{label}</label>
    <select value={v || ""} onChange={(e) => on(e.target.value)} data-testid={`filter-${label.toLowerCase().replace(/[^a-z]/g, "-")}`} className="w-full h-8 rounded-md border border-input bg-background px-2 text-xs">
      <option value="">All</option>
      {opts.map((o) => Array.isArray(o) ? <option key={o[0]} value={o[0]}>{o[1]}</option> : <option key={o} value={o}>{o}</option>)}
    </select>
  </div>
);

const ManualDialog = ({ event, cats, onClose, onDone }) => {
  const [f, setF] = useState({ member_status: "Unknown", ticket_category: cats[0], payment_status: "not_applicable" });
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!f.first_name || !f.last_name) { toast.error("First and last name required"); return; }
    setBusy(true);
    try {
      const { data } = await api.post(`/events/${event.id}/manual-registration`, { ...f, email: f.email || null });
      setSaved(data); toast.success("Registration created"); onDone();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } finally { setBusy(false); }
  };
  const sendConf = async () => { try { const { data } = await api.post(`/registrations/${saved.id}/send-confirmation`); toast.success(`Confirmation ${data.status}`); } catch { toast.error("Failed"); } };
  const checkIn = async () => { try { await api.put(`/registrations/${saved.id}/checkin`, { checked_in: true }); toast.success("Checked in"); onDone(); } catch { toast.error("Failed"); } };
  const printB = () => printBadges(saved, event, { w: 4, h: 6 });
  const another = () => { setSaved(null); setF({ member_status: "Unknown", ticket_category: cats[0], payment_status: "not_applicable" }); };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Add Manual Registration</DialogTitle></DialogHeader>
        {saved ? (
          <div className="space-y-3" data-testid="manual-saved">
            <p className="text-sm text-emerald-600 font-medium">{saved.name} added · {saved.confirmation_number}</p>
            <div className="grid grid-cols-2 gap-2">
              <Button size="sm" variant="outline" onClick={sendConf} data-testid="manual-send-conf">Send Confirmation</Button>
              <Button size="sm" variant="outline" onClick={checkIn}>Check In</Button>
              <Button size="sm" variant="outline" onClick={printB}>Print Badge</Button>
              <Button size="sm" variant="outline" onClick={another} data-testid="manual-add-another">Add Another</Button>
            </div>
            <DialogFooter><Button onClick={onClose} className="bg-brand-magenta hover:bg-brand-pink">Return to List</Button></DialogFooter>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="First name" name="first_name" value={f.first_name} onChange={on} required />
                <Field label="Last name" name="last_name" value={f.last_name} onChange={on} required />
                <Field label="Email" name="email" type="email" value={f.email} onChange={on} />
                <Field label="Phone" name="phone" value={f.phone} onChange={on} />
                <SelectField label="State" name="state" value={f.state} onChange={on} options={US_STATES_TERRITORIES} />
                <Field label="City" name="city" value={f.city} onChange={on} />
                <Field label="ZIP" name="zip_code" value={f.zip_code} onChange={on} />
                <SelectField label="AAWTA member" name="member_status" value={f.member_status} onChange={on} options={["Yes", "No", "Unknown"]} />
                <Field label="Business / org" name="business_name" value={f.business_name} onChange={on} />
                <Field label="Business website" name="business_website" value={f.business_website} onChange={on} />
                <Field label="Job title" name="job_title" value={f.job_title} onChange={on} />
                <SelectField label="Registration category" name="ticket_category" value={f.ticket_category} onChange={on} options={cats} />
                <div className="space-y-1.5"><label className="text-sm text-slate-700">Payment status</label><select data-testid="field-payment_status" value={f.payment_status || ""} onChange={(e) => on("payment_status", e.target.value)} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm">{PAYMENT_STATUSES.map((s) => <option key={s} value={s}>{PAYMENT_LABELS[s]}</option>)}</select></div>
                <SelectField label="Badge category" name="badge_category" value={f.badge_category} onChange={on} options={BADGE_CATEGORIES} />
              </div>
              <Field label="Internal notes" name="internal_notes" value={f.internal_notes} onChange={on} textarea />
              <div className="space-y-1.5 pt-1 border-t border-slate-100">
                <Consent label="Complimentary registration" name="complimentary" checked={f.complimentary} onChange={on} />
                <Consent label="Newsletter opt-in (only if attendee consented)" name="newsletter_opt_in" checked={f.newsletter_opt_in} onChange={on} />
                <Consent label="Upcoming events opt-in (only if attendee consented)" name="events_opt_in" checked={f.events_opt_in} onChange={on} />
                <Consent label="Check in now" name="checked_in" checked={f.checked_in} onChange={on} />
              </div>
            </div>
            <DialogFooter><Button onClick={save} disabled={busy} data-testid="manual-save-btn" className="bg-brand-magenta hover:bg-brand-pink">{busy ? "Saving…" : "Save Registration"}</Button></DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

const EditDialog = ({ reg, cats, onClose, onDone }) => {
  const [f, setF] = useState({ ...reg, is_member_str: reg.is_member ? "Yes" : "No" });
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const save = async () => {
    try {
      await api.put(`/registrations/${reg.id}`, {
        first_name: f.first_name, last_name: f.last_name, email: f.email || null, phone: f.phone, state: f.state,
        city: f.city, zip_code: f.zip_code, is_member: f.is_member_str === "Yes", business_name: f.business_name,
        business_website: f.business_website, job_title: f.job_title, ticket_category: f.ticket_category,
        badge_category: f.badge_category, dietary: f.dietary, accessibility: f.accessibility, internal_notes: f.internal_notes,
      });
      toast.success("Registration updated"); onDone(); onClose();
    } catch { toast.error("Update failed"); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Edit Registration</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <Field label="First name" name="first_name" value={f.first_name} onChange={on} />
          <Field label="Last name" name="last_name" value={f.last_name} onChange={on} />
          <Field label="Email" name="email" type="email" value={f.email} onChange={on} />
          <Field label="Phone" name="phone" value={f.phone} onChange={on} />
          <SelectField label="State" name="state" value={f.state} onChange={on} options={US_STATES_TERRITORIES} />
          <Field label="City" name="city" value={f.city} onChange={on} />
          <Field label="ZIP" name="zip_code" value={f.zip_code} onChange={on} />
          <SelectField label="AAWTA member" name="is_member_str" value={f.is_member_str} onChange={on} options={["Yes", "No"]} />
          <Field label="Business / org" name="business_name" value={f.business_name} onChange={on} />
          <Field label="Business website" name="business_website" value={f.business_website} onChange={on} />
          <Field label="Job title" name="job_title" value={f.job_title} onChange={on} />
          <SelectField label="Registration category" name="ticket_category" value={f.ticket_category} onChange={on} options={cats} />
          <SelectField label="Badge category" name="badge_category" value={f.badge_category} onChange={on} options={BADGE_CATEGORIES} />
        </div>
        <DialogFooter><Button onClick={save} data-testid="edit-save-btn" className="bg-brand-magenta hover:bg-brand-pink">Save Changes</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const CategoryDialog = ({ data, cats, onClose, onDone }) => {
  const [c, setC] = useState(data.ticket_category);
  const save = async () => { try { await api.put(`/registrations/${data.id}`, { ticket_category: c }); toast.success("Category changed"); onDone(); onClose(); } catch { toast.error("Failed"); } };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader><DialogTitle>Change Registration Category</DialogTitle></DialogHeader>
        <SelectField label="Category" name="ticket_category" value={c} onChange={(_, v) => setC(v)} options={cats} />
        <DialogFooter><Button onClick={save} data-testid="category-save-btn" className="bg-brand-magenta hover:bg-brand-pink">Save</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const ViewDialog = ({ reg, onClose }) => (
  <Dialog open onOpenChange={(o) => !o && onClose()}>
    <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto" data-testid="view-dialog">
      <DialogHeader><DialogTitle>{reg.name}</DialogTitle></DialogHeader>
      <div className="text-sm space-y-1.5 text-slate-600">
        {[["Confirmation #", reg.confirmation_number], ["Email", reg.email], ["Phone", reg.phone], ["State", reg.state], ["City", reg.city], ["Member", reg.is_member ? "Yes" : (reg.member_status || "No")], ["Business", reg.business_name], ["Website", reg.business_website], ["Job title", reg.job_title], ["Category", reg.ticket_category], ["Badge category", reg.badge_category], ["Source", reg.source], ["Payment", reg.payment_status], ["Status", reg.status], ["Checked in", reg.checked_in ? `Yes (${reg.checkin_method || "manual"})` : "No"], ["Confirmation email", reg.confirmation_status || "not sent"], ["Dietary", reg.dietary], ["Accessibility", reg.accessibility], ["Internal notes", reg.internal_notes], ["Created by", reg.created_by], ["Updated by", reg.updated_by]].filter(([, v]) => v).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3 border-b border-slate-50 py-1"><span className="text-slate-400">{k}</span><span className="text-right text-slate-700 break-all">{String(v)}</span></div>
        ))}
      </div>
    </DialogContent>
  </Dialog>
);

const HistoryDialog = ({ reg, onClose }) => {
  const [items, setItems] = useState(null);
  useEffect(() => { api.get(`/registrations/${reg.id}/history`).then((r) => setItems(r.data)).catch(() => setItems([])); }, [reg.id]);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto" data-testid="history-dialog">
        <DialogHeader><DialogTitle>Activity History — {reg.name}</DialogTitle></DialogHeader>
        {!items ? <p className="text-sm text-slate-400">Loading…</p> : !items.length ? <p className="text-sm text-slate-400">No activity recorded.</p> : (
          <div className="space-y-2">
            {items.map((a) => (
              <div key={a.id} className="text-sm border-l-2 border-brand-magenta/30 pl-3">
                <p className="font-medium text-slate-700">{a.action.replace(/_/g, " ")}</p>
                <p className="text-xs text-slate-400">{a.user_name} · {new Date(a.created_at).toLocaleString()}</p>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

const ImportDialog = ({ event, onClose, onDone }) => {
  const [step, setStep] = useState("upload");
  const [parsed, setParsed] = useState(null);
  const [mapping, setMapping] = useState({});
  const [report, setReport] = useState(null);
  const [strategy, setStrategy] = useState("skip");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const upload = async (e) => {
    const file = e.target.files?.[0]; if (!file) return;
    setBusy(true);
    try { const fd = new FormData(); fd.append("file", file); const { data } = await api.post(`/events/${event.id}/import/parse`, fd, { headers: { "Content-Type": "multipart/form-data" } }); setParsed(data); setMapping(data.mapping || {}); setStep("map"); }
    catch { toast.error("Could not parse file"); } finally { setBusy(false); }
  };
  const preview = async () => { setBusy(true); try { const { data } = await api.post(`/events/${event.id}/import/preview`, { mapping, rows: parsed.rows }); setReport(data); setStep("preview"); } catch { toast.error("Preview failed"); } finally { setBusy(false); } };
  const commit = async () => { setBusy(true); try { const { data } = await api.post(`/events/${event.id}/import/commit`, { mapping, rows: parsed.rows, duplicate_strategy: strategy }); setResult(data); setStep("done"); onDone(); } catch { toast.error("Import failed"); } finally { setBusy(false); } };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="import-dialog">
        <DialogHeader><DialogTitle>Import Registrations</DialogTitle></DialogHeader>
        {step === "upload" && (
          <div className="space-y-3 text-sm">
            <p className="text-slate-500">Upload a CSV or XLSX file. Need the format?</p>
            <Button size="sm" variant="outline" onClick={() => window.open(`${API}/events/${event.id}/import-template.csv`, "_blank")} data-testid="download-template">Download template</Button>
            <label className="flex items-center gap-2 rounded-md border border-dashed border-slate-300 px-3 py-3 cursor-pointer hover:border-brand-magenta" data-testid="import-file">
              <Upload size={16} /> {busy ? "Parsing…" : "Choose CSV / XLSX file"}
              <input type="file" className="hidden" accept=".csv,.xlsx" onChange={upload} disabled={busy} />
            </label>
          </div>
        )}
        {step === "map" && parsed && (
          <div className="space-y-3">
            <p className="text-sm text-slate-500">Match spreadsheet columns to fields ({parsed.count} rows).</p>
            <div className="grid grid-cols-2 gap-2 max-h-72 overflow-y-auto">
              {IMPORT_FIELDS.map((f) => (
                <div key={f}>
                  <label className="text-[11px] text-slate-500">{f.replace(/_/g, " ")}{["first_name", "last_name"].includes(f) ? " *" : ""}</label>
                  <select value={mapping[f] || ""} onChange={(e) => setMapping((p) => ({ ...p, [f]: e.target.value }))} data-testid={`map-${f}`} className="w-full h-8 rounded-md border border-input bg-background px-2 text-xs">
                    <option value="">—</option>
                    {parsed.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              ))}
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setStep("upload")}>Back</Button><Button onClick={preview} disabled={busy} data-testid="import-preview-btn" className="bg-brand-magenta hover:bg-brand-pink">Preview</Button></DialogFooter>
          </div>
        )}
        {step === "preview" && report && (
          <div className="space-y-3 text-sm" data-testid="import-preview">
            <div className="grid grid-cols-2 gap-2">
              {[["Total", report.total], ["Valid", report.valid], ["Duplicates", report.duplicates], ["Missing required", report.missing_required], ["Invalid emails", report.invalid_emails], ["Invalid phones", report.invalid_phones], ["Will skip", report.skipped]].map(([k, v]) => (
                <div key={k} className="flex justify-between bg-slate-50 rounded px-2 py-1"><span className="text-slate-500">{k}</span><span className="font-semibold">{v}</span></div>
              ))}
            </div>
            <div>
              <label className="text-xs text-slate-500">On duplicate</label>
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)} data-testid="import-strategy" className="w-full h-8 rounded-md border border-input bg-background px-2 text-sm">
                <option value="skip">Skip duplicates</option>
                <option value="update">Update existing</option>
                <option value="new">Import as new</option>
              </select>
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setStep("map")}>Back</Button><Button onClick={commit} disabled={busy} data-testid="import-commit-btn" className="bg-brand-magenta hover:bg-brand-pink">{busy ? "Importing…" : "Import"}</Button></DialogFooter>
          </div>
        )}
        {step === "done" && result && (
          <div className="space-y-3 text-sm" data-testid="import-result">
            <p className="text-emerald-600 font-medium">Import complete</p>
            <div className="grid grid-cols-2 gap-2">
              {[["Imported", result.imported], ["Updated", result.updated], ["Skipped", result.skipped], ["Duplicates", result.duplicates], ["Failed", result.failed]].map(([k, v]) => (
                <div key={k} className="flex justify-between bg-slate-50 rounded px-2 py-1"><span className="text-slate-500">{k}</span><span className="font-semibold">{v}</span></div>
              ))}
            </div>
            {result.errors?.length ? <div className="max-h-32 overflow-y-auto text-xs text-rose-500">{result.errors.map((e, i) => <p key={i}>Row {e.row}: {e.reason}</p>)}</div> : null}
            <DialogFooter><Button onClick={onClose} className="bg-brand-magenta hover:bg-brand-pink">Done</Button></DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

const ExportDialog = ({ event, ids, onClose }) => {
  const [segment, setSegment] = useState("all");
  const [format, setFormat] = useState("csv");
  const [fields, setFields] = useState(EXPORT_FIELDS);
  const toggle = (f) => setFields((p) => p.includes(f) ? p.filter((x) => x !== f) : [...p, f]);
  const download = () => {
    const p = new URLSearchParams({ format, segment, fields: fields.join(",") });
    if (ids && ids.length) p.set("ids", ids.join(","));
    window.open(`${API}/events/${event.id}/export?${p}`, "_blank");
    onClose();
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="export-dialog">
        <DialogHeader><DialogTitle>Export Registrations{ids && ids.length ? ` (${ids.length} selected)` : ""}</DialogTitle></DialogHeader>
        <div className="space-y-3 text-sm">
          {!(ids && ids.length) && (
            <div>
              <label className="text-xs text-slate-500">Segment</label>
              <select value={segment} onChange={(e) => setSegment(e.target.value)} data-testid="export-segment" className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm">
                {SEGMENTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="text-xs text-slate-500">Format</label>
            <div className="flex gap-2 mt-1">
              {["csv", "xlsx", "pdf"].map((f) => <button key={f} onClick={() => setFormat(f)} data-testid={`export-format-${f}`} className={`px-3 py-1.5 rounded-full text-xs font-medium border ${format === f ? "bg-brand-magenta text-white border-brand-magenta" : "bg-white text-slate-600 border-slate-200"}`}>{f.toUpperCase()}</button>)}
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-500">Fields</label>
            <div className="grid grid-cols-2 gap-1 mt-1 max-h-56 overflow-y-auto">
              {EXPORT_FIELDS.map((f) => (
                <label key={f} className="flex items-center gap-1.5 text-xs cursor-pointer"><input type="checkbox" checked={fields.includes(f)} onChange={() => toggle(f)} className="accent-[#D6189B]" /> {f.replace(/_/g, " ")}</label>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter><Button onClick={download} data-testid="export-download-btn" className="bg-brand-magenta hover:bg-brand-pink"><Download size={14} className="mr-1" /> Download</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const BulkConfirmDialog = ({ actionKey, count, event, cats, onClose, onConfirm }) => {
  const def = BULK.find((b) => b[0] === actionKey) || [actionKey, actionKey];
  const needsValue = ["change_category", "assign_badge_category", "update_payment"].includes(actionKey);
  const opts = actionKey === "change_category" ? cats : actionKey === "assign_badge_category" ? BADGE_CATEGORIES : actionKey === "update_payment" ? PAYMENT_STATUSES : [];
  const [value, setValue] = useState(opts[0] || "");
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm" data-testid="bulk-confirm">
        <DialogHeader><DialogTitle>{def[1]}</DialogTitle></DialogHeader>
        <div className="text-sm text-slate-600 space-y-2">
          <p><strong>Action:</strong> {def[1]}</p>
          <p><strong>Affected:</strong> {count} registration{count === 1 ? "" : "s"}</p>
          <p><strong>Event:</strong> {event.name}</p>
          {def[2] && <p className="text-amber-600">A confirmation email will be sent to each selected attendee.</p>}
          {needsValue && (
            <select value={value} onChange={(e) => setValue(e.target.value)} data-testid="bulk-value" className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm">
              {opts.map((o) => <option key={o} value={o}>{actionKey === "update_payment" ? PAYMENT_LABELS[o] : o}</option>)}
            </select>
          )}
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={() => onConfirm(actionKey, needsValue ? value : undefined)} data-testid="bulk-confirm-btn" className={["cancel", "archive"].includes(actionKey) ? "bg-rose-600 hover:bg-rose-700" : "bg-brand-magenta hover:bg-brand-pink"}>Confirm</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
