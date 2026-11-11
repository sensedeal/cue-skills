/**
 * The exact file set that goes into the uploaded ZIP.
 *
 * Doubao reads plugin.json / mcp.json / com.doubao/ / skills/ from the ZIP root.
 * Local tooling (scripts/, README.md, .gitignore, dist/) is deliberately excluded.
 * Both validate.mjs and pack.mjs import this list so they can never disagree.
 */
import fs from 'node:fs';
import path from 'node:path';

export const INCLUDE = ['plugin.json', 'mcp.json', 'com.doubao', 'skills'];

export function collectPackageFiles(root) {
  const out = [];
  const walk = (rel) => {
    const abs = path.join(root, rel);
    const stat = fs.statSync(abs);
    if (stat.isDirectory()) {
      for (const name of fs.readdirSync(abs).sort()) {
        if (name === '.DS_Store' || name === '__MACOSX') continue;
        walk(path.posix.join(rel, name));
      }
    } else if (stat.isFile()) {
      out.push({ rel, abs, size: stat.size });
    }
  };
  for (const entry of INCLUDE) {
    const abs = path.join(root, entry);
    if (!fs.existsSync(abs)) throw new Error(`Missing package entry: ${entry}`);
    walk(entry);
  }
  return out;
}
