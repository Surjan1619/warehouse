import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import './App.css';

// 1. Компонент защиты маршрутов
const ProtectedRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
};

// 2. Страница логина
const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch('http://localhost:8000/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    if (response.ok) {
      const data = await response.json();
      localStorage.setItem('token', data.access_token);
      navigate('/home');
    } else {
      alert('Ошибка входа');
    }
  };

  return (
    <div className="login-container">
      <form onSubmit={handleLogin} className="login-card">
        <h1>Вход</h1>
        <input type="text" placeholder="Имя" onChange={(e) => setUsername(e.target.value)} required />
        <input type="password" placeholder="Пароль" onChange={(e) => setPassword(e.target.value)} required />
        <button type="submit">Войти</button>
      </form>
    </div>
  );
};

// 3. Главная страница
const HomePage = () => {
  const navigate = useNavigate();
  return (
    <div style={{padding: '20px'}}>
      <h1>Главная WMS</h1>
      <button onClick={() => navigate('/products')}>Просмотр товаров</button>
      <button onClick={() => navigate('/admin')}>Управление (Admin)</button>
      <button onClick={() => { localStorage.removeItem('token'); navigate('/login'); }}>Выход</button>
    </div>
  );
};

// 4. Страница просмотра товаров
const ProductsPage = () => {
  const [products, setProducts] = useState([]);
  
  useEffect(() => {
    fetch('http://localhost:8000/products/', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
    .then(res => res.json())
    .then(setProducts);
  }, []);

  return (
    <div style={{padding: '20px'}}>
      <h1>Список товаров</h1>
      <ul>
        {products.map(p => <li key={p.id}>{p.name} - {p.quantity} шт.</li>)}
      </ul>
    </div>
  );
};

// 5. Админка (Управление товарами и типами)
const AdminPage = () => {
  const [products, setProducts] = useState([]);
  const [types, setTypes] = useState([]);
  
  useEffect(() => {
    // Загрузка товаров и типов
    Promise.all([
      fetch('http://localhost:8000/products/', { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } }).then(r => r.json()),
      fetch('http://localhost:8000/products/types', { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } }).then(r => r.json())
    ]).then(([p, t]) => { setProducts(p); setTypes(t); });
  }, []);

  return (
    <div style={{padding: '20px'}}>
      <h1>Управление товарами и типами</h1>
      {/* Здесь формы добавления/удаления (из предыдущего кода) */}
      <p>Формы управления будут здесь...</p>
    </div>
  );
};

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/home" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
        <Route path="/products" element={<ProtectedRoute><ProductsPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
        <Route path="/" element={<Navigate to="/home" />} />
      </Routes>
    </Router>
  );
}

export default App;
