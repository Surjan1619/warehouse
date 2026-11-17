import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { useAction, useList, numberOrNull, textOrNull } from '../hooks';

const emptyReceive = { material_id: '', length_mm: '', count: '1', location_id: '', note: '' };

const materialTitle = (m) => [m.name, m.color, m.sku && `арт. ${m.sku}`].filter(Boolean).join(' · ');

// Приход заготовок: трубы и профили принимаются по материалу, каждая получает номер
export const ReceiveStockPage = () => {
  const [materials, , materialsError] = useList('/materials/');
  const [locations] = useList('/locations/');
  const [form, setForm] = useState(emptyReceive);
  const { error, busy, run } = useAction();
  // The last delivery, shown so the numbers can be written on the pieces
  const [received, setReceived] = useState(null);
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const receive = async (e) => {
    e.preventDefault();
    setReceived(null);
    const body = {
      material_id: Number(form.material_id),
      length_mm: Number(form.length_mm),
      count: Number(form.count),
      location_id: numberOrNull(form.location_id),
      note: textOrNull(form.note),
    };
    let created = [];
    const ok = await run(async () => {
      created = await api('/stock-items/', { method: 'POST', body });
    }, '');
    if (!ok) return;

    setReceived({ materialId: body.material_id, items: created });
    // Keep material and location: deliveries are entered in series
    setForm({ ...emptyReceive, material_id: form.material_id, location_id: form.location_id });
  };

  const codes = received?.items.map((item) => item.code) ?? [];

  return (
    <Layout title="Приход заготовок">
      <section className="card">
        {materials.length === 0 ? (
          <p className="muted">
            Сначала добавьте материал в <Link to="/catalog">справочниках</Link>: заготовки заводятся по материалу.
          </p>
        ) : (
          <>
            <p className="muted card-hint">
              Каждая заготовка получает свой номер. Напишите его на трубе — по нему она находится в системе.
            </p>
            <form className="form-row" onSubmit={receive}>
              <label className="wide">
                Материал
                <select value={form.material_id} onChange={set('material_id')} required>
                  <option value="">— выберите —</option>
                  {materials.map((m) => <option key={m.id} value={m.id}>{materialTitle(m)}</option>)}
                </select>
              </label>
              <label>
                Длина, мм
                <input type="number" value={form.length_mm} onChange={set('length_mm')} min={1} step={1} required />
              </label>
              <label>
                Количество, шт.
                <input type="number" value={form.count} onChange={set('count')} min={1} max={500} step={1} required />
              </label>
              <label>
                Место хранения
                <select value={form.location_id} onChange={set('location_id')}>
                  <option value="">— не указано —</option>
                  {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </label>
              <label className="wide">
                Примечание
                <input type="text" value={form.note} onChange={set('note')} maxLength={500} />
              </label>
              <button className="btn" type="submit" disabled={busy}>Принять на склад</button>
            </form>
          </>
        )}
        <Messages error={error || materialsError} />
      </section>

      {received && (
        <section className="card">
          <h2>Принято: {codes.length} шт.</h2>
          <p className="muted card-hint">Напишите номера на трубах.</p>
          <p className="codes">
            {codes.length > 1 ? `${codes[0]} … ${codes[codes.length - 1]}` : codes[0]}
          </p>
          <Link className="btn btn-ghost" to={`/stock?material=${received.materialId}`}>
            Посмотреть в остатках
          </Link>
        </section>
      )}
    </Layout>
  );
};
