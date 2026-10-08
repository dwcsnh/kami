"use client";
// Component gallery (S03-4): every token and base component, for Sprint 09 and for the docs screenshots.
import { useState } from "react";
import { contrast } from "@/design/color";
import { tokens } from "@/design/tokens";
import { Badge, Button, IconButton, KpiCard, LegendChip, Panel, Segmented, Timeline, Toggle, Tooltip } from "@/ui";
import { IconCube, IconFit, IconPlay } from "@/ui/icons";
import s from "./gallery.module.css";

const STATE_LABELS: Record<string, string> = {
  idle: "Rảnh – đứng yên", cruising: "Rảnh – đang chạy", pickup: "Đi đón khách", on_trip: "Chở khách", reposition: "Điều xe",
};

function Swatch({ name, hex, on = tokens.color.surface }: { name: string; hex: string; on?: string }) {
  return (
    <div className={s.swatch}>
      <div className={s.swatchColor} style={{ background: hex }} />
      <div className={s.swatchMeta}>
        <b>{name}</b>
        <span>{hex} · {contrast(hex, on).toFixed(2)}:1</span>
      </div>
    </div>
  );
}

export default function Gallery() {
  const [seg, setSeg] = useState<"vehicles" | "trajectories">("vehicles");
  const [speed, setSpeed] = useState(60);
  const [on, setOn] = useState(true);
  const [t, setT] = useState(8 * 3600);
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  return (
    <main className={s.page}>
      <h1 className={s.title}>kami · Thành phần giao diện</h1>
      <p className={s.lead}>Design tokens và thành phần cơ bản của kami 0.2 (light mode, màu chủ đạo xanh Tiffany). Nguồn:
        <code> web/src/design/tokens.json</code>, <code>web/src/ui/</code>.</p>

      <section className={s.section}>
        <h2 className={s.h2}>Thang màu Tiffany (tỷ lệ tương phản với nền trắng)</h2>
        <div className={s.grid}>
          {Object.entries(tokens.color.brand).map(([k, v]) => <Swatch key={k} name={`brand-${k}`} hex={v} />)}
        </div>
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Nền, chữ, trạng thái giao diện</h2>
        <div className={s.grid}>
          {(["bg", "surface", "border", "text", "text-muted", "text-subtle", "primary", "accent", "accent-soft", "success",
             "danger", "warning", "map-ground", "map-water"] as const).map((k) => (
            <Swatch key={k} name={k} hex={tokens.color[k]} />
          ))}
        </div>
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Màu trạng thái xe — phương án A và B (tương phản với nền bản đồ)</h2>
        {(Object.keys(tokens.color.state) as (keyof typeof tokens.color.state)[]).map((p) => (
          <div key={p} style={{ marginBottom: 16 }}>
            <p style={{ margin: "0 0 8px", fontWeight: 600 }}>Phương án {p}</p>
            <div className={s.grid}>
              {Object.entries(tokens.color.state[p]).map(([k, v]) => (
                <Swatch key={k} name={STATE_LABELS[k] ?? k} hex={v} on={tokens.color["map-ground"]} />
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Kiểu chữ (Inter, số tabular)</h2>
        {Object.entries(tokens.font.size).map(([k, v]) => (
          <div key={k} className={s.typeRow}><code>font-size-{k} · {v}</code><span style={{ fontSize: v }}>Đơn hoàn thành 1.234 — 07:45:30</span></div>
        ))}
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Nút & điều khiển</h2>
        <div className={s.row}>
          <Button variant="primary">Chạy mô phỏng</Button>
          <Button>Xuất dữ liệu</Button>
          <Button variant="ghost">Huỷ</Button>
          <Button variant="primary" size="sm">Nhỏ</Button>
          <IconButton label="Phát" variant="primary" round><IconPlay size={20} /></IconButton>
          <IconButton label="Căn khung khu vực"><IconFit /></IconButton>
          <IconButton label="3D" pressed><IconCube /></IconButton>
          <Tooltip text="Gợi ý ngắn"><Badge>Tooltip khi rê chuột</Badge></Tooltip>
          <Badge color={tokens.color.state.A.on_trip}>Chở khách</Badge>
        </div>
        <div className={s.row} style={{ marginTop: 16 }}>
          <Segmented label="Chế độ" value={seg} onChange={setSeg}
            options={[{ value: "vehicles", label: "Xe di chuyển" }, { value: "trajectories", label: "Quỹ đạo" }]} />
          <Segmented label="Tốc độ" size="sm" value={speed} onChange={setSpeed}
            options={[1, 10, 60, 300].map((v) => ({ value: v, label: `${v}×` }))} />
          <Toggle checked={on} onChange={setOn} label="Cung OD nhu cầu" />
        </div>
        <div className={s.row} style={{ marginTop: 16, maxWidth: 560 }}>
          <Timeline label="Thời gian" value={t} min={7 * 3600} max={9.5 * 3600} onChange={setT}
            ticks={[7, 7.5, 8, 8.5, 9, 9.5].map((h) => ({ value: h * 3600, label: `${String(Math.floor(h)).padStart(2, "0")}:${h % 1 ? "30" : "00"}` }))} />
        </div>
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Panel, thẻ KPI, chú giải</h2>
        <div className={s.cols}>
          <Panel title="Chỉ số vận hành">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <KpiCard label="Đơn hoàn thành" value="1.234" hint="luỹ kế" accent={tokens.color.success} />
              <KpiCard label="Đơn hủy" value="87" hint="luỹ kế" accent={tokens.color.danger} />
              <KpiCard label="Thời gian đón TB" value="4,8" unit="phút" hint="1 phút gần nhất" />
              <KpiCard label="Thời gian chờ TB" value="5,2" unit="phút" hint="1 phút gần nhất" accent={tokens.color.primary} />
            </div>
          </Panel>
          {(["A", "B"] as const).map((p) => (
            <Panel key={p} title={`Trạng thái xe — phương án ${p}`}>
              <div className={s.mapSample}>
                {Object.entries(tokens.color.state[p]).map(([k, v], i) => (
                  <LegendChip key={k} color={v} label={STATE_LABELS[k]} count={[42, 18, 61, 152, 9][i]} on={!hidden[k]}
                    emphasis={k === "on_trip"} onToggle={() => setHidden((h) => ({ ...h, [k]: !h[k] }))} />
                ))}
              </div>
            </Panel>
          ))}
        </div>
      </section>
    </main>
  );
}
