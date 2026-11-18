import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { useList } from '../hooks';
import {
  IMPORT_ERRORS,
  codeRange,
  newGoodsRows,
  rowOutcome,
  rowSource,
  rowTarget,
  summaryText,
  typesPayload,
} from '../importText';
import { amount } from '../productOptions';

const errorText = (err) => IMPORT_ERRORS[err.message] || err.message;

const formatDate = (iso) => (iso ? new Date(iso).toLocaleDateString('ru-RU') : '');

/**
 * Приход по документу поставщика: файл Excel → предпросмотр → «Добавить на склад».
 * Сервер сам читает файл и при подтверждении читает его ещё раз, поэтому на склад
 * попадает ровно то, что написано в документе. Ручной приход остаётся на соседних вкладках.
 */
export const ImportDocumentPage = () => {
  const [types] = useList('/products/types');
  const [locations] = useList('/locations/');
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [locationId, setLocationId] = useState('');
  const [typeChoices, setTypeChoices] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  // A new file input after each import, so the same file can be chosen again
  const [pickKey, setPickKey] = useState(0);

  const send = (path) => {
    const files = new FormData();
    files.append('file', file);
    if (path === '/imports/') {
      if (locationId) files.append('location_id', locationId);
      files.append('product_types', typesPayload(typeChoices));
    }
    return api(path, { method: 'POST', files });
  };

  const choose = async (e) => {
    const chosen = e.target.files?.[0] ?? null;
    setFile(chosen);
    setPreview(null);
    setResult(null);
    setTypeChoices({});
    setError('');
    if (!chosen) return;
    setBusy(true);
    try {
      const files = new FormData();
      files.append('file', chosen);
      setPreview(await api('/imports/preview', { method: 'POST', files }));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    setBusy(true);
    setError('');
    try {
      setResult(await send('/imports/'));
      setPreview(null);
      setFile(null);
      setPickKey((k) => k + 1);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const newGoods = preview ? newGoodsRows(preview.rows) : [];

  return (
    <Layout title="Приход по документу">
      <section className="card">
        <p className="muted card-hint">
          Загрузите спецификацию поставщика (файл Excel .xlsx или .xlsm). Программа покажет, что добавится, и ничего не
          изменит, пока вы не нажмёте «Добавить на склад». Принять вручную можно на вкладках{' '}
          <Link to="/receive">«Заготовки»</Link> и <Link to="/receive/products">«Товары»</Link>.
        </p>
        <label className="file-pick">
          Документ
          <input
            type="file"
            accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12"
            onChange={choose}
            disabled={busy}
            key={pickKey}
          />
        </label>
        {busy && !preview && <p className="muted">Читаем документ…</p>}
        <Messages error={error} />
      </section>

      {preview && (
        <section className="card">
          <div className="card-head">
            <h2>
              {preview.number ? `Спецификация № ${preview.number}` : preview.filename}
              {preview.date && ` от ${formatDate(preview.date)}`}
            </h2>
          </div>
          {preview.supplier && <p className="muted">Поставщик: {preview.supplier}</p>}

          {preview.previous && (
            <p className="field-error" role="alert">
              Этот документ уже добавлен на склад {formatDate(preview.previous.created_at)}
              {preview.previous.user && ` (${preview.previous.user.username})`}. Второй раз его добавить нельзя — даже
              копию в другой валюте.
            </p>
          )}
          {preview.summary.problems > 0 && (
            <p className="field-error" role="alert">
              Строк с ошибками: {preview.summary.problems}. Они отмечены красным; исправьте файл и загрузите его снова.
            </p>
          )}

          <p>
            <b>Добавится:</b> {summaryText(preview.summary)}
          </p>

          <div className="table-wrap">
            <table className="table import-table">
              <thead>
                <tr>
                  <th className="num">Стр.</th>
                  <th>Код</th>
                  <th>Наименование</th>
                  <th className="num">В документе</th>
                  <th>На склад</th>
                  <th>Куда</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => {
                  const target = rowTarget(row);
                  return (
                    <tr key={row.line} className={row.problem ? 'has-error' : ''}>
                      <td className="num muted">{row.line}</td>
                      <td className="code">{row.code || '—'}</td>
                      <td>{row.title}</td>
                      <td className="num">{rowSource(row)}</td>
                      <td className={row.problem ? 'field-error' : ''}>{rowOutcome(row)}</td>
                      <td>
                        {!row.kind ? (
                          '—'
                        ) : target ? (
                          <span>
                            {target}
                            {row.product && (
                              <span className="muted"> (сейчас {amount(row.product.quantity, row.product.unit)})</span>
                            )}
                          </span>
                        ) : (
                          <span className="badge-new">{row.kind === 'stock' ? 'новый материал' : 'новый товар'}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {preview.can_import && (
            <>
              <div className="form-row">
                <label>
                  Место хранения для всего
                  <select value={locationId} onChange={(e) => setLocationId(e.target.value)} disabled={busy}>
                    <option value="">— не указывать —</option>
                    {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                  </select>
                </label>
              </div>

              {newGoods.length > 0 && types.length > 0 && (
                <details className="import-types">
                  <summary>Типы для новых товаров ({newGoods.length}) — по желанию</summary>
                  {newGoods.map((row) => (
                    <label key={row.line} className="form-row">
                      <span className="wide">{row.title}</span>
                      <select
                        value={typeChoices[row.line] ?? ''}
                        onChange={(e) => setTypeChoices({ ...typeChoices, [row.line]: e.target.value })}
                        disabled={busy}
                      >
                        <option value="">— без типа —</option>
                        {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                    </label>
                  ))}
                </details>
              )}

              <div className="result-actions">
                <button type="button" className="btn" onClick={confirm} disabled={busy}>
                  {busy ? 'Добавляем…' : 'Добавить на склад'}
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {result && (
        <section className="card" role="status">
          <h2>
            Документ {result.number ? `№ ${result.number}` : result.filename} добавлен на склад
          </h2>
          <p>
            Строк: {result.rows}, заготовок: {result.stock_pieces.toLocaleString('ru-RU')}, новых материалов:{' '}
            {result.new_materials}, новых товаров: {result.new_products}.
          </p>
          <ul className="list">
            {result.result.map((row) => (
              <li key={row.line}>
                {row.title}:{' '}
                {row.kind === 'stock' ? (
                  <>
                    {row.pieces} × {row.length_mm.toLocaleString('ru-RU')} мм,{' '}
                    <span className="code">{codeRange(row.first_item_id, row.last_item_id)}</span>
                  </>
                ) : (
                  <>
                    +{amount(row.count, row.unit)}, теперь {amount(row.quantity_after, row.unit)}
                  </>
                )}
              </li>
            ))}
          </ul>
          <p className="muted card-hint">
            Номера заготовок нужно написать на трубах. Посмотреть их — в разделе <Link to="/stock">«Остатки»</Link>.
          </p>
        </section>
      )}
    </Layout>
  );
};
