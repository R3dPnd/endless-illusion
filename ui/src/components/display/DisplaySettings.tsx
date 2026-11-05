import { useEffect, useRef, useState } from "react";
import { describeDisplay, SCALE_MAX, SCALE_MIN, SCALE_STEP } from "../../display";
import type { DisplayState } from "../../hooks/useDisplay";
import { Button } from "../ui";

interface SegProps<T extends string> {
  label: string;
  value: T;
  options: { id: T; label: string }[];
  onChange: (v: T) => void;
}

function Segmented<T extends string>({ label, value, options, onChange }: SegProps<T>) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      <span className="seg__label">{label}</span>
      <div className="seg__opts">
        {options.map((o) => (
          <button key={o.id} type="button" role="radio" aria-checked={o.id === value} className={`seg__opt ${o.id === value ? "is-on" : ""}`} onClick={() => onChange(o.id)}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Header button + popover for scale, density, effects, touch targets and font. */
export default function DisplaySettings({ d }: { d: DisplayState }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { prefs, resolved, display } = d;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const auto = (v: string) => `Auto · ${v}`;
  const pct = Math.round(resolved.scale * 100);

  return (
    <div className="display-settings" ref={ref}>
      <button type="button" className="tab display-settings__toggle" aria-expanded={open} aria-haspopup="dialog" onClick={() => setOpen((o) => !o)} title="Display settings">
        ◧ {pct}%
      </button>
      {open && (
        <div className="display-pop panel" role="dialog" aria-label="Display settings">
          <h2>Display</h2>
          <p className="display-pop__detected">
            <span className="chip chip--tool">{resolved.profile}</span> {describeDisplay(display)}
          </p>

          <div className="seg">
            <span className="seg__label">
              Scale {prefs.scale === "auto" ? <em className="hint">(auto)</em> : null}
            </span>
            <div className="scale-row">
              <Button onClick={() => d.stepScale(-1)} aria-label="Smaller" disabled={resolved.scale <= SCALE_MIN}>
                −
              </Button>
              <input
                type="range"
                min={SCALE_MIN}
                max={SCALE_MAX}
                step={SCALE_STEP}
                value={resolved.scale}
                onChange={(e) => d.update({ scale: Number(e.target.value) })}
                aria-label="UI scale"
              />
              <Button onClick={() => d.stepScale(1)} aria-label="Larger" disabled={resolved.scale >= SCALE_MAX}>
                +
              </Button>
              <span className="scale-row__val">{pct}%</span>
              <Button onClick={() => d.update({ scale: "auto" })} disabled={prefs.scale === "auto"}>
                Auto
              </Button>
            </div>
          </div>

          <Segmented
            label="Density"
            value={prefs.density}
            onChange={(density) => d.update({ density })}
            options={[
              { id: "auto", label: prefs.density === "auto" ? auto(resolved.density) : "Auto" },
              { id: "compact", label: "Compact" },
              { id: "comfortable", label: "Comfy" },
              { id: "spacious", label: "Spacious" },
            ]}
          />
          <Segmented
            label="Effects"
            value={prefs.effects}
            onChange={(effects) => d.update({ effects })}
            options={[
              { id: "auto", label: prefs.effects === "auto" ? auto(resolved.effects) : "Auto" },
              { id: "full", label: "Full" },
              { id: "reduced", label: "Reduced" },
              { id: "off", label: "Off" },
            ]}
          />
          <Segmented
            label="Touch targets"
            value={prefs.touch}
            onChange={(touch) => d.update({ touch })}
            options={[
              { id: "auto", label: prefs.touch === "auto" ? auto(resolved.touch ? "on" : "off") : "Auto" },
              { id: "on", label: "Large" },
              { id: "off", label: "Normal" },
            ]}
          />
          <Segmented
            label="Font"
            value={prefs.font}
            onChange={(font) => d.update({ font })}
            options={[
              { id: "pixel", label: "Pixel" },
              { id: "readable", label: "Readable" },
            ]}
          />

          <div className="display-pop__foot">
            <Button onClick={d.toggleFullscreen}>{d.fullscreen ? "Exit fullscreen" : "Fullscreen"}</Button>
            <Button variant="danger" onClick={d.reset}>
              Reset
            </Button>
            <span className="hint display-pop__keys">Ctrl +/− scale · Ctrl 0 auto{d.isDesktop ? " · F11 fullscreen" : ""}</span>
          </div>
        </div>
      )}
    </div>
  );
}
