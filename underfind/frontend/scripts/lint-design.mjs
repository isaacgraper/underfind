// Enforces the DESIGN.md lint rules on the new frontend (src/app, ui, views, theme). Exit 1 on any violation.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..', 'src');
const dirs = ['app', 'ui', 'views', 'theme'];
const cssRules = [
  [/transition\s*:\s*all\b/, 'transition: all'],
  [/scale\(\s*0\s*\)/, 'scale(0)'],
  [/\bease-in\b(?!-out)/, 'ease-in'],
  [/outline\s*:\s*(none|0)\b/, 'outline: none'],
  [/font-size\s*:\s*(?:[0-9]|1[01])(?:\.\d+)?px/, 'font-size below 12px'],
];
const hex = /#[0-9a-fA-F]{3,8}\b/;

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

const problems = [];

for (const file of dirs.flatMap((d) => walk(path.join(root, d)))) {
  const rel = path.relative(root, file);
  const text = readFileSync(file, 'utf8');

  if (file.endsWith('.css')) {
    // Strip comments, then track whether each :hover sits inside a hover media query.
    const code = text.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
    const lines = code.split('\n');
    let depth = 0;
    let hoverDepth = -1;

    lines.forEach((line, i) => {
      for (const [re, label] of cssRules) if (re.test(line)) problems.push(`${rel}:${i + 1} ${label}`);
      if (!rel.endsWith('tokens.css') && hex.test(line)) problems.push(`${rel}:${i + 1} raw hex outside tokens.css`);
      if (/@media[^{]*hover:\s*hover/.test(line)) hoverDepth = depth;
      if (/:hover/.test(line) && hoverDepth < 0) problems.push(`${rel}:${i + 1} :hover outside (hover: hover) media query`);
      for (const ch of line) {
        if (ch === '{') depth += 1;
        if (ch === '}') {
          depth -= 1;
          if (hoverDepth >= 0 && depth <= hoverDepth) hoverDepth = -1;
        }
      }
    });
  } else if (/\.(tsx?|ts)$/.test(file)) {
    text.split('\n').forEach((line, i) => {
      if (hex.test(line) && !/&#|href|url\(/.test(line)) problems.push(`${rel}:${i + 1} raw hex in TSX`);
    });
  }
}

if (problems.length) {
  console.error(`Design lint failed:\n${problems.map((p) => `  ${p}`).join('\n')}`);
  process.exit(1);
}

console.log('Design lint passed.');
