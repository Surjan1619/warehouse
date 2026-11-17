import { useState } from 'react';
import { api } from '../api';
import { Layout } from '../components/Layout';
import { Messages } from '../components/Messages';
import { useAction, useList } from '../hooks';

// Типы штучных товаров. Создаёт и удаляет только администратор: сервер
// отвечает работнику 403, а страница открыта только в разделе администрирования.
export const ProductTypesPage = () => {
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
    <Layout title="Типы товаров">
      <section className="card">
        <p className="muted card-hint">
          Группы штучных товаров: моторы, пульты, крепёж. Работники выбирают тип при добавлении товара, но создавать
          и удалять типы может только администратор.
        </p>
        <form className="form-row" onSubmit={create}>
          <label className="wide">
            Название
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
          </label>
          <button className="btn" type="submit" disabled={busy}>Добавить</button>
        </form>
        <Messages
          error={
            error === 'Cannot delete type: in use or not found'
              ? 'Тип используется товарами, удалить нельзя'
              : error || loadError
          }
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
    </Layout>
  );
};
