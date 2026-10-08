/**
 * Minimal HTTP + SSE layer over global fetch (Node >= 20.12).
 * No runtime dependency beyond Node itself.
 */

import { refreshAccessToken } from './credentials.js';
import { CueApiError, CueError, EXIT } from './errors.js';

export interface RequestOptions {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  endpoint: string;
  body?: unknown;
  apiKey?: string;
  base: string;
  timeoutMs?: number;
  accept?: string;
}

export interface SseEvent {
  event: string;
  data: string;
}

function urlOf(base: string, endpoint: string): string {
  return `${base.replace(/\/+$/, '')}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
}

/** 只发一次请求，不判定状态码 —— 判定与重试交给 `call`（401 那条路要走一遍刷新） */
async function callOnce(opts: RequestOptions, accept: string): Promise<Response> {
  const headers: Record<string, string> = { Accept: accept };
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.apiKey) headers.Authorization = `Bearer ${opts.apiKey}`;

  try {
    return await fetch(urlOf(opts.base, opts.endpoint), {
      method: opts.method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      signal: AbortSignal.timeout(opts.timeoutMs ?? 30_000),
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'TimeoutError') {
      throw new CueError(
        `request timed out after ${opts.timeoutMs ?? 30_000}ms on ${opts.endpoint}`,
        EXIT.TIMEOUT,
      );
    }
    const reason = err instanceof Error ? err.message : String(err);
    throw new CueApiError(0, `network unreachable: ${reason}`, opts.endpoint);
  }
}

/**
 * 发请求；**401 时静默刷新一次并重试**（wayfinder #72 的裁定）。
 *
 * 为什么刷新放在这一层而不是各个命令里：`call` 是**所有** API 调用的唯一收口，
 * 放这里只需要把「刷新 + 重试一次」写对一次；分散到各命令则必然有人漏。
 *
 * 只有具备 refresh token 时才会真的刷新（`refreshAccessToken` 在
 * `credentials.json` 不存在时直接返回 null）⇒ 用长期 api_key 的用户行为不变。
 *
 * ⚠️ **只重试一次**（`attempt` 递增）：刷新后仍 401 说明令牌真无效，
 * 再刷就是拿服务端的重放检测开玩笑（两次同 token 刷新 = 家族撤销）。
 */
async function call(opts: RequestOptions, accept: string, attempt = 0): Promise<Response> {
  const response = await callOnce(opts, accept);

  if (response.status === 401 && opts.apiKey && attempt === 0) {
    const refreshed = await refreshAccessToken(opts.base, opts.apiKey);
    if (refreshed) {
      return call({ ...opts, apiKey: refreshed.accessToken }, accept, attempt + 1);
    }
  }

  if (!response.ok) {
    const raw = await response.text().catch(() => '');
    let detail = raw.slice(0, 400);
    try {
      const parsed: unknown = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        const record = parsed as Record<string, unknown>;
        detail = typeof record.detail === 'string' ? record.detail : JSON.stringify(parsed);
      }
    } catch {
      /* keep raw text */
    }
    throw new CueApiError(response.status, detail || '(no body)', opts.endpoint);
  }

  return response;
}

export async function requestJson<T = unknown>(opts: RequestOptions): Promise<T> {
  const response = await call(opts, 'application/json');
  const raw = await response.text();
  if (!raw.trim()) return undefined as T;
  return JSON.parse(raw) as T;
}

async function* iterateLines(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx = buffer.indexOf('\n');
      while (idx >= 0) {
        const line = buffer.slice(0, idx).replace(/\r$/, '');
        buffer = buffer.slice(idx + 1);
        yield line;
        idx = buffer.indexOf('\n');
      }
    }
    if (buffer.length > 0) yield buffer;
  } finally {
    reader.releaseLock();
  }
}

/** Parse an SSE line stream into (event, data) pairs. Pure, testable. */
export function parseSse(lines: Iterable<string> | AsyncIterable<string>): AsyncGenerator<SseEvent> {
  return (async function* () {
    let event = '';
    for await (const line of lines as AsyncIterable<string>) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        const data = line.slice(5).trim();
        if (data) yield { event, data };
      } else if (line === '') {
        event = '';
      }
    }
  })();
}

export async function* streamSse(opts: RequestOptions): AsyncGenerator<SseEvent> {
  const response = await call(opts, 'text/event-stream');
  if (!response.body) {
    throw new CueApiError(0, 'response has no body for SSE stream', opts.endpoint);
  }
  yield* parseSse(iterateLines(response.body));
}
