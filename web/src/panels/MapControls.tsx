"use client";
// Map toolbar (S03-5): zoom in/out, compass (shows the bearing; click = north up and flat), 2D/3D, fit the area,
// hide the panels. Mouse / touch / keyboard gestures of Mapbox GL stay available.
import { useEffect, useState } from "react";
import { PITCH_3D } from "@/map/baseStyle";
import { mapApiRef } from "@/map/MapView";
import { usePlayback } from "@/store/playback";
import { IconButton } from "@/ui";
import { IconCompass, IconCube, IconExpand, IconFit, IconMinus, IconPlus, IconSquare } from "@/ui/icons";
import s from "./panels.module.css";

export function MapControls() {
  const [cam, setCam] = useState({ pitch: 0, bearing: 0 });
  const toggleChrome = usePlayback((x) => x.toggleChrome);
  useEffect(() => {
    let off: (() => void) | undefined;
    const attach = () => {
      const api = mapApiRef.current;
      if (!api) return false;
      const upd = () => setCam({ pitch: api.getPitch(), bearing: api.getBearing() });
      api.map.on("move", upd);
      upd();
      off = () => api.map.off("move", upd);
      return true;
    };
    const id = attach() ? undefined : setInterval(() => attach() && clearInterval(id), 200);
    return () => {
      if (id) clearInterval(id);
      off?.();
    };
  }, []);
  const pitched = cam.pitch > 5;
  return (
    <div className={s.toolbar} role="toolbar" aria-label="Điều khiển bản đồ">
      <IconButton label="Phóng to (+)" onClick={() => mapApiRef.current?.zoomBy(1)}><IconPlus /></IconButton>
      <IconButton label="Thu nhỏ (−)" onClick={() => mapApiRef.current?.zoomBy(-1)}><IconMinus /></IconButton>
      <IconButton label="Về hướng bắc, bỏ nghiêng" onClick={() => mapApiRef.current?.resetNorth()}>
        <IconCompass style={{ transform: `rotateX(${cam.pitch * 0.8}deg) rotate(${-cam.bearing}deg)` }} />
      </IconButton>
      <span className={s.toolbarSep} aria-hidden="true" />
      <IconButton label={pitched ? "Chuyển sang 2D" : "Chuyển sang 3D (nghiêng)"} pressed={pitched}
        onClick={() => mapApiRef.current?.setPitch(pitched ? 0 : PITCH_3D)}>
        {pitched ? <IconSquare /> : <IconCube />}
      </IconButton>
      <IconButton label="Căn khung khu vực" onClick={() => mapApiRef.current?.fitArea()}><IconFit /></IconButton>
      <IconButton label="Toàn màn hình bản đồ (F)" onClick={toggleChrome}><IconExpand /></IconButton>
    </div>
  );
}
