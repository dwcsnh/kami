import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, errorFrom, request } from "./api";
afterEach(()=>vi.unstubAllGlobals());
describe("API client",()=>{
  it("keeps field paths and conflict messages",()=>{
    expect(errorFrom(422,{errors:[{path:"fleets[0].ref",message:"không tồn tại"}]}).errors[0].path).toBe("fleets[0].ref");
    expect(errorFrom(409,{detail:"đang bận"}).message).toBe("đang bận");
    expect(errorFrom(502,"bad").status).toBe(502);
  });
  it("sends typed mutations to the same origin and handles DELETE 204",async()=>{
    const fetch=vi.fn().mockResolvedValue(new Response(null,{status:204}));vi.stubGlobal("fetch",fetch);
    await api.remove("fleets",2);
    expect(fetch).toHaveBeenCalledWith("/api/v1/fleets/2",expect.objectContaining({method:"DELETE",cache:"no-store"}));
  });
  it("surfaces network and malformed backend data without losing the caller draft",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(request("/health")).rejects.toBeInstanceOf(ApiError);
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response("not-json",{status:200})));
    await expect(request("/health")).rejects.toMatchObject({status:502});
  });
});
