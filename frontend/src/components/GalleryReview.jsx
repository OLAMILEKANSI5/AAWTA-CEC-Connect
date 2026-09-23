import React, { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Check, X, RotateCcw, Images } from "lucide-react";
import { api, API } from "@/auth";
import { Button } from "@/components/ui/button";
import { EmptyState, Loading } from "@/components/shared";

const TABS = [["pending", "Pending Review"], ["approved", "Approved"], ["rejected", "Rejected"]];

export const GalleryReview = () => {
  const [status, setStatus] = useState("pending");
  const [data, setData] = useState(null);

  const load = useCallback(() => {
    setData(null);
    api.get(`/gallery/photos?status=${status}`).then((r) => setData(r.data)).catch(() => setData({ photos: [], counts: {} }));
  }, [status]);
  useEffect(() => { load(); }, [load]);

  const setPhotoStatus = async (id, newStatus) => {
    try { await api.put(`/gallery/photos/${id}/status`, { status: newStatus }); toast.success(newStatus === "approved" ? "Approved — now public" : newStatus === "rejected" ? "Removed from gallery" : "Reset to pending"); load(); }
    catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-4" data-testid="gallery-review">
      <div className="flex flex-wrap gap-2">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setStatus(k)} data-testid={`gallery-tab-${k}`}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${status === k ? "bg-brand-magenta text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {label}{data?.counts?.[k] != null && <span className="ml-1.5 opacity-80">({data.counts[k]})</span>}
          </button>
        ))}
      </div>

      {data === null ? <Loading /> : data.photos.length === 0 ? (
        <EmptyState icon={Images} title="No photos here" subtitle={status === "pending" ? "Photos from post-event reports will appear here for review." : `No ${status} photos.`} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {data.photos.map((p) => (
            <div key={p.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`gallery-photo-${p.id}`}>
              <a href={`${API}/files/${p.file_id}/download`} target="_blank" rel="noreferrer" className="block aspect-square bg-brand-navy/5">
                <img src={`${API}/files/${p.file_id}/download`} alt={p.caption || p.event_name} className="w-full h-full object-cover" onError={(e) => { e.currentTarget.style.display = "none"; }} />
              </a>
              <div className="p-3">
                <p className="font-medium text-sm text-brand-navy truncate">{p.event_name}</p>
                {p.caption && <p className="text-xs text-slate-500 line-clamp-2 mt-0.5">“{p.caption}”</p>}
                <p className="text-[11px] text-slate-400 mt-1">by {p.submitted_by || "—"}</p>
                <div className="flex gap-1.5 mt-2">
                  {status !== "approved" && <Button size="sm" onClick={() => setPhotoStatus(p.id, "approved")} data-testid={`approve-photo-${p.id}`} className="flex-1 h-8 bg-emerald-600 hover:bg-emerald-700"><Check size={14} className="mr-1" /> Approve</Button>}
                  {status !== "rejected" && <Button size="sm" variant="outline" onClick={() => setPhotoStatus(p.id, "rejected")} data-testid={`reject-photo-${p.id}`} className="flex-1 h-8 text-rose-600 border-rose-200"><X size={14} className="mr-1" /> {status === "approved" ? "Remove" : "Reject"}</Button>}
                  {status !== "pending" && <Button size="sm" variant="ghost" onClick={() => setPhotoStatus(p.id, "pending")} data-testid={`reset-photo-${p.id}`} className="h-8 px-2 text-slate-500"><RotateCcw size={14} /></Button>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
