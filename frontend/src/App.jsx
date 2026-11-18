import { BrowserRouter as Router, Routes, Route, Navigate, Link, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import './App.css';
import { api, login, getToken, getUser, isAdmin } from './api';
import { Layout } from './components/Layout';
import { ROLE_LABELS } from './labels';
import { ProductsPage } from './pages/ProductsPage';
import { StockPage } from './pages/StockPage';
import { AssemblyPage } from './pages/AssemblyPage';
import { CutPage } from './pages/CutPage';
import { ClearDatabasePage } from './pages/ClearDatabasePage';
import { CatalogPage } from './pages/CatalogPage';
import { JournalPage } from './pages/JournalPage';
import { ReceiveStockPage } from './pages/ReceiveStockPage';
import { ReceiveProductsPage } from './pages/ReceiveProductsPage';
import { ImportDocumentPage } from './pages/ImportDocumentPage';
import { IssuePage } from './pages/IssuePage';
import { ProductTypesPage } from './pages/ProductTypesPage';
import { visibleSections } from './navigation';

// 1. Защита маршрутов: нужен вход, а для adminOnly — ещё и роль администратора.
// Это только удобство интерфейса: права проверяет сервер.
const ProtectedRoute = ({ children, adminOnly = false }) => {
  if (!getToken()) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin(getUser())) return <Navigate to="/home" replace />;
  return children;
};

// 2. Страница входа
const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  if (getToken()) return <Navigate to="/home" replace />;

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(username, password);
      navigate('/home');
    } catch (err) {
      setError(err.status === 400 ? 'Неверное имя или пароль' : err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-container">
      <form onSubmit={handleLogin} className="login-card">
        <h1>Вход</h1>
        <input
          type="text"
          placeholder="Имя"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Пароль"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? 'Вход…' : 'Войти'}</button>
        <p className="hint">Учётную запись создаёт администратор</p>
      </form>
    </div>
  );
};

// 3. Главная страница: все разделы с их страницами
const HomePage = () => {
  const user = getUser();
  return (
    <Layout title="Главная">
      {visibleSections(isAdmin(user)).map((section) => (
        <section key={section.key} className="home-section">
          <h2>
            {section.title} <span className="muted">· {section.hint}</span>
          </h2>
          <div className="tiles">
            {section.pages.map((page) => (
              <Link key={page.path} to={page.path} className="tile">
                <h3>{page.title}</h3>
                <p>{page.hint}</p>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </Layout>
  );
};

// 5. Панель администратора: пользователи
const emptyForm = { username: '', password: '', role: 'worker' };

const AdminPage = () => {
  const me = getUser();
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const loadUsers = async () => setUsers(await api('/users/'));

  useEffect(() => {
    api('/users/').then(setUsers).catch((err) => setError(err.message));
  }, []);

  const run = async (action, successText) => {
    setError('');
    setNotice('');
    setBusy(true);
    try {
      await action();
      setNotice(successText);
      await loadUsers();
      return true;
    } catch (err) {
      setError(err.status === 409 ? 'Пользователь с таким именем уже есть' : err.message);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const createUser = async (e) => {
    e.preventDefault();
    const ok = await run(
      () => api('/users/', { method: 'POST', body: form }),
      `Пользователь «${form.username}» создан`,
    );
    if (ok) setForm(emptyForm);
  };

  const setActive = (user, isActive) =>
    run(
      () => api(`/users/${user.id}`, { method: 'PATCH', body: { is_active: isActive } }),
      isActive ? `«${user.username}» снова может входить` : `«${user.username}» отключён`,
    );

  const resetPassword = (user) => {
    const password = window.prompt(`Новый пароль для «${user.username}» (не короче 6 символов)`);
    if (!password) return;
    run(
      () => api(`/users/${user.id}`, { method: 'PATCH', body: { password } }),
      `Пароль «${user.username}» изменён`,
    );
  };

  return (
    <Layout title="Пользователи">
      <section className="card">
        <h2>Новый пользователь</h2>
        <form className="form-row" onSubmit={createUser}>
          <label>
            Имя
            <input
              type="text"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              minLength={3}
              maxLength={50}
              autoComplete="off"
              required
            />
          </label>
          <label>
            Пароль
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              minLength={6}
              autoComplete="new-password"
              required
            />
          </label>
          <label>
            Роль
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="worker">{ROLE_LABELS.worker}</option>
              <option value="admin">{ROLE_LABELS.admin}</option>
            </select>
          </label>
          <button className="btn" type="submit" disabled={busy}>Создать</button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
        {notice && <p className="notice" role="status">{notice}</p>}
      </section>

      <section className="card">
        <h2>Все пользователи</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Имя</th>
                <th>Роль</th>
                <th>Состояние</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className={u.is_active ? '' : 'inactive'}>
                  <td>{u.username}{u.id === me?.id && <span className="muted"> (вы)</span>}</td>
                  <td>{ROLE_LABELS[u.role] || u.role}</td>
                  <td>{u.is_active ? 'Активен' : 'Отключён'}</td>
                  <td className="actions">
                    <button className="btn btn-ghost" disabled={busy} onClick={() => resetPassword(u)}>
                      Сменить пароль
                    </button>
                    {u.id !== me?.id && (
                      <button className="btn btn-ghost" disabled={busy} onClick={() => setActive(u, !u.is_active)}>
                        {u.is_active ? 'Отключить' : 'Включить'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </Layout>
  );
};

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/home" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
        <Route path="/stock" element={<ProtectedRoute><StockPage /></ProtectedRoute>} />
        <Route path="/assembly" element={<ProtectedRoute><AssemblyPage /></ProtectedRoute>} />
        <Route path="/cut" element={<ProtectedRoute><CutPage /></ProtectedRoute>} />
        <Route path="/products" element={<ProtectedRoute><ProductsPage /></ProtectedRoute>} />
        <Route path="/catalog" element={<ProtectedRoute><CatalogPage /></ProtectedRoute>} />
        <Route path="/receive" element={<ProtectedRoute><ReceiveStockPage /></ProtectedRoute>} />
        <Route path="/receive/products" element={<ProtectedRoute><ReceiveProductsPage /></ProtectedRoute>} />
        <Route path="/receive/document" element={<ProtectedRoute><ImportDocumentPage /></ProtectedRoute>} />
        <Route path="/issue" element={<ProtectedRoute><IssuePage /></ProtectedRoute>} />
        <Route path="/admin/types" element={<ProtectedRoute adminOnly><ProductTypesPage /></ProtectedRoute>} />
        <Route path="/journal" element={<ProtectedRoute adminOnly><JournalPage /></ProtectedRoute>} />
        <Route path="/admin/clear" element={<ProtectedRoute adminOnly><ClearDatabasePage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute adminOnly><AdminPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
