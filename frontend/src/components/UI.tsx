import React from 'react';
import { AlertCircle, Info, Loader2 } from 'lucide-react';

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gp-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-gp-ink-secondary">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2.5">{actions}</div>}
    </div>
  );
}

export function StatCard({
  label,
  value,
  subtext,
  icon,
  accent = 'primary',
}: {
  label: string;
  value: string | number;
  subtext?: string;
  icon?: React.ReactNode;
  accent?: 'primary' | 'success' | 'warning' | 'error' | 'neutral';
}) {
  const accentMap: Record<string, string> = {
    primary: 'bg-gp-primary-light text-gp-primary border-gp-primary-border',
    success: 'bg-gp-success-bg text-gp-success border-gp-success/20',
    warning: 'bg-gp-warning-bg text-gp-warning border-gp-warning/20',
    error: 'bg-gp-error-bg text-gp-error border-gp-error/20',
    neutral: 'bg-gp-bg text-gp-ink-secondary border-gp-border',
  };

  return (
    <div className="gov-card p-5 flex items-start justify-between gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-gp-ink-secondary">{label}</p>
        <p className="mt-2 text-2xl font-bold text-gp-ink">{value}</p>
        {subtext && <p className="mt-1 text-xs text-gp-ink-muted">{subtext}</p>}
      </div>
      {icon && (
        <div className={`p-2.5 rounded-lg border ${accentMap[accent] || accentMap.primary}`}>
          {icon}
        </div>
      )}
    </div>
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  const styles: Record<string, string> = {
    Critical: 'bg-gp-error-bg text-gp-error border border-gp-error/20',
    High: 'bg-gp-warning-bg text-gp-warning border border-gp-warning/20',
    Moderate: 'bg-gp-primary-light text-gp-primary border border-gp-primary-border',
    Low: 'bg-gp-bg text-gp-ink-secondary border border-gp-border',
    'On Track': 'bg-gp-success-bg text-gp-success border border-gp-success/20',
    'Fully Transferable': 'bg-gp-success-bg text-gp-success border border-gp-success/20',
    'Partially Transferable': 'bg-gp-primary-light text-gp-primary border border-gp-primary-border',
    'Requires Reinforcement': 'bg-gp-warning-bg text-gp-warning border border-gp-warning/20',
    'Not Covered': 'bg-gp-error-bg text-gp-error border border-gp-error/20',
    'Revision Overdue': 'bg-gp-error-bg text-gp-error border border-gp-error/20',
    'Due Soon': 'bg-gp-warning-bg text-gp-warning border border-gp-warning/20',
    Retained: 'bg-gp-success-bg text-gp-success border border-gp-success/20',
    'Baseline Needed': 'bg-gp-bg text-gp-ink-secondary border border-gp-border',
  };
  return (
    <span className={`gov-badge ${styles[priority] || 'bg-gp-bg text-gp-ink-secondary border border-gp-border'}`}>
      {priority}
    </span>
  );
}

export function DemoDataBanner({ show }: { show?: boolean }) {
  if (!show) return null;
  return (
    <div className="mb-5 flex items-start gap-3 rounded-xl border border-gp-primary-border bg-gp-primary-light px-4 py-3 text-xs text-gp-ink">
      <Info className="w-4 h-4 text-gp-primary shrink-0 mt-0.5" />
      <div>
        <span className="font-semibold text-gp-primary">Demonstration Baseline Active:</span> Metrics shown include
        seeded demonstration assessment records so all analytics, transfer, and diagnosis pipelines are immediately
        inspectable. Complete a new diagnostic or topic assessment to incorporate your live performance evidence.
      </div>
    </div>
  );
}

export function LoadingState({ label = 'Loading intelligence modules...' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gp-ink-secondary">
      <Loader2 className="w-7 h-7 animate-spin text-gp-primary mb-3" />
      <p className="text-sm font-medium">{label}</p>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-gp-error/25 bg-gp-error-bg p-4 flex items-center justify-between gap-4 text-gp-error text-sm mb-4">
      <div className="flex items-center gap-2.5">
        <AlertCircle className="w-5 h-5 text-gp-error shrink-0" />
        <span>{message}</span>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3 py-1.5 rounded-lg bg-white border border-gp-error/25 text-xs font-semibold hover:bg-gp-error-bg"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function MarkdownProse({ content }: { content: string }) {
  const lines = content.split('\n');
  return (
    <div className="space-y-1.5 text-sm leading-relaxed text-gp-ink-secondary">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-1" />;
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={i} className="text-sm font-bold text-gp-ink pt-2">
              {trimmed.slice(4)}
            </h4>
          );
        }
        if (trimmed.startsWith('- ')) {
          return (
            <div key={i} className="flex items-start gap-2 pl-1">
              <span className="mt-2 w-1.5 h-1.5 rounded-full bg-gp-primary shrink-0" />
              <span dangerouslySetInnerHTML={{ __html: formatInline(trimmed.slice(2)) }} />
            </div>
          );
        }
        return <p key={i} dangerouslySetInnerHTML={{ __html: formatInline(trimmed) }} />;
      })}
    </div>
  );
}

function formatInline(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-gp-ink">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em class="italic text-gp-ink-secondary">$1</em>');
}
