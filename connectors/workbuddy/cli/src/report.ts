/**
 * SSE stream → report extraction. Mirrors the cue-buddy `sse_report.py`
 * contract so both clients produce identical reports from the same stream.
 */

import type { SseEvent } from './http.js';

export interface SourceRef {
  index: number;
  url: string;
  title: string;
}

export interface TimelineEntry {
  agent: string;
  execution_time: number;
}

interface Payload {
  data?: unknown;
  [key: string]: unknown;
}

function parsePayload(raw: string): Payload | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? (parsed as Payload) : null;
  } catch {
    return null;
  }
}

/** Live streams wrap the payload in { data: {...} }; replay streams are flat. */
function eventData(payload: Payload): Record<string, unknown> {
  const nested = payload.data;
  if (nested && typeof nested === 'object') return nested as Record<string, unknown>;
  return payload as Record<string, unknown>;
}

function agentName(payload: Payload): string {
  const nested = payload.data && typeof payload.data === 'object' ? (payload.data as Record<string, unknown>) : {};
  const name = payload.agent_name ?? nested.agent_name ?? '';
  return typeof name === 'string' ? name : '';
}

/** Accumulate text emitted inside the reporter agent's start/end window. */
export function extractReporterContent(events: SseEvent[]): string {
  let inReporter = false;
  const pieces: string[] = [];
  for (const { event, data } of events) {
    if (!data) continue;
    const payload = parsePayload(data);
    if (!payload) continue;
    if (event === 'start_of_agent' && agentName(payload) === 'reporter') {
      inReporter = true;
      continue;
    }
    if (event === 'end_of_agent' && agentName(payload) === 'reporter') {
      inReporter = false;
      continue;
    }
    if (inReporter && event === 'message') {
      const delta = eventData(payload).delta;
      if (delta && typeof delta === 'object') {
        const text = (delta as Record<string, unknown>).content;
        if (typeof text === 'string' && text) pieces.push(text);
      }
    }
  }
  return pieces.join('');
}

export function extractSources(events: SseEvent[]): SourceRef[] {
  const map = new Map<number, SourceRef>();
  for (const { event, data } of events) {
    if (event !== 'tool_chunk' || !data) continue;
    const payload = parsePayload(data);
    if (!payload) continue;
    const chunk = eventData(payload).chunk;
    if (!chunk || typeof chunk !== 'object') continue;
    for (const [key, value] of Object.entries(chunk as Record<string, unknown>)) {
      if (!/^[0-9]+$/.test(key)) continue;
      if (!value || typeof value !== 'object') continue;
      const entry = value as Record<string, unknown>;
      const inner = (entry.data && typeof entry.data === 'object' ? entry.data : entry) as Record<string, unknown>;
      const url = typeof inner.url === 'string' ? inner.url : '';
      const title = typeof inner.title === 'string' ? inner.title : '';
      if (url || title) map.set(Number(key), { index: Number(key), url, title });
    }
  }
  return [...map.values()].sort((a, b) => a.index - b.index);
}

export function extractTimeline(events: SseEvent[]): TimelineEntry[] {
  const out: TimelineEntry[] = [];
  for (const { event, data } of events) {
    if (event !== 'end_of_agent' || !data) continue;
    const payload = parsePayload(data);
    if (!payload) continue;
    const d = eventData(payload);
    const agent = typeof d.agent_name === 'string' ? d.agent_name : '?';
    const t = typeof d.execution_time === 'number' ? d.execution_time : 0;
    out.push({ agent, execution_time: t });
  }
  return out;
}

export type EmptyKind = 'no_events' | 'no_agent_events' | 'stream_cut_before_reporter' | 'reporter_started_no_text';

export function diagnoseEmpty(events: SseEvent[]): { kind: EmptyKind; lastAgent: string | null; messageEvents: number } {
  let lastAgent: string | null = null;
  let reporterStarted = false;
  let messageEvents = 0;
  for (const { event, data } of events) {
    if (!data) continue;
    const payload = parsePayload(data);
    if (!payload) continue;
    if (event === 'start_of_agent') {
      const name = agentName(payload);
      if (name) lastAgent = name;
      if (name === 'reporter') reporterStarted = true;
    } else if (event === 'message') {
      messageEvents += 1;
    }
  }
  if (events.length === 0) return { kind: 'no_events', lastAgent, messageEvents };
  if (!lastAgent) return { kind: 'no_agent_events', lastAgent, messageEvents };
  if (!reporterStarted) return { kind: 'stream_cut_before_reporter', lastAgent, messageEvents };
  return { kind: 'reporter_started_no_text', lastAgent, messageEvents };
}
