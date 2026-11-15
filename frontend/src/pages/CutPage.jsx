import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { STATUS_LABELS } from '../labels';
import { useAction, useList } from '../hooks';

const newPiece = () => ({ length_mm: '', used: true, times: '2' });

// Upper bound of rows on the page; the server accepts up to 100 pieces per cut
const MAX_PIECES = 100;

const mm = (value) => `${value.toLocaleString('ru-RU')} мм`;

const materialTitle = (m) => [m.name, m.color, m.sku && `арт. ${m.sku}`].filter(Boolean).join(' · ');

const REMAINDER_TEXT = {
  none: 'без остатка',
  stock: 'вернётся на склад',
  scrap: 'уйдёт в отходы',
};

/**
 * Резка в два шага:
 * 1. работник выбирает материал и вводит нужные куски;
 * 2. система показывает, из каких заготовок их можно вырезать, начиная
 *    с самой экономной, и работник подтверждает резку.
 * Подбор и расчёт остатка делает сервер (POST /cuts/suggest).
 */
export const CutPage = () => {
  const [params] = useSearchParams();
  // "Резать" on the stock page passes the piece the worker wants to cut
  const preferredId = Number(params.get('item')) || null;
  const preferredMaterial = params.get('material') || '';

  const [materials, , loadError] = useList('/materials/');
  const [materialId, setMaterialId] = useState(preferredMaterial);
  const [pieces, setPieces] = useState([newPiece()]);
  const [suggestion, setSuggestion] = useState(null);
  const [chosenId, setChosenId] = useState(null);
  const [result, setResult] = useState(null);
  const { error, busy, run } = useAction();

  const lengths = pieces.map((p) => Number(p.length_mm));
  const piecesValid = lengths.every((l) => l > 0);
  const piecesTotal = lengths.reduce((sum, l) => sum + (l > 0 ? l : 0), 0);

  // Any change to the request makes the shown options stale
  const changeRequest = (change) => {
    change();
    setSuggestion(null);
    setChosenId(null);
  };

  const updatePiece = (index, changes) =>
    setPieces(pieces.map((p, i) => (i === index ? { ...p, ...changes } : p)));

  // Replace one row with `times` identical rows, so that equal pieces
  // do not have to be typed one by one
  const multiplyPiece = (index) => {
    const piece = pieces[index];
    const times = Math.floor(Number(piece.times));
    if (!(times >= 2)) return;
    const copies = Array.from({ length: times }, () => ({ ...piece, times: '2' }));
    changeRequest(() =>
      setPieces([...pieces.slice(0, index), ...copies, ...pieces.slice(index + 1)].slice(0, MAX_PIECES)),
    );
  };

  const findSources = async (e) => {
    e.preventDefault();
    setResult(null);
    let found = null;
    const ok = await run(async () => {
      found = await api('/cuts/suggest', {
        method: 'POST',
        body: { material_id: Number(materialId), pieces: lengths },
      });
    }, '');
    if (!ok) return;

    // In a group of identical pieces, take the one the worker came with
    const candidates = found.candidates.map((c) =>
      preferredId && c.item_ids.includes(preferredId) ? { ...c, pick_id: preferredId } : { ...c, pick_id: c.item.id },
    );
    const preferred = candidates.find((c) => c.pick_id === preferredId);
    setSuggestion({ ...found, candidates });
    setChosenId((preferred || candidates[0])?.pick_id ?? null);
  };

  const cut = async () => {
    let operation = null;
    const ok = await run(async () => {
      operation = await api('/cuts/', {
        method: 'POST',
        body: {
          source_item_id: chosenId,
          pieces: pieces.map((p) => ({ length_mm: Number(p.length_mm), used: p.used })),
        },
      });
    }, '');
    if (!ok) return;
    setResult(operation);
    setSuggestion(null);
    setChosenId(null);
    setPieces([newPiece()]);
  };

  const chosen = suggestion?.candidates.find((c) => c.pick_id === chosenId);
  const codeOf = (candidate) => `T-${String(candidate.pick_id).padStart(6, '0')}`;

  return (
    <Layout title="Резка">
      <section className="card">
        <h2>1. Что нужно получить</h2>
        {materials.length === 0 && !loadError ? (
          <p className="muted">
            Сначала добавьте материал в <Link to="/catalog">справочниках</Link> и примите заготовки на странице{' '}
            <Link to="/stock">«Заготовки»</Link>.
          </p>
        ) : (
          <form onSubmit={findSources}>
            <div className="form-row">
              <label className="wide">
                Материал
                <select
                  value={materialId}
                  onChange={(e) => changeRequest(() => setMaterialId(e.target.value))}
                  required
                >
                  <option value="">— выберите —</option>
                  {materials.map((m) => <option key={m.id} value={m.id}>{materialTitle(m)}</option>)}
                </select>
              </label>
            </div>

            <h2 className="section-title">Куски</h2>
            {pieces.map((piece, index) => (
              <div className="form-row piece-row" key={index}>
                <label>
                  Длина, мм
                  <input
                    type="number"
                    value={piece.length_mm}
                    onChange={(e) => changeRequest(() => updatePiece(index, { length_mm: e.target.value }))}
                    min={1}
                    step={1}
                    required
                  />
                </label>
                <label>
                  Куда
                  <select
                    value={piece.used ? 'used' : 'stock'}
                    onChange={(e) => updatePiece(index, { used: e.target.value === 'used' })}
                  >
                    <option value="used">Использован</option>
                    <option value="stock">На склад</option>
                  </select>
                </label>
                <div className="multiply">
                  <span>×</span>
                  <input
                    type="number"
                    aria-label="Сколько одинаковых кусков"
                    value={piece.times}
                    onChange={(e) => updatePiece(index, { times: e.target.value })}
                    min={2}
                    max={MAX_PIECES}
                    step={1}
                  />
                  <button
                    type="button"
                    className="btn btn-ghost"
                    title="Заменить эту строку на несколько одинаковых"
                    disabled={!(Number(piece.length_mm) > 0) || !(Number(piece.times) >= 2)}
                    onClick={() => multiplyPiece(index)}
                  >
                    Умножить
                  </button>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={pieces.length === 1}
                  onClick={() => changeRequest(() => setPieces(pieces.filter((_, i) => i !== index)))}
                >
                  Убрать
                </button>
              </div>
            ))}
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => changeRequest(() => setPieces([...pieces, newPiece()]))}
            >
              + Ещё кусок
            </button>

            <div className="cut-summary">
              <div>
                Кусков: <b>{pieces.length}</b>, всего <b>{mm(piecesTotal)}</b>
              </div>
            </div>

            <button className="btn form-submit" type="submit" disabled={busy || !materialId || !piecesValid}>
              Подобрать заготовку
            </button>
          </form>
        )}
        <Messages error={error || loadError} />
      </section>

      {suggestion && (
        <section className="card">
          <h2>2. Из чего резать</h2>
          {suggestion.candidates.length === 0 ? (
            <p className="muted">
              Нет заготовки, в которую помещаются все куски: нужно {mm(suggestion.required_mm)}
              {suggestion.longest_available_mm
                ? `, а самая длинная на складе — ${mm(suggestion.longest_available_mm)}. Уберите часть кусков и разрежьте их из другой заготовки.`
                : ', а этого материала на складе нет.'}
            </p>
          ) : (
            <>
              <p className="muted card-hint">
                Сверху самый экономный вариант: чем меньше остаток, тем выше. Можно выбрать другой.
              </p>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th></th>
                      <th>Заготовка</th>
                      <th className="num">Длина, мм</th>
                      <th>Место</th>
                      <th className="num">Остаток, мм</th>
                      <th>Что с остатком</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suggestion.candidates.map((c, index) => (
                      <tr
                        key={c.pick_id}
                        className={c.pick_id === chosenId ? 'selected' : ''}
                        onClick={() => setChosenId(c.pick_id)}
                      >
                        <td>
                          <input
                            type="radio"
                            name="source"
                            aria-label={`Резать из ${codeOf(c)}`}
                            checked={c.pick_id === chosenId}
                            onChange={() => setChosenId(c.pick_id)}
                          />
                        </td>
                        <td>
                          <span className="code">{codeOf(c)}</span>
                          {c.count > 1 && <span className="muted"> · таких же ещё {c.count - 1} шт.</span>}
                          {index === 0 && <span className="status status-in_stock best">лучший вариант</span>}
                        </td>
                        <td className="num">{c.item.length_mm.toLocaleString('ru-RU')}</td>
                        <td>{c.item.location?.name || '—'}</td>
                        <td className="num">{c.remainder_mm.toLocaleString('ru-RU')}</td>
                        <td className={c.remainder_fate === 'scrap' ? 'warn' : 'muted'}>
                          {REMAINDER_TEXT[c.remainder_fate]}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {chosen && (
                <div className="cut-summary" role="status">
                  <div>
                    Режем <b>{codeOf(chosen)}</b> ({mm(chosen.item.length_mm)}) на {pieces.length} шт.
                  </div>
                  {chosen.kerf_loss_mm > 0 && <div>Уйдёт в пропил: {mm(chosen.kerf_loss_mm)}</div>}
                  <div>
                    Остаток: <b>{mm(chosen.remainder_mm)}</b>{' '}
                    <span className="muted">— {REMAINDER_TEXT[chosen.remainder_fate]}</span>
                  </div>
                </div>
              )}

              <button className="btn form-submit" type="button" disabled={busy || !chosen} onClick={cut}>
                Разрезать{chosen ? ` ${codeOf(chosen)}` : ''}
              </button>
            </>
          )}
        </section>
      )}

      {result && (
        <section className="card">
          <h2>Готово: {result.source_item.code} разрезана</h2>
          <p className="muted card-hint">
            Напишите новые номера на кусках, которые остаются на складе.
            {result.kerf_loss_mm > 0 && ` Потери на рез: ${mm(result.kerf_loss_mm)}.`}
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Номер</th>
                  <th className="num">Длина, мм</th>
                  <th>Статус</th>
                  <th>Примечание</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((item) => (
                  <tr key={item.id}>
                    <td className="code">{item.code}</td>
                    <td className="num">{item.length_mm.toLocaleString('ru-RU')}</td>
                    <td><span className={`status status-${item.status}`}>{STATUS_LABELS[item.status]}</span></td>
                    <td className="muted">{item.note || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </Layout>
  );
};
