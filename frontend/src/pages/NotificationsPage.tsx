import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck } from 'lucide-react';
import { api } from '../api/client';
import { ErrorBanner, LoadingState, PageHeader } from '../components/UI';

export default function NotificationsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.listNotifications();
      setItems(res.notifications || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load notifications');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const markRead = async (id: number) => {
    await api.markNotificationRead(id);
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
  };

  const markAll = async () => {
    await api.markAllNotificationsRead();
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  if (loading) return <LoadingState label="Loading notifications..." />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Notifications"
        subtitle="Revision triggers, study plan updates, assessment reminders, and evidence-based insights."
        actions={
          <button
            onClick={markAll}
            className="gov-btn-secondary px-3.5 py-2 text-xs"
          >
            <CheckCheck className="w-4 h-4 text-gp-primary" /> Mark All Read
          </button>
        }
      />

      <div className="gov-card divide-y divide-gp-divider">
        {items.length === 0 ? (
          <div className="p-10 text-center text-sm text-gp-ink-muted">No notifications yet.</div>
        ) : (
          items.map((n) => (
            <div
              key={n.id}
              className={`p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                n.is_read ? 'bg-gp-surface' : 'bg-gp-primary-light/40'
              }`}
            >
              <div className="flex items-start gap-3">
                <div
                  className={`p-2 rounded-lg border ${
                    n.is_read
                      ? 'bg-gp-bg text-gp-ink-muted border-gp-border'
                      : 'bg-gp-primary-soft text-gp-primary border-gp-primary-border'
                  }`}
                >
                  <Bell className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-gp-ink">{n.title}</h3>
                    {!n.is_read && <span className="w-2 h-2 rounded-full bg-gp-primary" />}
                  </div>
                  <p className="text-xs text-gp-ink-secondary mt-1">{n.message}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => {
                    markRead(n.id);
                    navigate(n.action_route || '/');
                  }}
                  className="gov-btn-primary px-3 py-1.5 text-xs"
                >
                  Open Module
                </button>
                {!n.is_read && (
                  <button
                    onClick={() => markRead(n.id)}
                    className="gov-btn-secondary px-3 py-1.5 text-xs"
                  >
                    Mark Read
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
