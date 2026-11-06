/**
 * 查询依据组件
 * 展示本次问数用到的指标口径、召回关键词和生成的 SQL，让结果可解释
 */
import { Check, ChevronDown, Code2, Copy, FileSearch, Tag, Target } from "lucide-react";
import { useState } from "react";
import { cn } from "../lib/format";
import type { MetaInfo } from "../types/agent";

export function QueryMeta({ meta }: { meta?: MetaInfo }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!meta) return null;

  const sql = meta.sql ?? "";
  const keywords = meta.keywords ?? [];
  const metrics = meta.metrics ?? [];

  if (!sql && keywords.length === 0 && metrics.length === 0) {
    return null;
  }

  const copySql = async () => {
    if (!sql) return;

    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // 剪贴板不可用时保持静默，用户可以手动选中文本复制
    }
  };

  return (
    <section className="mt-4 border border-ink/10 bg-white/40 shadow-line">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink/10 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <FileSearch className="h-4 w-4 text-moss" aria-hidden="true" />
          查询依据
        </div>

        {sql && (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="inline-flex items-center gap-1.5 border border-ink/15 bg-white/70 px-2.5 py-1 text-xs font-medium text-ink/70 transition hover:border-moss/40 hover:text-ink"
          >
            <Code2 className="h-3.5 w-3.5" aria-hidden="true" />
            {open ? "收起 SQL" : "查看 SQL"}
            <ChevronDown
              className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
              aria-hidden="true"
            />
          </button>
        )}
      </div>

      <div className="space-y-3 px-4 py-3">
        {metrics.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">
              <Target className="h-3.5 w-3.5" aria-hidden="true" />
              本次口径
            </div>
            <div className="flex flex-wrap gap-2">
              {metrics.map((metric, index) => (
                <span
                  key={`${metric.name}-${index}`}
                  title={metric.description || undefined}
                  className="inline-flex items-baseline gap-1.5 border border-moss/25 bg-moss/10 px-2.5 py-1 text-xs text-ink/80"
                >
                  <span className="font-semibold">{metric.name}</span>
                  {metric.description && (
                    <span className="text-ink/55">{metric.description}</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        {keywords.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">
              <Tag className="h-3.5 w-3.5" aria-hidden="true" />
              召回关键词
            </div>
            <div className="flex flex-wrap gap-1.5">
              {keywords.map((keyword, index) => (
                <span
                  key={`${keyword}-${index}`}
                  className="border border-ink/10 bg-white/60 px-2 py-0.5 text-xs text-ink/65"
                >
                  {keyword}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {open && sql && (
        <div className="border-t border-ink/10">
          <div className="flex items-center justify-between gap-3 px-4 py-2">
            <span className="text-xs text-ink/45">共 {sql.split("\n").length} 行</span>
            <button
              type="button"
              onClick={copySql}
              className="inline-flex items-center gap-1.5 text-xs text-ink/60 transition hover:text-ink"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-moss" aria-hidden="true" />
                  已复制
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                  复制 SQL
                </>
              )}
            </button>
          </div>
          <pre className="max-h-[280px] overflow-auto bg-ink/[0.04] px-4 py-3 font-mono text-[12.5px] leading-6 text-ink/85">
            <code>{sql}</code>
          </pre>
        </div>
      )}
    </section>
  );
}
