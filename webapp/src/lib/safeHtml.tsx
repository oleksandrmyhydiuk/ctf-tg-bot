import { Fragment } from 'react';
import type { ReactNode } from 'react';

const ALLOWED_TAGS = new Set(['b', 'strong', 'i', 'em', 'code', 'pre', 'br']);

function decodeHtmlEntities(input: string): string {
  return input
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&');
}

interface Token {
  type: 'text' | 'open' | 'close' | 'br';
  value: string;
}

function tokenizeHtml(html: string): Token[] {
  const tokens: Token[] = [];
  const tagRegex = /<(\/?)([a-zA-Z0-9]+)(?:\s[^>]*)?(\/?)>/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tagRegex.exec(html)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({
        type: 'text',
        value: decodeHtmlEntities(html.slice(lastIndex, match.index)),
      });
    }

    const isClose = match[1] === '/';
    const tag = match[2].toLowerCase();

    if (ALLOWED_TAGS.has(tag)) {
      if (tag === 'br') {
        tokens.push({ type: 'br', value: 'br' });
      } else if (isClose) {
        tokens.push({ type: 'close', value: tag });
      } else {
        tokens.push({ type: 'open', value: tag });
      }
    }
    // Disallowed tags (e.g. script, img, iframe, a, style) are silently stripped

    lastIndex = tagRegex.lastIndex;
  }

  if (lastIndex < html.length) {
    tokens.push({
      type: 'text',
      value: decodeHtmlEntities(html.slice(lastIndex)),
    });
  }

  return tokens;
}

interface StackFrame {
  tag: string;
  children: ReactNode[];
}

function renderElement(tag: string, children: ReactNode[], key: number): ReactNode {
  switch (tag) {
    case 'b':
    case 'strong':
      return (
        <strong key={key} className="font-bold text-emerald-100">
          {children}
        </strong>
      );
    case 'i':
    case 'em':
      return (
        <em key={key} className="italic text-slate-200">
          {children}
        </em>
      );
    case 'code':
      return (
        <code
          key={key}
          className="px-1 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-cyan-300 font-mono text-[11px] break-all"
        >
          {children}
        </code>
      );
    case 'pre':
      return (
        <pre
          key={key}
          className="my-1.5 p-2 rounded bg-[#040709] border border-emerald-500/25 text-emerald-300 font-mono text-[11px] whitespace-pre-wrap break-words overflow-x-auto"
        >
          {children}
        </pre>
      );
    default:
      return <Fragment key={key}>{children}</Fragment>;
  }
}

/**
 * Safely renders Telegram-style bot HTML (`<b>`, `<i>`, `<code>`, `<pre>`, `<br>`)
 * into React nodes without `dangerouslySetInnerHTML`. Any unknown tags are stripped.
 */
export function renderSafeBotHtml(html: string): ReactNode {
  if (!html) return null;

  const tokens = tokenizeHtml(html);
  const stack: StackFrame[] = [{ tag: 'root', children: [] }];
  let keyCounter = 0;

  for (const token of tokens) {
    if (token.type === 'text') {
      const parts = token.value.split('\n');
      const target = stack[stack.length - 1].children;
      parts.forEach((part, idx) => {
        if (idx > 0) {
          target.push(<br key={keyCounter++} />);
        }
        if (part) {
          target.push(part);
        }
      });
    } else if (token.type === 'br') {
      stack[stack.length - 1].children.push(<br key={keyCounter++} />);
    } else if (token.type === 'open') {
      stack.push({ tag: token.value, children: [] });
    } else if (token.type === 'close') {
      // Find matching open tag in stack
      let matchIdx = -1;
      for (let i = stack.length - 1; i >= 1; i--) {
        if (stack[i].tag === token.value) {
          matchIdx = i;
          break;
        }
      }
      if (matchIdx !== -1) {
        while (stack.length > matchIdx) {
          const frame = stack.pop()!;
          const node = renderElement(frame.tag, frame.children, keyCounter++);
          stack[stack.length - 1].children.push(node);
        }
      }
    }
  }

  // Close any unclosed tags cleanly
  while (stack.length > 1) {
    const frame = stack.pop()!;
    const node = renderElement(frame.tag, frame.children, keyCounter++);
    stack[stack.length - 1].children.push(node);
  }

  return stack[0].children;
}

/**
 * Strips all HTML tags for plain-text previews (e.g., card subtitles).
 */
export function stripBotHtml(html: string): string {
  return decodeHtmlEntities(html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
}
