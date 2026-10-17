import { afterEach, describe, expect, it, vi } from "vitest";
import { createLiveApi, createSavedApi } from "./client";
import { ApiError, fetchJson } from "./fetchJson";
import type { JobStatus } from "./types";

function respond(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("fetchJson", () => {
  it("passes on the server's own message and the retry time", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond({ detail: "You've reached the limit." }, 429, { "Retry-After": "120" })));
    const error = await fetchJson("http://api/optimise").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("You've reached the limit.");
    expect((error as ApiError).retryAfter).toBe(120);
  });

  it("joins the messages of invalid input", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond({ detail: [{ msg: "Value error, '31/03' isn't a date." }, { msg: "k is required" }] }, 422)));
    await expect(fetchJson("http://api/x")).rejects.toThrow("'31/03' isn't a date. k is required");
  });

  it("treats a static host's fallback page as a missing file", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<!doctype html>", { status: 200, headers: { "Content-Type": "text/html" } })));
    await expect(fetchJson("/saved/results/x.json")).rejects.toMatchObject({ status: 404 });
  });

  it("says when the server can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("network");
    }));
    await expect(fetchJson("http://api.example/health")).rejects.toThrow("Can't reach http://api.example.");
  });
});

describe("saved runs", () => {
  it("explains that an unknown result lives on the live server", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond({ detail: "Not Found" }, 404)));
    await expect(createSavedApi("/saved/").result("abc")).rejects.toThrow("kept on the live server");
  });
});

describe("following a job", () => {
  it("polls until the job ends when there is no event stream", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", undefined);
    const answers: Partial<JobStatus>[] = [
      { status: "running", progress: { stage: "Tuning circuit", step: 1, total: 10 } },
      { status: "done", progress: { stage: "Done", step: 1, total: 1 } },
    ];
    const fetch = vi.fn(async () => respond(answers.shift()));
    vi.stubGlobal("fetch", fetch);
    const seen: string[] = [];
    createLiveApi("http://api/").watch("job1", (status) => seen.push(status.status));
    await vi.runAllTimersAsync();
    expect(seen).toEqual(["running", "done"]);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls[0]).toEqual(expect.arrayContaining(["http://api/jobs/job1"]));
  });

  it("stops asking once told to", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", undefined);
    const fetch = vi.fn(async () => respond({ status: "running" }));
    vi.stubGlobal("fetch", fetch);
    const stop = createLiveApi("http://api").watch("job1", () => undefined);
    await vi.advanceTimersByTimeAsync(10);
    stop();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
