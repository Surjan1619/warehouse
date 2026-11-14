import { Link, useNavigate } from 'react-router-dom';
import { getUser, clearSession, isAdmin } from '../api';
import { ROLE_LABELS } from '../labels';

// Общая рамка страниц: шапка с именем пользователя и выходом
export const Layout = ({ title, children }) => {
  const navigate = useNavigate();
  const user = getUser();

  const logout = () => {
    clearSession();
    navigate('/login');
  };

  return (
    <div className="page">
      <header className="topbar">
        <Link to="/home" className="brand">WMS</Link>
        <nav>
          <Link to="/stock">Заготовки</Link>
          <Link to="/products">Товары</Link>
          <Link to="/catalog">Справочники</Link>
          {isAdmin(user) && <Link to="/admin">Пользователи</Link>}
        </nav>
        <div className="topbar-user">
          <span>
            {user?.username} <span className="badge">{ROLE_LABELS[user?.role] || user?.role}</span>
          </span>
          <button className="btn btn-ghost" onClick={logout}>Выход</button>
        </div>
      </header>
      <main className="content">
        <h1>{title}</h1>
        {children}
      </main>
    </div>
  );
};
