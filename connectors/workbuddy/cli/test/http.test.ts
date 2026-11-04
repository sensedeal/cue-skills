import { describe, expect, it } from 'vitest';
import { parseSse } from '../src/http.js';

async function collect(lines: string[]) {
  const out: { event: string; data: string }[] = [];
  for await (const ev of parseSse(lines)) out.push(ev);
  return out;
}

describe('parseSse', () => {
  it('parses event/data pairs separated by blank lines', async () => {
    const events = await collect([
      'event: start_of_agent',
      'data: {"agent_name":"planner"}',
      '',
      'event: message',
      'data: {"delta":{"content":"hello"}}',
      '',
      'event: end_of_agent',
      'data: {"agent_name":"planner"}',
      '',
    ]);
    expect(events).toEqual([
      { event: 'start_of_agent', data: '{"agent_name":"planner"}' },
      { event: 'message', data: '{"delta":{"content":"hello"}}' },
      { event: 'end_of_agent', data: '{"agent_name":"planner"}' },
    ]);
  });

  it('handles CRLF and missing event lines', async () => {
    const events = await collect(['data: {"a":1}\r', '', 'data: {"b":2}\r', '']);
    expect(events).toEqual([
      { event: '', data: '{"a":1}' },
      { event: '', data: '{"b":2}' },
    ]);
  });

  it('drops keep-alive comments and empty data', async () => {
    const events = await collect([': ping', '', 'event: message', 'data:', '']);
    expect(events).toEqual([]);
  });
});
