import { describe, expect, it } from 'vitest';
import { diagnoseEmpty, extractReporterContent, extractSources, extractTimeline } from '../src/report.js';
import type { SseEvent } from '../src/http.js';

function ev(event: string, data: unknown): SseEvent {
  return { event, data: typeof data === 'string' ? data : JSON.stringify(data) };
}

const stream: SseEvent[] = [
  ev('start_of_agent', { agent_name: 'planner' }),
  ev('end_of_agent', { agent_name: 'planner', execution_time: 3 }),
  ev('start_of_agent', { agent_name: 'reporter' }),
  ev('message', { data: { delta: { content: '# 报告\n' } } }),
  ev('message', { delta: { content: '正文一段。' } }),
  ev('end_of_agent', { agent_name: 'reporter', execution_time: 12 }),
  ev('tool_chunk', { data: { chunk: { '1': { data: { url: 'https://a.cn', title: 'A' } } } } }),
];

describe('report extraction', () => {
  it('collects reporter text only inside the reporter window', () => {
    expect(extractReporterContent(stream)).toBe('# 报告\n正文一段。');
  });

  it('unwraps live streams nested under data, and flat replay payloads', () => {
    const flat: SseEvent[] = [
      ev('start_of_agent', { agent_name: 'reporter' }),
      ev('message', { delta: { content: 'flat' } }),
    ];
    expect(extractReporterContent(flat)).toBe('flat');
  });

  it('extracts sources sorted by index', () => {
    expect(extractSources(stream)).toEqual([{ index: 1, url: 'https://a.cn', title: 'A' }]);
  });

  it('extracts the agent timeline', () => {
    expect(extractTimeline(stream)).toEqual([
      { agent: 'planner', execution_time: 3 },
      { agent: 'reporter', execution_time: 12 },
    ]);
  });

  it('diagnoses an empty report', () => {
    expect(diagnoseEmpty([]).kind).toBe('no_events');
    expect(diagnoseEmpty([ev('message', { delta: { content: 'x' } })]).kind).toBe('no_agent_events');
    expect(diagnoseEmpty([ev('start_of_agent', { agent_name: 'planner' })]).kind).toBe('stream_cut_before_reporter');
    expect(
      diagnoseEmpty([ev('start_of_agent', { agent_name: 'reporter' }), ev('end_of_agent', { agent_name: 'reporter' })]).kind,
    ).toBe('reporter_started_no_text');
  });
});
