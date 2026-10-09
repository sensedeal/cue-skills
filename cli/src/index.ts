#!/usr/bin/env node
/**
 * @cueai/cue-cli — local CLI bridge for Cue (cuecue.cn) deep research.
 */

import { Command } from 'commander';
import { login, logout, status } from './commands/auth.js';
import { doctor } from './commands/doctor.js';
import { getTemplate, listTemplates } from './commands/playbook.js';
import { research } from './commands/research.js';
import { CueError, EXIT } from './errors.js';
import { CLI_VERSION } from './version.js';

const program = new Command();
program.name('cue').description('Cue (cuecue.cn) CLI — deep research from the terminal').version(CLI_VERSION);

const auth = program.command('auth').description('Manage Cue credentials');

auth
  .command('login')
  .description('Authorize this machine (device flow, or --api-key for a key you already have)')
  .option('--api-key <key>', '直接写入一个已有的 API key（跳过浏览器）')
  .option('--base-url <url>', 'Cue API base URL')
  .option('--json', 'JSON 输出')
  .action(async (opts) => {
    process.exitCode = await login({ apiKey: opts.apiKey, base: opts.baseUrl, json: Boolean(opts.json) });
  });

auth
  .command('status')
  .description('Check whether this machine is authorized (no side effects)')
  .option('--base-url <url>', 'Cue API base URL')
  .option('--json', 'JSON 输出')
  .action(async (opts) => {
    process.exitCode = await status({ base: opts.baseUrl, json: Boolean(opts.json) });
  });

auth
  .command('logout')
  .description('Revoke the session and clear locally stored credentials')
  .option('--base-url <url>', 'Cue API base URL')
  .option('--json', 'JSON 输出')
  .action(async (opts) => {
    process.exitCode = await logout({ base: opts.baseUrl, json: Boolean(opts.json) });
  });

program
  .command('research')
  .alias('r')
  .argument('<query>', '研究问题（自然语言）')
  .description('Run one deep research job and print the Markdown report')
  .option('--template-id <id>', '使用指定搭子模板')
  .option('--conversation-id <id>', '续接已有会话')
  .option('-o, --output <file>', '报告落盘（Markdown）')
  .option('--timeout <seconds>', '整轮超时（默认 1200s）', '1200')
  .option('--base-url <url>', 'Cue API base URL')
  .option('--json', '输出结构化 JSON（报告 + 来源 + 时间线）')
  .option('-q, --quiet', '不打印进度')
  .action(async (query: string, opts) => {
    process.exitCode = await research(query, {
      templateId: opts.templateId,
      conversationId: opts.conversationId,
      output: opts.output,
      timeoutMs: Number(opts.timeout) * 1000,
      base: opts.baseUrl,
      json: Boolean(opts.json),
      quiet: Boolean(opts.quiet),
    });
  });

const playbook = program.command('playbook').description('Browse research templates');

playbook
  .command('list')
  .description('List your templates')
  .option('--mode <mode>', 'all / unread / timer / is_frequent / is_me / is_update', 'is_me')
  .option('--include-system', 'include system templates')
  .option('--base-url <url>', 'Cue API base URL')
  .option('--json', 'JSON 输出')
  .action(async (opts) => {
    process.exitCode = await listTemplates({
      mode: opts.mode,
      includeSystem: Boolean(opts.includeSystem),
      base: opts.baseUrl,
      json: Boolean(opts.json),
    });
  });

playbook
  .command('get')
  .argument('<id>', 'template_id')
  .description('Show one template')
  .option('--base-url <url>', 'Cue API base URL')
  .option('--json', 'JSON 输出')
  .action(async (id: string, opts) => {
    process.exitCode = await getTemplate(id, { base: opts.baseUrl, json: Boolean(opts.json) });
  });

program
  .command('doctor')
  .description('Print an environment self-check as JSON')
  .option('--base-url <url>', 'Cue API base URL')
  .action(async (opts) => {
    process.exitCode = await doctor({ base: opts.baseUrl });
  });

async function main(): Promise<void> {
  await program.parseAsync(process.argv);
}

main().catch((err: unknown) => {
  if (err instanceof CueError) {
    console.error(`❌ ${err.message}`);
    process.exit(err.code || EXIT.ERROR);
  }
  console.error(err instanceof Error ? `❌ ${err.message}` : err);
  process.exit(EXIT.ERROR);
});
