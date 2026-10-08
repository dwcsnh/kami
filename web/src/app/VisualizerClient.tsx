"use client";
// The visualizer uses WebGL and window: load it in the browser only.
import dynamic from "next/dynamic";

const Visualizer = dynamic(() => import("@/panels/Visualizer"), { ssr: false });

export default function VisualizerClient() {
  return <Visualizer />;
}
