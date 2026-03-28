"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const components: Components = {
  h1: ({ children }) => (
    <h1 className="mb-3 text-lg font-bold text-gray-900">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-4 text-base font-semibold text-gray-900">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-3 text-sm font-semibold text-gray-800">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="mb-2 text-sm leading-relaxed text-gray-700">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 ml-4 list-disc space-y-1 text-sm text-gray-700">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 ml-4 list-decimal space-y-1 text-sm text-gray-700">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-gray-900">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-gray-600">{children}</em>,
  code: ({ children, className }) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs text-gray-800">
          {children}
        </code>
      );
    }
    return (
      <code className="block overflow-x-auto rounded-md bg-gray-50 p-3 font-mono text-xs leading-relaxed text-gray-700 border border-gray-100">
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="mb-2">{children}</pre>,
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-2 border-gray-300 pl-3 text-sm italic text-gray-500">
      {children}
    </blockquote>
  ),
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto">
      <table className="w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-gray-200 text-left text-xs font-medium text-gray-500">
      {children}
    </thead>
  ),
  tbody: ({ children }) => <tbody className="divide-y divide-gray-100">{children}</tbody>,
  th: ({ children }) => <th className="px-2 py-1.5">{children}</th>,
  td: ({ children }) => <td className="px-2 py-1.5 text-gray-700">{children}</td>,
  hr: () => <hr className="my-3 border-gray-200" />,
  a: ({ children, href }) => (
    <a href={href} className="text-blue-600 underline underline-offset-2" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

export function Markdown({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
