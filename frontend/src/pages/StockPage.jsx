import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { STATUS_LABELS } from '../labels';
import { useAction, useList, numberOrNull, textOrNull } from '../hooks';

const emptyReceive = { material_id: '', length_mm: '', count: '1', location_id: '', note: '' };

const materialTitle = (m) => [m.name, m.color, m.sku && `арт. ${m.sku}`].filter(Boolean).join(' · ');

// Заготовки: каждая труба или профиль — отдельная запись со своей длиной
export const StockPage = () => {
  const [status, setStatus] = useState('in_stock');
  const [items, reload, loadError] = useList(`/stock-items/${status ? `?status=${status}` : ''}`);
  const [materials] = useList('/materials/');
  const [locations] = useList('/locations/');
  const [form, setForm] = useState(emptyReceive);
  const { error, busy, run } = useAction();
  // Shown after a successful receipt so the numbers can be written on the pieces
  const [received, setReceived] = useState('');
  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const receive = async (e) => {
    e.preventDefault();
    setReceived('');
    const body = {
      material_id: Number(form.material_id),
      length_mm: Number(form.length_mm),
      count: Number(form.count),
      location_id: numberOrNull(form.location_id),
      note: textOrNull(form.note),
    };
    let created = [];
    const ok = await run(
      async () => {
        created = await api('/stock-items/', { method: 'POST', body });
      },
      '',
    );
    if (!ok) return;

    const codes = created.map((item) => item.code);
    const range = codes.length > 1 ? `${codes[0]} … ${codes[codes.length - 1]}` : codes[0];
    setReceived(`Добавлено заготовок: ${codes.length}. Номера: ${range}`);
    // Keep material and location: deliveries are entered in series
    setForm({ ...emptyReceive, material_id: form.material_id, location_id: form.location_id });
    await reload();
  };

  const totalLength = items.reduce((sum, item) => sum + item.length_mm, 0);

  return (
    <Layout title="Заготовки">
      <section className="card">
        <h2>Приход</h2>
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
        <Messages error={error || loadError} notice={received} />
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Заготовки</h2>
          <label className="inline-filter">
            Статус
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Все</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
        </div>

        {items.length === 0 ? (
          <p className="muted">Заготовок с таким статусом нет</p>
        ) : (
          <>
            <p className="muted card-hint">
              Всего: {items.length} шт., {(totalLength / 1000).toLocaleString('ru-RU')} м
            </p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Номер</th>
                    <th>Материал</th>
                    <th className="num">Длина, мм</th>
                    <th>Статус</th>
                    <th>Место</th>
                    <th>Заказ</th>
                    <th>Примечание</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="code">{item.code}</td>
                      <td>{materialTitle(item.material)}</td>
                      <td className="num">{item.length_mm.toLocaleString('ru-RU')}</td>
                      <td><span className={`status status-${item.status}`}>{STATUS_LABELS[item.status]}</span></td>
                      <td>{item.location?.name || '—'}</td>
                      <td>{item.order?.number || '—'}</td>
                      <td className="muted">{item.note || ''}</td>
                      <td className="actions">
                        {item.status === 'in_stock' && (
                          <Link className="btn btn-ghost" to={`/cut?item=${item.id}&material=${item.material.id}`}>Резать</Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </Layout>
  );
};
