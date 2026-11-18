import { Link } from 'react-router-dom';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { useAction, useList } from '../hooks';
import { amount, unitOf } from '../productOptions';

// Остатки штучных товаров. Приход и расход — в своих разделах.
export const ProductsPage = () => {
  const [products, reload, loadError] = useList('/products/');
  const { error, notice, busy, run } = useAction();

  const remove = async (product) => {
    if (!window.confirm(`Удалить товар «${product.name}»?`)) return;
    const ok = await run(
      () => api(`/products/${product.id}`, { method: 'DELETE' }),
      `Товар «${product.name}» удалён`,
      // 409: the product was restocked or issued, its history must stay
      'У товара есть история прихода и расхода, удалить его нельзя',
    );
    if (ok) await reload();
  };

  return (
    <Layout title="Остатки товаров">
      <section className="card">
        <p className="muted card-hint">
          Пополнить или завести товар — в разделе <Link to="/receive/products">«Приход»</Link>, выдать со склада — в
          разделе <Link to="/issue">«Расход»</Link>.
        </p>
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
                    <td className="num">{amount(p.quantity, unitOf(p))}</td>
                    <td className="actions">
                      <button className="btn btn-ghost" disabled={busy} onClick={() => remove(p)}>Удалить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Messages error={error || loadError} notice={notice} />
      </section>
    </Layout>
  );
};
