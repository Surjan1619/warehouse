import { useState } from 'react';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { useAction, useList, numberOrNull, textOrNull } from '../hooks';

// --- Материалы: то, что режется (профили, направляющие, валы) ---
const emptyMaterial = { name: '', kind: '', sku: '', color: '', kerf_mm: '3', min_usable_length_mm: '300' };

const MaterialsCard = () => {
  const [materials, reload, loadError] = useList('/materials/');
  const [form, setForm] = useState(emptyMaterial);
  const { error, notice, busy, run } = useAction();
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const create = async (e) => {
    e.preventDefault();
    const body = {
      name: form.name.trim(),
      kind: textOrNull(form.kind),
      sku: textOrNull(form.sku),
      color: textOrNull(form.color),
      kerf_mm: Number(form.kerf_mm),
      min_usable_length_mm: Number(form.min_usable_length_mm),
    };
    const ok = await run(
      () => api('/materials/', { method: 'POST', body }),
      `Материал «${body.name}» добавлен`,
      'Материал с таким артикулом уже есть',
    );
    if (ok) {
      setForm(emptyMaterial);
      await reload();
    }
  };

  const remove = async (material) => {
    if (!window.confirm(`Удалить материал «${material.name}»?`)) return;
    const ok = await run(
      () => api(`/materials/${material.id}`, { method: 'DELETE' }),
      `Материал «${material.name}» удалён`,
    );
    if (ok) await reload();
  };

  return (
    <section className="card">
      <h2>Материалы</h2>
      <p className="muted card-hint">То, что режется: профили, направляющие, валы. Заготовки добавляются по материалу.</p>
      <form className="form-row" onSubmit={create}>
        <label className="wide">
          Название
          <input type="text" value={form.name} onChange={set('name')} maxLength={100} required />
        </label>
        <label>
          Вид
          <input type="text" value={form.kind} onChange={set('kind')} maxLength={50} placeholder="профиль" />
        </label>
        <label>
          Артикул
          <input type="text" value={form.sku} onChange={set('sku')} maxLength={50} />
        </label>
        <label>
          Цвет
          <input type="text" value={form.color} onChange={set('color')} maxLength={50} />
        </label>
        <label>
          Ширина реза, мм
          <input type="number" value={form.kerf_mm} onChange={set('kerf_mm')} min={0} max={100} required />
        </label>
        <label>
          Мин. остаток, мм
          <input
            type="number"
            value={form.min_usable_length_mm}
            onChange={set('min_usable_length_mm')}
            min={0}
            required
          />
        </label>
        <button className="btn" type="submit" disabled={busy}>Добавить</button>
      </form>
      <Messages error={error || loadError} notice={notice} />

      {materials.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Вид</th>
                <th>Артикул</th>
                <th>Цвет</th>
                <th className="num">Рез, мм</th>
                <th className="num">Мин. остаток, мм</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {materials.map((m) => (
                <tr key={m.id}>
                  <td>{m.name}</td>
                  <td>{m.kind || '—'}</td>
                  <td>{m.sku || '—'}</td>
                  <td>{m.color || '—'}</td>
                  <td className="num">{m.kerf_mm}</td>
                  <td className="num">{m.min_usable_length_mm}</td>
                  <td className="actions">
                    <button className="btn btn-ghost" disabled={busy} onClick={() => remove(m)}>Удалить</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

// --- Типы штучных товаров ---
const ProductTypesCard = () => {
  const [types, reload, loadError] = useList('/products/types');
  const [name, setName] = useState('');
  const { error, notice, busy, run } = useAction();

  const create = async (e) => {
    e.preventDefault();
    const ok = await run(
      () => api('/products/types', { method: 'POST', body: { name: name.trim() } }),
      `Тип «${name.trim()}» добавлен`,
    );
    if (ok) {
      setName('');
      await reload();
    }
  };

  const remove = async (type) => {
    if (!window.confirm(`Удалить тип «${type.name}»?`)) return;
    const ok = await run(
      () => api(`/products/types/${type.id}`, { method: 'DELETE' }),
      `Тип «${type.name}» удалён`,
    );
    if (ok) await reload();
  };

  return (
    <section className="card">
      <h2>Типы товаров</h2>
      <p className="muted card-hint">Группы штучных товаров: моторы, пульты, крепёж.</p>
      <form className="form-row" onSubmit={create}>
        <label className="wide">
          Название
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
        </label>
        <button className="btn" type="submit" disabled={busy}>Добавить</button>
      </form>
      <Messages
        error={error === 'Cannot delete type: in use or not found' ? 'Тип используется товарами, удалить нельзя' : error || loadError}
        notice={notice}
      />

      {types.length > 0 && (
        <ul className="chips">
          {types.map((t) => (
            <li key={t.id}>
              {t.name}
              <button className="chip-remove" title="Удалить" disabled={busy} onClick={() => remove(t)}>×</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

// --- Места хранения ---
const LocationsCard = () => {
  const [locations, reload, loadError] = useList('/locations/');
  const [form, setForm] = useState({ name: '', capacity: '' });
  const { error, notice, busy, run } = useAction();

  const create = async (e) => {
    e.preventDefault();
    const body = { name: form.name.trim(), capacity: numberOrNull(form.capacity) };
    const ok = await run(
      () => api('/locations/', { method: 'POST', body }),
      `Место «${body.name}» добавлено`,
      'Место с таким названием уже есть',
    );
    if (ok) {
      setForm({ name: '', capacity: '' });
      await reload();
    }
  };

  return (
    <section className="card">
      <h2>Места хранения</h2>
      <p className="muted card-hint">Стеллажи, ячейки, зоны склада.</p>
      <form className="form-row" onSubmit={create}>
        <label className="wide">
          Название
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            maxLength={50}
            placeholder="Стеллаж A-1"
            required
          />
        </label>
        <label>
          Вместимость
          <input
            type="number"
            value={form.capacity}
            onChange={(e) => setForm({ ...form, capacity: e.target.value })}
            min={0}
          />
        </label>
        <button className="btn" type="submit" disabled={busy}>Добавить</button>
      </form>
      <Messages error={error || loadError} notice={notice} />

      {locations.length > 0 && (
        <ul className="chips">
          {locations.map((l) => (
            <li key={l.id}>
              {l.name}
              {l.capacity != null && <span className="muted"> · {l.capacity}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

export const CatalogPage = () => (
  <Layout title="Справочники">
    <MaterialsCard />
    <ProductTypesCard />
    <LocationsCard />
  </Layout>
);
