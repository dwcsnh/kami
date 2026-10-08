// Where replay documents come from. Sprint 03: static files (web/public/fixtures/<name>/); Sprint 08 adds an API
// source with the same interface (one endpoint per file).
import { type Manifest, type ReplayDocs, SCHEMA_VERSION } from "./types";

export interface ReplaySource {
  manifest(): Promise<Manifest>;
  file(name: keyof Manifest["files"], meta: Manifest["files"][keyof Manifest["files"]]): Promise<unknown>;
}

/** JSON from raw bytes, gzip-compressed or not (a server may already have decoded Content-Encoding). */
export async function parseBytes(bytes: Uint8Array): Promise<unknown> {
  let raw = bytes;
  if (bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b) {
    const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(new DecompressionStream("gzip"));
    raw = new Uint8Array(await new Response(stream).arrayBuffer());
  }
  return JSON.parse(new TextDecoder().decode(raw));
}

export class StaticReplaySource implements ReplaySource {
  constructor(private readonly baseUrl: string) {}

  private async get(path: string): Promise<unknown> {
    const res = await fetch(`${this.baseUrl.replace(/\/$/, "")}/${path}`);
    if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
    return parseBytes(new Uint8Array(await res.arrayBuffer()));
  }

  manifest(): Promise<Manifest> {
    return this.get("manifest.json") as Promise<Manifest>;
  }

  file(_name: keyof Manifest["files"], meta: Manifest["files"][keyof Manifest["files"]]): Promise<unknown> {
    return this.get(meta.path);
  }
}

export function checkManifest(m: Manifest): void {
  if (m.kind !== "kami.replay") throw new Error(`not a kami replay (kind = ${String(m.kind)})`);
  if (!Number.isInteger(m.schema_version)) throw new Error("manifest.schema_version missing");
  if (m.schema_version > SCHEMA_VERSION) {
    throw new Error(`replay schema_version ${m.schema_version} is newer than this app supports (${SCHEMA_VERSION})`);
  }
}

export async function loadReplay(source: ReplaySource, onProgress?: (msg: string) => void): Promise<ReplayDocs> {
  onProgress?.("Đang đọc manifest…");
  const manifest = await source.manifest();
  checkManifest(manifest);
  onProgress?.("Đang tải quỹ đạo xe…");
  const [vehicles, trips, events, metrics] = await Promise.all(
    (["vehicles", "trips", "events", "metrics"] as const).map((n) => source.file(n, manifest.files[n])),
  );
  return { manifest, vehicles, trips, events, metrics } as ReplayDocs;
}
