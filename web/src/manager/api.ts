import type {
  Comparison,
  Entity,
  Health,
  MetricRow,
  Resource,
  RunDetail,
  RunRow,
} from "./types";

export interface FieldError {
  path: string;
  message: string;
}
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly errors: FieldError[],
  ) {
    super(
      errors
        .map((e) => (e.path ? e.path + ": " + e.message : e.message))
        .join("\n"),
    );
  }
}
export function errorFrom(status: number, body: unknown): ApiError {
  const doc = body as { errors?: FieldError[]; detail?: unknown } | null;
  return new ApiError(
    status,
    Array.isArray(doc?.errors)
      ? doc.errors
      : [
          {
            path: "",
            message:
              typeof doc?.detail === "string"
                ? doc.detail
                : "Không thể hoàn tất yêu cầu (HTTP " + status + ").",
          },
        ],
  );
}
export async function request<T>(
  url: string,
  init: RequestInit = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch("/api/v1" + url, {
      cache: "no-store",
      ...init,
      signal: init.signal ?? AbortSignal.timeout(10000),
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch (e) {
    if (init.signal?.aborted) throw e;
    throw new ApiError(0, [
      {
        path: "",
        message: "Không kết nối được backend. Kiểm tra service và thử lại.",
      },
    ]);
  }
  if (res.status === 204) return undefined as T;
  const doc = await res.json().catch(() => null);
  if (!res.ok) throw errorFrom(res.status, doc);
  if (doc === null)
    throw new ApiError(502, [
      { path: "", message: "Backend trả dữ liệu không hợp lệ." },
    ]);
  return doc as T;
}
const post = <T>(url: string, body?: unknown) =>
  request<T>(url, {
    method: "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
export const api = {
  health: (signal?: AbortSignal) => request<Health>("/health", { signal }),
  entities: <T>(kind: Resource, signal?: AbortSignal) =>
    request<Entity<T>[]>("/" + kind, { signal }),
  save: <T>(kind: Resource, spec: T, id?: number) =>
    request<Entity<T>>("/" + kind + (id === undefined ? "" : "/" + id), {
      method: id === undefined ? "POST" : "PUT",
      body: JSON.stringify(spec),
    }),
  remove: (kind: Resource, id: number) =>
    request<void>("/" + kind + "/" + id, { method: "DELETE" }),
  runs: (signal?: AbortSignal) => request<RunRow[]>("/runs", { signal }),
  detail: (id: number, signal?: AbortSignal) =>
    request<RunDetail>("/runs/" + id, { signal }),
  queue: (scenario_id: number) => post<RunDetail>("/runs", { scenario_id }),
  start: (id: number) => post<RunDetail>("/runs/" + id + "/start"),
  cancel: (id: number) => post<RunDetail>("/runs/" + id + "/cancel"),
  summary: (id: number, signal?: AbortSignal) =>
    request<{ summary: Record<string, number | null> }>(
      "/runs/" + id + "/metrics",
      { signal },
    ),
  timeseries: (id: number, signal?: AbortSignal) =>
    request<{ rows: MetricRow[] }>("/runs/" + id + "/timeseries", { signal }),
  compare: (ids: number[], signal?: AbortSignal) =>
    request<Comparison>("/runs/compare?ids=" + ids.join(","), { signal }),
};
