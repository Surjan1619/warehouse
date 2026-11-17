import { useEffect, useState } from 'react';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { ACTION_LABELS } from '../labels';
import { useList } from '../hooks';
import { describeEvent, lengthOf, subjectOf } from '../journalText';

const PAGE_SIZE = 50;

const formatTime = (iso) =>
  new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

// A date input gives "2026-11-15" meaning the viewer's local day. The server
// stores UTC, so send the exact moment the local day starts.
const startOfLocalDay = (date, addDays = 0) => {
  const [year, month, day] = date.split('-').map(Number);
  return new Date(year, month - 1, day + addDays).toISOString();
};

const buildQuery = (filters, offset) => {
  const params = new URLSearchParams({ limit: PAGE_SIZE, offset });
  if (filters.user_id) params.set('user_id', filters.user_id);
  if (filters.action) params.set('action', filters.action);
  if (filters.date_from) params.set('date_from', startOfLocalDay(filters.date_from));
  // "По" is inclusive for the viewer, so the range ends when the next day starts
  if (filters.date_to) params.set('date_to', startOfLocalDay(filters.date_to, 1));
  return `/activity/?${params}`;
};

const noFilters = { user_id: '', action: '', date_from: '', date_to: '' };

// Журнал действий: кто, что сделал, с чем и когда. Только для администратора.
export const JournalPage = () => {
  const [users] = useList('/users/');
  const [filters, setFilters] = useState(noFilters);
  const [page, setPage] = useState({ items: [], total: 0 });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const query = buildQuery(filters, 0);
  useEffect(() => {
    let cancelled = false;
    api(query)
      .then((data) => !cancelled && (setPage(data), setError('')))
      .catch((err) => !cancelled && setError(err.message));
    // A slow answer to an older filter must not overwrite a newer one
    return () => {
      cancelled = true;
    };
  }, [query]);

  const loadMore = async () => {
    setBusy(true);
    try {
      const next = await api(buildQuery(filters, page.items.length));
      setPage({ items: [...page.items, ...next.items], total: next.total });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const set = (field) => (e) => setFilters({ ...filters, [field]: e.target.value });
  const filtered = Object.values(filters).some(Boolean);

  return (
    <Layout title="Журнал">
      <section className="card">
        <div className="form-row">
          <label>
            Работник
            <select value={filters.user_id} onChange={set('user_id')}>
              <option value="">Все</option>
              {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
            </select>
          </label>
          <label>
            Действие
            <select value={filters.action} onChange={set('action')}>
              <option value="">Все</option>
              {Object.entries(ACTION_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            С
            <input type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={set('date_from')} />
          </label>
          <label>
            По
            <input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={set('date_to')} />
          </label>
          <button type="button" className="btn btn-ghost" disabled={!filtered} onClick={() => setFilters(noFilters)}>
            Сбросить
          </button>
        </div>
        <Messages error={error} />
      </section>

      <section className="card">
        {page.items.length === 0 ? (
          <p className="muted">{filtered ? 'По этим условиям записей нет' : 'В журнале пока нет записей'}</p>
        ) : (
          <>
            <p className="muted card-hint">
              Показано {page.items.length} из {page.total}
            </p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Когда</th>
                    <th>Работник</th>
                    <th>Действие</th>
                    <th>Что сделано</th>
                    <th>Материал / товар</th>
                    <th className="num">Штук</th>
                    <th className="num">Длина, мм</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((event) => (
                    <tr key={event.id}>
                      <td>{formatTime(event.created_at)}</td>
                      <td>{event.user?.username || '—'}</td>
                      <td><span className={`status action-${event.action}`}>{ACTION_LABELS[event.action]}</span></td>
                      <td className="wrap">{describeEvent(event)}</td>
                      <td>{subjectOf(event)}</td>
                      <td className="num">{event.quantity || '—'}</td>
                      <td className="num">{lengthOf(event)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {page.items.length < page.total && (
              <button type="button" className="btn btn-ghost form-submit" disabled={busy} onClick={loadMore}>
                Показать ещё
              </button>
            )}
          </>
        )}
      </section>
    </Layout>
  );
};
