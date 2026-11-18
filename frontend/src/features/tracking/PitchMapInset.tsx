import type { LbwResult, Zone } from "./types";
import { ZONE_COLORS } from "./types";
import { lbwColor, mapWorldToInset } from "./lbwDisplay";

// Zone bands in metres from the batter's stump line (laws scale).
const BANDS: { zone: Zone; z0: number; z1: number }[] = [
  { zone: "YORKER", z0: 0, z1: 2 },
  { zone: "FULL", z0: 2, z1: 6 },
  { zone: "GOOD", z0: 6, z1: 8 },
  { zone: "SHORT", z0: 8, z1: 18.9 },
];
const STUMP_HALF_M = 0.1143;
const IMPACT_Z_M = 1.0;

// Internal drawing units; the outer <svg> scales to width/height.
const VB_W = 140;
const VB_H = 420;
const PAD = 8;
const PW = VB_W - 2 * PAD;
const PH = VB_H - 2 * PAD;

function at(X: number, Z: number): { x: number; y: number } {
  const p = mapWorldToInset(X, Z, PW, PH);
  return { x: p.x + PAD, y: p.y + PAD };
}

interface Props {
  lbw: LbwResult | null | undefined;
  /** Rendered size; when nested inside another <svg>, x/y place it in that space. */
  width: number;
  height: number;
  x?: number;
  y?: number;
}

/** Top-down pitch map (batter's end at the top) with the line-only LBW projection. */
export function PitchMapInset({ lbw, width, height, x, y }: Props) {
  if (!lbw) return null;
  const color = lbwColor(lbw.overall);
  const { x: X_b, z: Z_b } = lbw.pitching;
  const X_i = lbw.impact.x;
  const { x: X_s, sigma } = lbw.wickets;

  const tl = at(-1.32, 0);
  const br = at(1.32, 18.9);
  const pitch = at(X_b, Z_b);
  const imp = at(X_i, IMPACT_Z_M);
  const ws = at(X_s, 0);
  const wl = at(X_s - sigma, 0);
  const wr = at(X_s + sigma, 0);
  const sL = at(-STUMP_HALF_M, 0);
  const sR = at(STUMP_HALF_M, 0);

  return (
    <svg
      x={x}
      y={y}
      width={width}
      height={height}
      viewBox={`0 0 ${VB_W} ${VB_H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="Top-down pitch map, line-only LBW"
    >
      <rect x={0} y={0} width={VB_W} height={VB_H} rx={6} fill="#0b1220" fillOpacity={0.85} />
      <rect x={tl.x} y={tl.y} width={br.x - tl.x} height={br.y - tl.y} fill="#b9a27a" fillOpacity={0.35} />
      {BANDS.map((b) => {
        const a = at(-1.32, b.z0);
        const c = at(1.32, b.z1);
        return (
          <g key={b.zone}>
            <rect
              x={a.x} y={a.y} width={c.x - a.x} height={c.y - a.y}
              fill={ZONE_COLORS[b.zone]} fillOpacity={0.22}
              stroke="#ffffff" strokeOpacity={0.35} strokeWidth={0.8}
            />
            <text
              x={a.x + 3} y={(a.y + c.y) / 2 + 4}
              fontSize={10} fontWeight={700} fill="#ffffff" fillOpacity={0.85}
            >
              {b.zone}
            </text>
          </g>
        );
      })}
      {/* ±sigma wedge from the impact to the stump line, then the centre line */}
      <polygon
        points={`${imp.x},${imp.y} ${wl.x},${wl.y} ${wr.x},${wr.y}`}
        fill={color} fillOpacity={0.45}
      />
      <line x1={imp.x} y1={imp.y} x2={ws.x} y2={ws.y} stroke={color} strokeWidth={1.6} />
      {/* stumps at Z = 0 */}
      <line x1={sL.x} y1={sL.y} x2={sR.x} y2={sR.y} stroke="#ffffff" strokeWidth={3} />
      {/* impact tick */}
      <line x1={imp.x - 5} y1={imp.y} x2={imp.x + 5} y2={imp.y} stroke="#ffffff" strokeWidth={2} />
      {/* pitching point */}
      <circle cx={pitch.x} cy={pitch.y} r={4} fill={color} stroke="#ffffff" strokeWidth={1.2} />
    </svg>
  );
}
