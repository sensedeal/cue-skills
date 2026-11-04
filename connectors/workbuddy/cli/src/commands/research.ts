/**
 * `cue research` — run one deep-research job against POST /chat/stream and
 * print (or save) the reporter's Markdown report.
 */

import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { API_KEY_PAGE, loadConfig } from '../config.js';
import { CueError, EXIT } from '../errors.js';
import { streamSse, type SseEvent } from '../http.js';
import { diagnoseEmpty, extractReporterContent, extractSources, extractTimeline } from '../report.js';

export interface ResearchOptions {
  base?: string;
  templateId?: string;
  conversationId?: string;
  output?: string;
  timeoutMs?: number;
  json?: boolean;
  quiet?: boolean;
}

export function normalizeTemplateId(templateId: string): string {
  return templateId.startsWith('template_') ? templateId : `template_${templateId}`;
}

function validateTemplateId(templateId: string): string | null {
  const suffix = templateId.startsWith('template_') ? templateId.slice('template_'.length) : templateId;
  if (/^[0-9]+$/.test(suffix)) {
    return `template_id=${templateId}: 纯数字后缀不是 Cue id（形如 template_fnig0i），请取搭子的 template_id 字段。`;
  }
  return null;
}

function resolveOutput(output: string): string {
  if (output.startsWith('~/')) {
    const home = process.env.HOME || process.env.USERPROFILE || '';
    return path.join(home, output.slice(2));
  }
  return output;
}

export async function research(query: string, opts: ResearchOptions = {}): Promise<number> {
  if (!query || !query.trim()) {
    throw new CueError('研究问题不能为空', EXIT.BAD_INPUT);
  }

  const cfg = loadConfig();
  if (!cfg.apiKey) {
    console.error(
      `\n[cue] 缺少 API key。\n` +
        `  → 执行 cue auth login（或到 ${API_KEY_PAGE} 创建 key 后 cue auth login --api-key sk-...）\n` +
        `  → 也可 export CUE_API_KEY=sk-...\n`,
    );
    return EXIT.NO_CREDENTIALS;
  }

  const base = opts.base?.trim() || cfg.base;
  let templateId = opts.templateId?.trim();
  if (templateId) {
    templateId = normalizeTemplateId(templateId);
    const bad = validateTemplateId(templateId);
    if (bad) throw new CueError(bad, EXIT.BAD_INPUT);
  }

  const conversationId = opts.conversationId?.trim() || `cue-cli-${randomBytes(6).toString('hex')}`;
  const payload: Record<string, unknown> = {
    messages: [{ role: 'user', content: query }],
    conversation_id: conversationId,
    chat_id: randomBytes(16).toString('hex'),
    need_confirm: false,
    need_analysis: false,
    need_underlying: false,
    need_recommend: false,
  };
  if (templateId) payload.template_id = templateId;

  const started = Date.now();
  const events: SseEvent[] = [];
  const timeoutMs = opts.timeoutMs ?? 1_200_000;

  for await (const event of streamSse({
    method: 'POST',
    endpoint: '/chat/stream',
    body: payload,
    apiKey: cfg.apiKey,
    base,
    timeoutMs,
  })) {
    events.push(event);
    if (!opts.quiet && !opts.json) {
      if (event.event === 'start_of_agent') {
        try {
          const parsed = JSON.parse(event.data) as { data?: { agent_name?: string }; agent_name?: string };
          const name = parsed.agent_name ?? parsed.data?.agent_name ?? '';
          if (name) process.stderr.write(`  ▸ ${name} 开始\n`);
        } catch {
          /* ignore malformed progress event */
        }
      } else if (event.event === 'end_of_agent') {
        try {
          const parsed = JSON.parse(event.data) as { data?: { agent_name?: string; execution_time?: number }; agent_name?: string; execution_time?: number };
          const name = parsed.agent_name ?? parsed.data?.agent_name ?? '';
          const secs = parsed.execution_time ?? parsed.data?.execution_time ?? 0;
          if (name) process.stderr.write(`  ✓ ${name} 完成 (${secs}s)\n`);
        } catch {
          /* ignore malformed progress event */
        }
      }
    }
  }

  const elapsedMs = Date.now() - started;
  const report = extractReporterContent(events);

  if (!report) {
    const diag = diagnoseEmpty(events);
    console.error(
      `\n[cue] 未捕获到报告正文 (conversation_id=${conversationId})\n` +
        `  kind=${diag.kind} lastAgent=${diag.lastAgent ?? '-'} messageEvents=${diag.messageEvents}\n` +
        `  → 可用 cue research "<追问>" --conversation-id ${conversationId} 续跑，或提高 --timeout。\n`,
    );
    return EXIT.ERROR;
  }

  const sources = extractSources(events);
  const timeline = extractTimeline(events);

  if (opts.json) {
    console.log(
      JSON.stringify(
        { conversationId, elapsedMs, reportChars: report.length, report, sources, timeline },
        null,
        2,
      ),
    );
    return EXIT.OK;
  }

  if (opts.output) {
    const out = resolveOutput(opts.output);
    fs.mkdirSync(path.dirname(out) || '.', { recursive: true });
    const appendix = sources.length
      ? `\n\n---\n\n## 来源\n\n${sources.map((s) => `- [${s.index}] ${s.title || s.url} — ${s.url}`).join('\n')}\n`
      : '';
    fs.writeFileSync(out, `${report}${appendix}`, 'utf-8');
    console.log(`报告已写入: ${out} (${report.length} 字, ${(elapsedMs / 1000).toFixed(1)}s, conversation_id=${conversationId})`);
    return EXIT.OK;
  }

  process.stdout.write(`${report}\n\n---\nconversation_id: ${conversationId}\nelapsed: ${(elapsedMs / 1000).toFixed(1)}s\n`);
  return EXIT.OK;
}
