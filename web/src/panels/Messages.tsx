"use client";
import { Panel } from "@/ui";
import s from "./panels.module.css";
import { LoadingState } from "@/manager/LoadingState";

export function TokenMissing() {
  return (
    <div className={s.centerMessage}>
      <Panel className={s.messageCard} title="Cần Mapbox access token">
        <p>Bản đồ nền dùng Mapbox GL JS. Tạo một <b>token public</b> (bắt đầu bằng <code>pk.</code>, nên giới hạn URL) trong
          tài khoản Mapbox rồi đặt vào <code>web/.env.local</code> (file này không được commit):</p>
        <pre>NEXT_PUBLIC_MAPBOX_TOKEN=pk.…</pre>
        <p>Sau đó chạy lại <code>npm run dev</code>. Hướng dẫn đầy đủ: <code>docs/engine/20-visualizer.md</code>.</p>
      </Panel>
    </div>
  );
}

export function Loading({ message }: { message: string }) {
  return (
    <div className={s.centerMessage}>
      <div className={s.messageCard}><LoadingState variant="map" label={message}/></div>
    </div>
  );
}

export function LoadError({ error, url }: { error: string; url: string }) {
  return (
    <div className={s.centerMessage}>
      <Panel className={s.messageCard} title="Không đọc được dữ liệu phát lại">
        <p>{error}</p>
        <p>Nguồn: <code>{url}</code>. Sinh lại fixture: <code>python -m kami replay demo</code>.</p>
      </Panel>
    </div>
  );
}
