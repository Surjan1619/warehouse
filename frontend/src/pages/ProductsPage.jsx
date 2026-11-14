import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { useAction, useList, numberOrNull, textOrNull } from '../hooks';

const emptyProduct = {
  name: '',
  quantity: '1',
  product_type_id: '',
  location_id: '',
  length: '',
  width: '',
  thickness: '',
  weight: '',
  shape: '',
};

// Штучные товары: учёт по количеству
export const ProductsPage = () => {
  const [products, reload, loadError] = useList('/products/');
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
      product_type_id: numberOrNull(form.product_type_id),
      location_id: numberOrNull(form.location_id),
      length: numberOrNull(form.length),
      width: numberOrNull(form.width),
      thickness: numberOrNull(form.thickness),
      weight: numberOrNull(form.weight),
      shape: textOrNull(form.shape),
    };
    const ok = await run(
      () => api('/products/', { method: 'POST', body }),
      `Товар «${body.name}» добавлен`,
    );
    if (ok) {
      // Keep type and location: goods are usually added in series
      setForm({ ...emptyProduct, product_type_id: form.product_type_id, location_id: form.location_id });
      await reload();
    }
  };

  const remove = async (product) => {
    if (!window.confirm(`Удалить товар «${product.name}»?`)) return;
    const ok = await run(
      () => api(`/products/${product.id}`, { method: 'DELETE' }),
      `Товар «${product.name}» удалён`,
    );
    if (ok) await reload();
  };

  return (
    <Layout title="Товары">
      <section className="card">
        <h2>Новый товар</h2>
        <p className="muted card-hint">
          Штучные товары: моторы, пульты, крепёж. Трубы и профили добавляются на странице{' '}
          <Link to="/stock">«Заготовки»</Link>.
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
        <Messages error={error || loadError} notice={notice} />
        {(types.length === 0 || locations.length === 0) && (
          <p className="muted card-hint">
            Типы и места хранения создаются в <Link to="/catalog">справочниках</Link>.
          </p>
        )}
      </section>

      <section className="card">
        <h2>На складе</h2>
        {products.length === 0 ? (
          <p className="muted">Товаров пока нет</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Название</th>
                  <th>Тип</th>
                  <th>Место</th>
                  <th className="num">Количество</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}</td>
                    <td>{p.product_type?.name || '—'}</td>
                    <td>{p.location?.name || '—'}</td>
                    <td className="num">{p.quantity ?? 0}</td>
                    <td className="actions">
                      <button className="btn btn-ghost" disabled={busy} onClick={() => remove(p)}>Удалить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </Layout>
  );
};
