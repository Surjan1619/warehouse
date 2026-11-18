import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { useAction, useList, numberOrNull, textOrNull } from '../hooks';
import { UNITS, UNIT_NAMES, amount, groupByType, productLabel, unitOf } from '../productOptions';

const emptyProduct = {
  name: '',
  quantity: '1',
  unit: 'шт',
  product_type_id: '',
  location_id: '',
  length: '',
  width: '',
  thickness: '',
  weight: '',
  shape: '',
};

// Пополнить товар, который уже есть в списке
const RestockCard = ({ products, reload }) => {
  const [productId, setProductId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const { error, busy, run } = useAction();
  // Shown after a restock with the quantity the server reports
  const [done, setDone] = useState('');
  const chosen = products.find((p) => p.id === Number(productId));

  const restock = async (e) => {
    e.preventDefault();
    setDone('');
    let updated = null;
    const ok = await run(async () => {
      updated = await api(`/products/${productId}/receive`, { method: 'POST', body: { quantity: Number(quantity) } });
    }, '');
    if (!ok) return;
    setQuantity('1');
    setDone(`«${updated.name}»: теперь ${amount(updated.quantity, unitOf(updated))}`);
    await reload();
  };

  return (
    <section className="card">
      <h2>Пополнить товар</h2>
      {products.length === 0 ? (
        <p className="muted">Товаров пока нет — заведите первый ниже.</p>
      ) : (
        <form className="form-row" onSubmit={restock}>
          <label className="wide">
            Товар
            <select value={productId} onChange={(e) => setProductId(e.target.value)} required>
              <option value="">— выберите —</option>
              {groupByType(products).map((group) => (
                <optgroup key={group.title} label={group.title}>
                  {group.items.map((p) => <option key={p.id} value={p.id}>{productLabel(p)}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <label>
            Пришло, {unitOf(chosen)}
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              min={1}
              max={100000}
              step={1}
              required
            />
          </label>
          <button className="btn" type="submit" disabled={busy}>Добавить на склад</button>
        </form>
      )}
      <Messages error={error} notice={done} />
    </section>
  );
};

// Завести товар, которого ещё нет в списке
const NewProductCard = ({ reload }) => {
  const [types] = useList('/products/types');
  const [locations] = useList('/locations/');
  const [form, setForm] = useState(emptyProduct);
  const { error, notice, busy, run } = useAction();
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const create = async (e) => {
    e.preventDefault();
    const body = {
      name: form.name.trim(),
      quantity: Number(form.quantity),
      unit: form.unit,
      product_type_id: numberOrNull(form.product_type_id),
      location_id: numberOrNull(form.location_id),
      length: numberOrNull(form.length),
      width: numberOrNull(form.width),
      thickness: numberOrNull(form.thickness),
      weight: numberOrNull(form.weight),
      shape: textOrNull(form.shape),
    };
    const ok = await run(() => api('/products/', { method: 'POST', body }), `Товар «${body.name}» добавлен`);
    if (ok) {
      // Keep unit, type and location: goods are usually added in series
      setForm({ ...emptyProduct, unit: form.unit, product_type_id: form.product_type_id, location_id: form.location_id });
      await reload();
    }
  };

  return (
    <section className="card">
      <h2>Новый товар</h2>
      <p className="muted card-hint">
        Если такой товар уже есть, пополните его выше, а не заводите второй раз.
      </p>
      <form onSubmit={create}>
        <div className="form-row">
          <label className="wide">
            Название
            <input type="text" value={form.name} onChange={set('name')} maxLength={100} required />
          </label>
          <label>
            Количество
            <input type="number" value={form.quantity} onChange={set('quantity')} min={0} required />
          </label>
          <label>
            Единица
            <select value={form.unit} onChange={set('unit')}>
              {UNITS.map((u) => <option key={u} value={u}>{u} — {UNIT_NAMES[u]}</option>)}
            </select>
          </label>
          <label>
            Тип
            <select value={form.product_type_id} onChange={set('product_type_id')}>
              <option value="">— без типа —</option>
              {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <label>
            Место хранения
            <select value={form.location_id} onChange={set('location_id')}>
              <option value="">— не указано —</option>
              {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </label>
        </div>

        <details className="more">
          <summary>Размеры и вес</summary>
          <div className="form-row">
            <label>
              Длина
              <input type="number" value={form.length} onChange={set('length')} min={0} step="any" />
            </label>
            <label>
              Ширина
              <input type="number" value={form.width} onChange={set('width')} min={0} step="any" />
            </label>
            <label>
              Толщина
              <input type="number" value={form.thickness} onChange={set('thickness')} min={0} step="any" />
            </label>
            <label>
              Вес
              <input type="number" value={form.weight} onChange={set('weight')} min={0} step="any" />
            </label>
            <label>
              Форма
              <input type="text" value={form.shape} onChange={set('shape')} maxLength={50} />
            </label>
          </div>
        </details>

        <button className="btn form-submit" type="submit" disabled={busy}>Добавить товар</button>
      </form>
      <Messages error={error} notice={notice} />
      <p className="muted card-hint">
        Типы товаров заводит администратор. Места хранения — в <Link to="/catalog">справочниках</Link>.
      </p>
    </section>
  );
};

// Приход штучных товаров: пополнение существующего или новый товар
export const ReceiveProductsPage = () => {
  const [products, reload, loadError] = useList('/products/');
  return (
    <Layout title="Приход товаров">
      <Messages error={loadError} />
      <RestockCard products={products} reload={reload} />
      <NewProductCard reload={reload} />
    </Layout>
  );
};
