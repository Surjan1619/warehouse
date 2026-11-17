import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { STATUS_LABELS } from '../labels';
import { useAction, useList } from '../hooks';
import { PAGE_SIZE, metres, pageCount, pageQuery, pageRange } from '../pagination';

const materialTitle = (m) => [m.name, m.color, m.sku && `арт. ${m.sku}`].filter(Boolean).join(' · ');

const lengthSpan = (row) =>
  row.min_length_mm === row.max_length_mm
    ? `все по ${row.min_length_mm.toLocaleString('ru-RU')} мм`
    : `от ${row.min_length_mm.toLocaleString('ru-RU')} до ${row.max_length_mm.toLocaleString('ru-RU')} мм`;

// Остатки заготовок: каждая труба или профиль — отдельная запись со своей длиной.
// Список не выводится целиком: сначала плитки по материалам, по щелчку —
// заготовки этого материала постранично. Приход — на странице /receive.
export const StockPage = () => {
  const [params] = useSearchParams();
  const [status, setStatus] = useState('in_stock');
  const [search, setSearch] = useState('');
  // The material whose pieces are listed: none until a tile is clicked, or the
  // one passed by "Посмотреть в остатках" after a receipt
  const [materialId, setMaterialId] = useState(() => Number(params.get('material')) || null);
  const [page, setPage] = useState(0);
  // A number is looked up as soon as it has a digit; the status filter is
  // ignored then, because the piece may already be cut or used
  const searchNumber = search.replace(/\D/g, '');
  const [summary, reloadSummary, summaryError] = useList(
    searchNumber ? '' : `/stock-items/summary${status ? `?status=${status}` : ''}`,
  );
  const [found, reloadFound, foundError] = useList(searchNumber ? `/stock-items/?number=${searchNumber}` : '');
  const [pageData, reloadPage, pageError] = useList(
    !searchNumber && materialId ? `/stock-items/page?${pageQuery({ status, materialId, page })}` : '',
  );
  const listing = Boolean(searchNumber || materialId);
  const items = searchNumber ? found : (pageData.items ?? []);
  const total = searchNumber ? found.length : (pageData.total ?? 0);
  const pages = pageCount(total);
  const loadError = summaryError || foundError || pageError;
  const reload = () => Promise.all([reloadSummary(), reloadFound(), reloadPage()]);
  const [materials] = useList('/materials/');
  // Actions on rows of the list: cancel a cut, correct a length
  const rowAction = useAction();

  const chooseStatus = (value) => {
    setStatus(value);
    setPage(0);
  };

  // A second click on the open material closes its list
  const chooseMaterial = (id) => {
    setMaterialId(id === materialId ? null : id);
    setPage(0);
  };

  // Undo the cut this piece was cut by: it returns to stock, its pieces are cancelled
  const cancelCut = async (item) => {
    if (!window.confirm(`Отменить резку заготовки ${item.code}? Она вернётся на склад, её куски будут отменены.`)) {
      return;
    }
    const ok = await rowAction.run(async () => {
      const cuts = await api(`/cuts/?source_item_id=${item.id}&limit=20`);
      const active = cuts.find((c) => !c.cancelled_at);
      if (!active) throw new Error('Действующая резка этой заготовки не найдена');
      await api(`/cuts/${active.id}/cancel`, { method: 'POST' });
    }, `Резка отменена: ${item.code} снова на складе`);
    if (ok) await reload();
  };

  // Correct a length entered wrongly at receipt; the server refuses it for cut pieces
  const correctLength = async (item) => {
    const answer = window.prompt(`Правильная длина ${item.code}, мм`, String(item.length_mm));
    if (answer === null) return;
    const length = Number(answer.replace(/\s/g, ''));
    if (!Number.isInteger(length) || length <= 0) {
      window.alert('Длина — целое число миллиметров больше нуля');
      return;
    }
    if (length === item.length_mm) return;
    const ok = await rowAction.run(async () => {
      await api(`/stock-items/${item.id}`, { method: 'PATCH', body: { length_mm: length } });
    }, `Длина ${item.code} исправлена: ${length.toLocaleString('ru-RU')} мм`);
    if (ok) await reload();
  };

  // Orders are not used on the site yet; keep the column out of the way until they are
  const showOrders = items.some((item) => item.order);
  const summaryCount = summary.reduce((sum, row) => sum + row.count, 0);
  const summaryLength = summary.reduce((sum, row) => sum + row.total_length_mm, 0);
  const openMaterial =
    summary.find((row) => row.material.id === materialId)?.material || materials.find((m) => m.id === materialId);

  return (
    <Layout title="Остатки заготовок">
      <section className="card">
        <div className="card-head">
          <p className="muted card-hint">
            Принять новые трубы — в разделе <Link to="/receive">«Приход»</Link>.
          </p>
          <label className="inline-filter">
            Номер
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="T-000123 или 123"
              maxLength={30}
            />
          </label>
          <label className="inline-filter">
            Статус
            <select value={status} disabled={Boolean(searchNumber)} onChange={(e) => chooseStatus(e.target.value)}>
              <option value="">Все</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
        </div>

        {!searchNumber &&
          (summary.length === 0 ? (
            <p className="muted">Заготовок с таким статусом нет</p>
          ) : (
            <>
              <p className="muted card-hint">
                Всего: {summaryCount} шт., {metres(summaryLength)}. Выберите материал, чтобы увидеть заготовки.
              </p>
              <div className="stock-tiles">
                {summary.map((row) => (
                  <button
                    key={row.material.id}
                    type="button"
                    className={`stock-tile${row.material.id === materialId ? ' selected' : ''}`}
                    aria-pressed={row.material.id === materialId}
                    onClick={() => chooseMaterial(row.material.id)}
                  >
                    <span className="stock-tile-name">{materialTitle(row.material)}</span>
                    <span className="stock-tile-count">
                      {row.count} шт. · {metres(row.total_length_mm)}
                    </span>
                    <span className="muted">{lengthSpan(row)}</span>
                  </button>
                ))}
              </div>
            </>
          ))}

        {listing && (
          <>
            {!searchNumber && openMaterial && (
              <div className="list-head">
                <h3>{materialTitle(openMaterial)}</h3>
                <button type="button" className="btn btn-ghost" onClick={() => chooseMaterial(materialId)}>
                  Свернуть
                </button>
              </div>
            )}
            {items.length === 0 ? (
              <p className="muted">
                {searchNumber
                  ? `Заготовки с номером T-${searchNumber.padStart(6, '0')} нет`
                  : total > 0
                    ? 'На этой странице заготовок больше нет'
                    : 'Заготовок этого материала с таким статусом нет'}
              </p>
            ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Номер</th>
                    {searchNumber && <th>Материал</th>}
                    <th className="num">Длина, мм</th>
                    <th>Статус</th>
                    <th>Место</th>
                    {showOrders && <th>Заказ</th>}
                    <th>Добавил</th>
                    <th>Примечание</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="code">{item.code}</td>
                      {searchNumber && <td>{materialTitle(item.material)}</td>}
                      <td className="num">{item.length_mm.toLocaleString('ru-RU')}</td>
                      <td><span className={`status status-${item.status}`}>{STATUS_LABELS[item.status]}</span></td>
                      <td>{item.location?.name || '—'}</td>
                      {showOrders && <td>{item.order?.number || '—'}</td>}
                      <td>{item.created_by?.username || '—'}</td>
                      <td className="muted note">{item.note || ''}</td>
                      <td className="actions">
                        {item.status === 'in_stock' && (
                          <Link className="btn btn-ghost" to={`/cut?item=${item.id}&material=${item.material.id}`}>Резать</Link>
                        )}
                        {!item.parent_id && ['in_stock', 'reserved'].includes(item.status) && (
                          <button
                            type="button"
                            className="btn btn-ghost"
                            title="Исправить длину, если её ввели неверно при приходе"
                            disabled={rowAction.busy}
                            onClick={() => correctLength(item)}
                          >
                            Длина
                          </button>
                        )}
                        {item.status === 'cut' && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-warn"
                            disabled={rowAction.busy}
                            onClick={() => cancelCut(item)}
                          >
                            Отменить резку
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}
            {!searchNumber && total > PAGE_SIZE && (
              <div className="pager">
                <button type="button" className="btn btn-ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>
                  ← Назад
                </button>
                <span className="muted">
                  {pageRange(page, total)} · страница {page + 1} из {pages}
                </span>
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={page >= pages - 1}
                  onClick={() => setPage(page + 1)}
                >
                  Вперёд →
                </button>
              </div>
            )}
          </>
        )}
        <Messages error={rowAction.error || loadError} notice={rowAction.notice} />
      </section>
    </Layout>
  );
};
