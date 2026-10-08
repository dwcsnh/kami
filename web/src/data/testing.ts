// Test helper (Node): load a replay folder from disk with the same parser the browser uses.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { checkManifest, parseBytes } from "./loader";
import type { Manifest, ReplayDocs } from "./types";

export async function loadFolder(dir: string): Promise<ReplayDocs> {
  const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8")) as Manifest;
  checkManifest(manifest);
  const read = async (n: keyof Manifest["files"]) => parseBytes(new Uint8Array(readFileSync(join(dir, manifest.files[n].path))));
  const [vehicles, trips, events, metrics] = await Promise.all(
    (["vehicles", "trips", "events", "metrics"] as const).map(read),
  );
  return { manifest, vehicles, trips, events, metrics } as ReplayDocs;
}
