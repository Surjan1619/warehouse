import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { STATUS_LABELS } from '../labels';
import { useList } from '../hooks';
import { amount, groupByType, productLabel, unitOf } from '../productOptions';
import {
  addCut,
  addGoods,
  allLinesValid,
  availableOf,
  commitRequest,
  isEmpty,
  loadDraft,
  newDraft,
  planRequest,
  planSignature,
  removeLine,
  saveDraft,
  totals,
  unplacedOf,
  updateLine,
} from '../assemblyDraft';

const n = (value) => value.toLocaleString('ru-RU');
const mm = (value) => `${n(value)} мм`;
const materialTitle = (m) => [m.name, m.color, m.sku && `арт. ${m.sku}`].filter(Boolean).join(' · ');

const REMAINDER_TEXT = {
  none: 'без остатка',
  stock: 'вернётся на склад',
  scrap: 'уйдёт в отходы',
};

// Server messages a worker may see here, in Russian
const translate = (message) => {
  if (!message) return '';
  if (message.startsWith('Not enough in stock')) return 'Товара на складе меньше, чем нужно. Проверьте количество.';
  if (message.includes('refresh the plan') || message.includes('cannot be cut'))
    return 'Пока вы собирали, одну из заготовок уже взяли. Раскрой пересчитан — проверьте его и завершите ещё раз.';
  if (message.startsWith('Pieces do not fit')) return 'Куски не помещаются в заготовку. Раскрой пересчитан — проверьте его.';
  if (message.startsWith('Too many pieces')) return 'Слишком много кусков одного материала: не больше 200.';
  return message;
};

const emptyCutForm = { material_id: '', length_mm: '', quantity: '1', used: 'used' };
const emptyGoodsForm = { product_id: '', quantity: '1' };

/** "3 000 + 1 500 × 2": equal lengths are collapsed. */
const describe = (pieces) => {
  const counts = new Map();
  for (const p of pieces) counts.set(p.length_mm, (counts.get(p.length_mm) || 0) + 1);
  return [...counts].map(([length, count]) => `${n(length)}${count > 1 ? ` × ${count}` : ''}`).join(' + ');
};

// Добавить отрезки: материал, длина, сколько штук, куда пойдут
const CutForm = ({ materials, onAdd }) => {
  const [form, setForm] = useState(emptyCutForm);
  const [error, setError] = useState('');
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });
  const lengthRef = useRef(null);

  const submit = (e) => {
    e.preventDefault();
    const length = Number(form.length_mm);
    const quantity = Number(form.quantity);
    if (!Number.isInteger(length) || length <= 0) return setError('Длина — целое число миллиметров больше нуля');
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 200) return setError('Количество — от 1 до 200');
    setError('');
    onAdd({ material_id: Number(form.material_id), length_mm: length, quantity, used: form.used === 'used' });
    // Keep the material and destination: several lengths of one material are typed in a row
    setForm({ ...form, length_mm: '', quantity: '1' });
    lengthRef.current?.focus();
  };

  return (
    <section className="card">
      <h2>Отрезки</h2>
      {materials.length === 0 ? (
        <p className="muted">
          Материалов нет. Добавьте их в <Link to="/catalog">справочниках</Link>.
        </p>
      ) : (
        <form onSubmit={submit} className="assembly-form">
          <label>
            Материал
            <select value={form.material_id} onChange={set('material_id')} required>
              <option value="">— выберите —</option>
              {materials.map((m) => <option key={m.id} value={m.id}>{materialTitle(m)}</option>)}
            </select>
          </label>
          <div className="assembly-form-row">
            <label>
              Длина, мм
              <input
                ref={lengthRef}
                type="number"
                value={form.length_mm}
                onChange={set('length_mm')}
                min={1}
                step={1}
                required
                aria-invalid={Boolean(error)}
              />
            </label>
            <label>
              Штук
              <input type="number" value={form.quantity} onChange={set('quantity')} min={1} max={200} step={1} required />
            </label>
          </div>
          <label>
            Куда пойдут
            <select value={form.used} onChange={set('used')}>
              <option value="used">В сборку</option>
              <option value="stock">Вернуть на склад</option>
            </select>
          </label>
          {error && <p className="field-error" role="alert">{error}</p>}
          <button className="btn" type="submit" disabled={!form.material_id}>Добавить отрезок</button>
        </form>
      )}
    </section>
  );
};

// Добавить штучный товар со склада
const GoodsForm = ({ products, draft, onAdd }) => {
  const [form, setForm] = useState(emptyGoodsForm);
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const product = products.find((p) => p.id === Number(form.product_id));
  const available = product?.quantity ?? 0;
  // What is already in the draft counts against the stock too
  const inDraft = draft.goods.find((l) => l.product_id === product?.id)?.quantity ?? 0;
  const quantity = Number(form.quantity);
  const tooMany = Boolean(product) && quantity + inDraft > available;
  const inStock = products.filter((p) => (p.quantity ?? 0) > 0);

  const submit = (e) => {
    e.preventDefault();
    if (tooMany || !Number.isInteger(quantity) || quantity < 1) return;
    onAdd({ product_id: product.id, quantity });
    setForm(emptyGoodsForm);
  };

  return (
    <section className="card">
      <h2>Товары со склада</h2>
      {inStock.length === 0 ? (
        <p className="muted">На складе нет штучных товаров.</p>
      ) : (
        <form onSubmit={submit} className="assembly-form">
          <label>
            Товар
            <select value={form.product_id} onChange={set('product_id')} required>
              <option value="">— выберите —</option>
              {groupByType(inStock).map((group) => (
                <optgroup key={group.title} label={group.title}>
                  {group.items.map((p) => <option key={p.id} value={p.id}>{productLabel(p)}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <label>
            Количество{product && `, ${unitOf(product)}`}
            <input
              type="number"
              value={form.quantity}
              onChange={set('quantity')}
              min={1}
              step={1}
              required
              aria-invalid={tooMany}
            />
          </label>
          {product && (
            <p className={tooMany ? 'field-error' : 'muted field-hint'} role={tooMany ? 'alert' : undefined}>
              На складе {amount(available, unitOf(product))}{inDraft > 0 && `, уже в сборке ${inDraft}`}
              {tooMany && ` — можно добавить не больше ${Math.max(available - inDraft, 0)}`}
            </p>
          )}
          <button className="btn" type="submit" disabled={!product || tooMany}>Добавить товар</button>
        </form>
      )}
    </section>
  );
};

/**
 * Сборка: всё, что берётся со склада для одного изделия (например, ворот), в одном окне.
 * Слева добавляются отрезки и товары, справа — общий список расхода с раскроем,
 * который считает сервер (POST /assemblies/plan). Пока сборка не завершена, склад
 * не меняется: черновик хранится в браузере. «Завершить сборку» выполняет все
 * резки и списания одной транзакцией (POST /assemblies).
 */
export const AssemblyPage = () => {
  const [materials, , materialsError] = useList('/materials/');
  const [products, reloadProducts, productsError] = useList('/products/');
  const [draft, setDraftState] = useState(loadDraft);
  const [plan, setPlan] = useState(null);
  // Signature of the draft the plan was made for; a plan for another draft is stale
  const [planFor, setPlanFor] = useState('');
  const [planError, setPlanError] = useState('');
  // Bumped to ask for a new layout of the same draft (after a failed finish)
  const [refresh, setRefresh] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // The assembly just finished, shown until a new one is started
  const [done, setDone] = useState(null);

  const setDraft = (next) => {
    setDraftState(next);
    saveDraft(next);
    setConfirming(false);
    setError('');
  };

  const signature = planSignature(draft);
  const request = planRequest(draft);
  const hasLines = request.materials.length > 0 || request.products.length > 0;

  // Ask the server for the layout whenever the question changes; a short pause
  // lets the worker finish typing a number first
  useEffect(() => {
    if (!hasLines) return undefined;
    let current = true;
    const timer = setTimeout(() => {
      api('/assemblies/plan', { method: 'POST', body: JSON.parse(signature) })
        .then((result) => {
          if (!current) return;
          setPlan(result);
          setPlanFor(signature);
          setPlanError('');
        })
        .catch((err) => current && setPlanError(translate(err.message)));
    }, 350);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [signature, hasLines, refresh]);

  const fresh = hasLines && plan !== null && planFor === signature;
  const ready = fresh && plan.ok && allLinesValid(draft);

  const materialOf = (id) => materials.find((m) => m.id === id);
  const productOf = (id) => products.find((p) => p.id === id);
  const sum = totals(draft);

  const resetPlan = () => {
    setPlan(null);
    setPlanFor('');
  };

  const startNew = () => {
    if (!isEmpty(draft) && !window.confirm('Начать новую сборку? Текущий список будет очищен.')) return;
    setDraft(newDraft());
    resetPlan();
    setDone(null);
  };

  const finish = async () => {
    if (busy || !ready) return;
    setBusy(true);
    setError('');
    try {
      const assembly = await api('/assemblies/', { method: 'POST', body: commitRequest(draft, plan) });
      setDone(assembly);
      // A new key: the next assembly must not be mistaken for a repeat of this one
      setDraft(newDraft());
      resetPlan();
      await reloadProducts();
    } catch (err) {
      setError(translate(err.message));
      setConfirming(false);
      // Stock may have changed meanwhile: ask for a new layout
      resetPlan();
      setRefresh((r) => r + 1);
      await reloadProducts().catch(() => {});
    } finally {
      setBusy(false);
    }
  };

  const plannedCuts = fresh ? plan.materials.flatMap((m) => m.cuts.map((c) => ({ ...c, material: m.material }))) : [];

  return (
    <Layout title="Сборка">
      <Messages error={materialsError || productsError} />

      {done && <DoneCard assembly={done} onClose={() => setDone(null)} />}

      <section className="card assembly-head">
        <div className="assembly-head-fields">
          <label>
            Что собираем
            <input
              type="text"
              value={draft.name}
              placeholder="Например: ворота для Иванова"
              maxLength={150}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </label>
          <label className="wide">
            Примечание
            <input
              type="text"
              value={draft.note}
              maxLength={500}
              onChange={(e) => setDraft({ ...draft, note: e.target.value })}
            />
          </label>
        </div>
        <button type="button" className="btn btn-ghost" onClick={startNew} disabled={busy}>
          Новая сборка
        </button>
      </section>

      <div className="assembly-grid">
        <div className="assembly-side">
          <CutForm materials={materials} onAdd={(line) => setDraft(addCut(draft, line))} />
          <GoodsForm products={products} draft={draft} onAdd={(line) => setDraft(addGoods(draft, line))} />
        </div>

        <section className="card assembly-list">
          <h2>Список расхода</h2>
          {isEmpty(draft) ? (
            <p className="muted">
              Добавьте слева отрезки и товары. Пока сборка не завершена, со склада ничего не списывается.
            </p>
          ) : (
            <>
              {draft.cuts.length > 0 && (
                <>
                  <h3 className="section-title">Отрезки</h3>
                  <div className="table-wrap">
                    <table className="table assembly-lines">
                      <thead>
                        <tr>
                          <th>Материал</th>
                          <th className="num">Длина, мм</th>
                          <th className="num">Штук</th>
                          <th>Куда</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {draft.cuts.map((line) => {
                          const missing = fresh ? unplacedOf(plan, line) : 0;
                          const material = materialOf(line.material_id);
                          return (
                            <tr key={line.id} className={missing ? 'has-error' : ''}>
                              <td>
                                {material ? material.name : `Материал №${line.material_id}`}
                                {missing > 0 && (
                                  <div className="field-error" role="alert">
                                    {missing === line.quantity ? 'Не хватает' : `Не хватает ${missing} из ${line.quantity}`}
                                    : нет свободной заготовки такой длины
                                  </div>
                                )}
                              </td>
                              <td className="num">
                                <input
                                  type="number"
                                  aria-label="Длина, мм"
                                  value={line.length_mm || ''}
                                  min={1}
                                  step={1}
                                  aria-invalid={!(line.length_mm > 0)}
                                  onChange={(e) =>
                                    setDraft(updateLine(draft, 'cuts', line.id, { length_mm: Number(e.target.value) }))
                                  }
                                />
                              </td>
                              <td className="num">
                                <input
                                  type="number"
                                  aria-label="Штук"
                                  className="narrow"
                                  value={line.quantity || ''}
                                  min={1}
                                  max={200}
                                  step={1}
                                  aria-invalid={!(line.quantity > 0)}
                                  onChange={(e) =>
                                    setDraft(updateLine(draft, 'cuts', line.id, { quantity: Number(e.target.value) }))
                                  }
                                />
                              </td>
                              <td>
                                <select
                                  aria-label="Куда"
                                  value={line.used ? 'used' : 'stock'}
                                  onChange={(e) =>
                                    setDraft(updateLine(draft, 'cuts', line.id, { used: e.target.value === 'used' }))
                                  }
                                >
                                  <option value="used">В сборку</option>
                                  <option value="stock">На склад</option>
                                </select>
                              </td>
                              <td className="actions">
                                <button
                                  type="button"
                                  className="chip-remove"
                                  title="Убрать"
                                  aria-label="Убрать"
                                  onClick={() => setDraft(removeLine(draft, 'cuts', line.id))}
                                >
                                  ×
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  <h3 className="section-title">Раскрой</h3>
                  {!fresh ? (
                    <p className={planError ? 'field-error' : 'muted'}>{planError || 'Считаем раскрой…'}</p>
                  ) : plannedCuts.length === 0 ? (
                    <p className="muted">Ни один отрезок не помещается в заготовки на складе.</p>
                  ) : (
                    <div className="table-wrap">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Заготовка</th>
                            <th className="num">Длина, мм</th>
                            <th>Место</th>
                            <th>Куски, мм</th>
                            <th className="num">Остаток, мм</th>
                            <th>Что с остатком</th>
                          </tr>
                        </thead>
                        <tbody>
                          {plannedCuts.map((c) => (
                            <tr key={c.item.id}>
                              <td>
                                <span className="code">{c.item.code}</span>
                                <div className="muted small">{c.material.name}</div>
                              </td>
                              <td className="num">{n(c.item.length_mm)}</td>
                              <td>{c.item.location?.name || '—'}</td>
                              <td className="wrap">{describe(c.pieces)}</td>
                              <td className="num">{n(c.remainder_mm)}</td>
                              <td className={c.remainder_fate === 'scrap' ? 'warn' : 'muted'}>
                                {REMAINDER_TEXT[c.remainder_fate]}
                                {c.kerf_loss_mm > 0 && <div className="small">пропил {mm(c.kerf_loss_mm)}</div>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}

              {draft.goods.length > 0 && (
                <>
                  <h3 className="section-title">Товары</h3>
                  <div className="table-wrap">
                    <table className="table assembly-lines">
                      <thead>
                        <tr>
                          <th>Товар</th>
                          <th className="num">Кол-во</th>
                          <th className="num">На складе</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {draft.goods.map((line) => {
                          const product = productOf(line.product_id);
                          const known = fresh ? availableOf(plan, line.product_id) : null;
                          const available = known ?? product?.quantity ?? 0;
                          const short = line.quantity > available;
                          return (
                            <tr key={line.id} className={short ? 'has-error' : ''}>
                              <td>
                                {product ? product.name : `Товар №${line.product_id}`}
                                {short && (
                                  <div className="field-error" role="alert">
                                    На складе только {amount(available, unitOf(product))}
                                  </div>
                                )}
                              </td>
                              <td className="num">
                                <input
                                  type="number"
                                  aria-label="Количество"
                                  className="narrow"
                                  value={line.quantity || ''}
                                  min={1}
                                  step={1}
                                  aria-invalid={short || !(line.quantity > 0)}
                                  onChange={(e) =>
                                    setDraft(updateLine(draft, 'goods', line.id, { quantity: Number(e.target.value) }))
                                  }
                                />
                              </td>
                              <td className="num">{amount(available, unitOf(product))}</td>
                              <td className="actions">
                                <button
                                  type="button"
                                  className="chip-remove"
                                  title="Убрать"
                                  aria-label="Убрать"
                                  onClick={() => setDraft(removeLine(draft, 'goods', line.id))}
                                >
                                  ×
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              <div className="cut-summary">
                {[...sum.materials].map(([id, t]) => (
                  <div key={id}>
                    {materialOf(id)?.name ?? `Материал №${id}`}: <b>{t.pieces} шт.</b>, {mm(t.length_mm)}
                    {t.used_mm !== t.length_mm && <span className="muted"> (в сборку {mm(t.used_mm)})</span>}
                  </div>
                ))}
                {sum.goods > 0 && (
                  <div>
                    Товаров: <b>{draft.goods.length} наим.</b>
                  </div>
                )}
              </div>

              {!allLinesValid(draft) && <p className="field-error">Заполните длину и количество во всех строках.</p>}
              {fresh && !plan.ok && (
                <p className="field-error">Материала или товара не хватает — исправьте строки, отмеченные красным.</p>
              )}
              {error && <p className="error" role="alert">{error}</p>}

              {confirming && ready ? (
                <Summary plan={plan} draft={draft} busy={busy} onConfirm={finish} onBack={() => setConfirming(false)} />
              ) : (
                <button
                  type="button"
                  className="btn form-submit"
                  disabled={!ready || busy}
                  onClick={() => setConfirming(true)}
                >
                  Завершить сборку
                </button>
              )}
            </>
          )}
        </section>
      </div>
    </Layout>
  );
};

// Итог перед подтверждением: что будет разрезано, получено, возвращено и списано
const Summary = ({ plan, draft, busy, onConfirm, onBack }) => {
  const cuts = plan.materials.flatMap((m) => m.cuts.map((c) => ({ ...c, material: m.material })));
  const pieces = cuts.flatMap((c) => c.pieces);
  const usedPieces = pieces.filter((p) => p.used);
  const keptPieces = pieces.filter((p) => !p.used);
  const kept = cuts.filter((c) => c.remainder_fate === 'stock');
  const scrap = cuts.filter((c) => c.remainder_fate === 'scrap');
  const usedLength = usedPieces.reduce((s, p) => s + p.length_mm, 0);
  const name = draft.name.trim();

  return (
    <div className="assembly-summary" role="region" aria-label="Итог сборки">
      <h3>Проверьте перед завершением{name && `: ${name}`}</h3>
      <ul>
        {cuts.length > 0 && (
          <li>
            <b>Разрезать заготовки ({cuts.length}):</b>{' '}
            {cuts.map((c) => `${c.item.code} (${c.material.name}, ${mm(c.item.length_mm)})`).join(', ')}
          </li>
        )}
        {usedPieces.length > 0 && (
          <li>
            <b>В сборку кусков: {usedPieces.length}</b> — {describe(usedPieces)} мм, всего {mm(usedLength)}
          </li>
        )}
        {keptPieces.length > 0 && (
          <li>
            <b>На склад кусков: {keptPieces.length}</b> — {describe(keptPieces)} мм
          </li>
        )}
        {kept.length > 0 && (
          <li>
            <b>Остатки вернутся на склад:</b> {kept.map((c) => mm(c.remainder_mm)).join(', ')}
          </li>
        )}
        {scrap.length > 0 && (
          <li className="warn">
            <b>В отходы:</b> {scrap.map((c) => mm(c.remainder_mm)).join(', ')}
          </li>
        )}
        {plan.products.length > 0 && (
          <li>
            <b>Списать товары:</b> {plan.products.map((p) => `${p.product.name} — ${amount(p.quantity, unitOf(p.product))}`).join(', ')}
          </li>
        )}
      </ul>
      <div className="result-actions">
        <button type="button" className="btn" disabled={busy} onClick={onConfirm}>
          {busy ? 'Сохраняем…' : 'Подтвердить и завершить'}
        </button>
        <button type="button" className="btn btn-ghost" disabled={busy} onClick={onBack}>
          Назад к списку
        </button>
      </div>
    </div>
  );
};

// Что получилось: номера кусков, чтобы подписать их, и списанные товары
const DoneCard = ({ assembly, onClose }) => (
  <section className="card assembly-done" role="status">
    <div className="card-head">
      <h2>
        Сборка №{assembly.id} завершена{assembly.name && `: ${assembly.name}`}
      </h2>
      <button type="button" className="btn btn-ghost" onClick={onClose}>
        Скрыть
      </button>
    </div>
    {assembly.cuts.map((cut) => (
      <div key={cut.id} className="assembly-done-cut">
        <span className="code">{cut.source_item.code}</span> разрезана на:{' '}
        {cut.results.map((r) => (
          <span key={r.id} className="assembly-piece">
            <span className="code">{r.code}</span> {mm(r.length_mm)}{' '}
            <span className={`status status-${r.status}`}>{STATUS_LABELS[r.status] || r.status}</span>
          </span>
        ))}
      </div>
    ))}
    {assembly.goods.length > 0 && (
      <p>Списано: {assembly.goods.map((g) => `${g.product.name} — ${amount(g.quantity, unitOf(g.product))}`).join(', ')}</p>
    )}
  </section>
);
