import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { useAction, useList } from '../hooks';
import { groupByType, productLabel } from '../productOptions';

// Расход штучных товаров: моторы, пульты, крепёж уходят со склада
export const IssuePage = () => {
  const [products, reload, loadError] = useList('/products/');
  const [productId, setProductId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const { error, busy, run } = useAction();
  // Shown after an issue with the quantity the server reports
  const [done, setDone] = useState('');

  const chosen = products.find((p) => p.id === Number(productId));
  const available = chosen?.quantity ?? 0;
  // Nothing to issue: hide such goods from the list, they only get in the way
  const inStock = products.filter((p) => (p.quantity ?? 0) > 0);

  const issue = async (e) => {
    e.preventDefault();
    setDone('');
    const name = chosen?.name;
    let updated = null;
    const ok = await run(async () => {
      updated = await api(`/products/${productId}/issue`, { method: 'POST', body: { quantity: Number(quantity) } });
    }, '');
    if (!ok) return;
    setQuantity('1');
    if (updated.quantity === 0) setProductId('');
    setDone(`Выдано: «${name}» × ${quantity}. Осталось ${updated.quantity} шт.`);
    await reload();
  };

  return (
    <Layout title="Расход товаров">
      <section className="card">
        <p className="muted card-hint">
          Выдача штучных товаров со склада: моторы, пульты, крепёж. Трубы и профили расходуются через{' '}
          <Link to="/cut">«Резку»</Link>.
        </p>
        {inStock.length === 0 ? (
          <p className="muted">На складе нет штучных товаров.</p>
        ) : (
          <form className="form-row" onSubmit={issue}>
            <label className="wide">
              Товар
              <select value={productId} onChange={(e) => setProductId(e.target.value)} required>
                <option value="">— выберите —</option>
                {groupByType(inStock).map((group) => (
                  <optgroup key={group.title} label={group.title}>
                    {group.items.map((p) => <option key={p.id} value={p.id}>{productLabel(p)}</option>)}
                  </optgroup>
                ))}
              </select>
            </label>
            <label>
              Сколько выдать, шт.
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                min={1}
                max={chosen ? available : undefined}
                step={1}
                required
              />
            </label>
            <button className="btn" type="submit" disabled={busy}>Выдать со склада</button>
          </form>
        )}
        <Messages
          error={error.startsWith('Not enough in stock') ? 'На складе меньше, чем нужно выдать' : error || loadError}
          notice={done}
        />
      </section>
    </Layout>
  );
};
