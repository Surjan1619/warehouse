import { useState } from 'react';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { CLEAR_GROUP_LABELS, TABLE_LABELS } from '../labels';

const GROUPS = [
  {
    key: 'stock',
    title: 'Склад',
    hint: 'Заготовки и куски, резки, сборки, заказы, штучные товары и их приход и расход.',
  },
  {
    key: 'journal',
    title: 'Журнал',
    hint: 'Все записи журнала. Останется одна запись о том, кто и когда очистил базу.',
  },
  {
    key: 'catalog',
    title: 'Справочники',
    hint: 'Материалы, места хранения и типы товаров. Только вместе со складом: заготовки и товары ссылаются на них.',
  },
];

const ERRORS = {
  'Wrong password': 'Неверный пароль',
  'Nothing chosen to clear': 'Выберите, что очистить',
  'The catalog can only be cleared together with the stock': 'Справочники можно очистить только вместе со складом',
};

/**
 * Очистка базы. Только для администратора: сервер проверяет роль и пароль
 * администратора, так что одного украденного токена для удаления мало.
 * Пользователи не удаляются никогда.
 */
export const ClearDatabasePage = () => {
  const [chosen, setChosen] = useState({ stock: false, journal: false, catalog: false });
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const toggle = (key) => (e) => {
    const next = { ...chosen, [key]: e.target.checked };
    // Without the stock the catalog cannot go: the stock refers to it
    if (!next.stock) next.catalog = false;
    setChosen(next);
    setError('');
  };

  const groups = GROUPS.filter((g) => chosen[g.key]);

  const submit = async (e) => {
    e.preventDefault();
    if (groups.length === 0) return setError('Выберите, что очистить');
    const what = groups.map((g) => CLEAR_GROUP_LABELS[g.key]).join(', ');
    if (!window.confirm(`Удалить безвозвратно: ${what}? Отменить это будет нельзя.`)) return;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const answer = await api('/maintenance/clear', { method: 'POST', body: { password, ...chosen } });
      setResult(answer.deleted);
      setChosen({ stock: false, journal: false, catalog: false });
    } catch (err) {
      setError(ERRORS[err.message] || err.message);
    } finally {
      // The password is never kept on the page longer than one attempt
      setPassword('');
      setBusy(false);
    }
  };

  return (
    <Layout title="Очистка базы">
      <section className="card danger-zone">
        <p className="card-hint">
          Удалённые данные <b>вернуть нельзя</b>. Учётные записи пользователей не удаляются. Номера заготовок после очистки
          не начинаются заново, поэтому старые номера на трубах ни с чем не перепутаются.
        </p>
        <form onSubmit={submit}>
          <div className="check-list">
            {GROUPS.map((g) => {
              const disabled = g.key === 'catalog' && !chosen.stock;
              return (
                <label key={g.key} className={disabled ? 'disabled' : ''}>
                  <input type="checkbox" checked={chosen[g.key]} disabled={disabled || busy} onChange={toggle(g.key)} />
                  <span>
                    <b>{g.title}</b>
                    <br />
                    <span className="muted">{g.hint}</span>
                  </span>
                </label>
              );
            })}
          </div>
          <div className="form-row">
            <label>
              Ваш пароль администратора
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                aria-invalid={error === 'Неверный пароль'}
              />
            </label>
            <button className="btn btn-danger" type="submit" disabled={busy || groups.length === 0 || !password}>
              {busy ? 'Удаляем…' : 'Очистить'}
            </button>
          </div>
          {error && <p className="field-error" role="alert">{error}</p>}
        </form>
      </section>

      {result && (
        <section className="card" role="status">
          <h2>База очищена</h2>
          <ul className="list">
            {Object.entries(result).map(([table, rows]) => (
              <li key={table}>
                Удалено {rows} {TABLE_LABELS[table] || table}
              </li>
            ))}
          </ul>
          <p className="muted card-hint">Запись об очистке добавлена в журнал.</p>
        </section>
      )}
    </Layout>
  );
};
