import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { getUser, clearSession, isAdmin } from '../api';
import { ROLE_LABELS } from '../labels';
import { sectionHome, sectionOf, visibleSections } from '../navigation';

// Общая рамка страниц: разделы в шапке, вкладки текущего раздела под ней,
// имя пользователя и выход
export const Layout = ({ title, children }) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const user = getUser();
  const current = sectionOf(pathname);

  const logout = () => {
    clearSession();
    navigate('/login');
  };

  return (
    <div className="page">
      <header className="topbar">
        <Link to="/home" className="brand">WMS</Link>
        <nav aria-label="Разделы">
          {visibleSections(isAdmin(user)).map((section) => (
            <Link
              key={section.key}
              to={sectionHome(section)}
              className={section.key === current?.key ? 'active' : ''}
              aria-current={section.key === current?.key ? 'true' : undefined}
            >
              {section.title}
            </Link>
          ))}
        </nav>
        <div className="topbar-user">
          <span>
            {user?.username} <span className="badge">{ROLE_LABELS[user?.role] || user?.role}</span>
          </span>
          <button className="btn btn-ghost" onClick={logout}>Выход</button>
        </div>
      </header>
      {current && current.pages.length > 1 && (
        <nav className="subnav" aria-label={current.title}>
          {current.pages.map((page) => (
            <NavLink key={page.path} to={page.path} end>
              {page.title}
            </NavLink>
          ))}
        </nav>
      )}
      <main className="content">
        <h1>{title}</h1>
        {children}
      </main>
    </div>
  );
};
