"use client";
import { fmtDate } from "@/lib/api";

export default function TimeSlider(props: {
  min: number; max: number; value: number | null; markers: { ts: number; label: string }[]; onChange: (v: number | null) => void;
}) {
  const { min, max, value, markers, onChange } = props;
  const v = value ?? max;
  const pct = (t: number) => ((t - min) / (max - min)) * 100;
  return (
    <div className="border-t border-line bg-panel px-4 py-3">
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="text-mute">Time travel · re-runs the same Cypher with a different timestamp</span>
        <span className="flex items-center gap-2">
          <span className="font-medium text-ink">{value == null ? "Now" : `As of ${fmtDate(v)}`}</span>
          {value != null && <button className="text-accent hover:underline" onClick={() => onChange(null)}>back to now</button>}
        </span>
      </div>
      <div className="relative pt-3">
        <div className="pointer-events-none absolute left-0 right-0 top-0 h-3">
          {markers.map((m) => (
            <span key={m.ts + m.label} title={`${fmtDate(m.ts)} · ${m.label}`}
              className="absolute top-0 h-2 w-[2px] bg-accent/70" style={{ left: `${pct(m.ts)}%` }} />
          ))}
        </div>
        <input type="range" min={min} max={max} step={86400000} value={v} className="w-full"
          onChange={(e) => { const n = Number(e.target.value); onChange(n >= max - 86400000 ? null : n); }} />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-mute"><span>{fmtDate(min)}</span><span>today</span></div>
    </div>
  );
}
