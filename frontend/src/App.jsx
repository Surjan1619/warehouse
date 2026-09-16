
import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'))
  const [products, setProducts] = useState([])
  const [types, setTypes] = useState([])
  const [error, setError] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  
  const [newProductName, setNewProductName] = useState('')
  const [newProductQuantity, setNewProductQuantity] = useState(0)
  const [newProductTypeId, setNewProductTypeId] = useState('')
  const [newProductLength, setNewProductLength] = useState('')
  const [newProductWidth, setNewProductWidth] = useState('')
  const [newProductThickness, setNewProductThickness] = useState('')
  const [newProductShape, setNewProductShape] = useState('')
  const [newProductWeight, setNewProductWeight] = useState('')
  
  const [newTypeName, setNewTypeName] = useState('')
  const [newTypeAttributes, setNewTypeAttributes] = useState({ 
    length: false, width: false, thickness: false, shape: false, weight: false 
  })

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)

      const response = await fetch('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      })

      if (!response.ok) throw new Error('Неверные данные')
      const data = await response.json()
      localStorage.setItem('token', data.access_token)
      setIsLoggedIn(true)
    } catch (err) {
      setError(err.message)
    }
  }

  const fetchProducts = async () => {
    try {
      const response = await fetch('http://localhost:8000/products/', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
      if (!response.ok) throw new Error('Ошибка загрузки товаров')
      const data = await response.json()
      setProducts(data)
    } catch (err) {
      alert(err.message)
    }
  }

  const fetchTypes = async () => {
    try {
      const response = await fetch('http://localhost:8000/products/types', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
      if (!response.ok) throw new Error('Ошибка загрузки типов')
      const data = await response.json()
      setTypes(data)
    } catch (err) {
      alert(err.message)
    }
  }

  const addProduct = async (e) => {
    e.preventDefault()
    try {
      const response = await fetch('http://localhost:8000/products/', {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          name: newProductName, 
          quantity: parseInt(newProductQuantity), 
          product_type_id: newProductTypeId ? parseInt(newProductTypeId) : null,
          length: newProductLength ? parseFloat(newProductLength) : null,
          width: newProductWidth ? parseFloat(newProductWidth) : null,
          thickness: newProductThickness ? parseFloat(newProductThickness) : null,
          shape: newProductShape || null,
          weight: newProductWeight ? parseFloat(newProductWeight) : null
        }),
      })
      if (!response.ok) throw new Error('Ошибка создания товара')
      setNewProductName('')
      setNewProductQuantity(0)
      setNewProductTypeId('')
      setNewProductLength('')
      setNewProductWidth('')
      setNewProductThickness('')
      setNewProductShape('')
      setNewProductWeight('')
      fetchProducts()
    } catch (err) {
      alert(err.message)
    }
  }

  const addProductType = async (e) => {
    e.preventDefault()
    try {
      const response = await fetch('http://localhost:8000/products/types', {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name: newTypeName, required_attributes: newTypeAttributes }),
      })
      if (!response.ok) throw new Error('Ошибка создания типа')
      setNewTypeName('')
      setNewTypeAttributes({ length: false, width: false, thickness: false, shape: false, weight: false })
      fetchTypes()
    } catch (err) {
      alert(err.message)
    }
  }

  useEffect(() => {
    if (isLoggedIn) fetchTypes()
  }, [isLoggedIn])

  const selectedType = types.find(t => t.id == newProductTypeId)

  return (
    <div className="login-container">
      {!isLoggedIn ? (
        <div className="login-card">
          <h1>Вход</h1>
          {error && <p style={{color: 'red'}}>{error}</p>}
          <form onSubmit={handleLogin}>
            <div className="input-group">
              <label htmlFor="username">Имя пользователя</label>
              <input type="text" id="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div className="input-group">
              <label htmlFor="password">Пароль</label>
              <input type="password" id="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button type="submit" className="login-button">Войти</button>
          </form>
        </div>
      ) : (
        <div className="products-container" style={{padding: '20px'}}>
          <h1>Управление товарами</h1>
          
          <form onSubmit={addProductType} style={{marginBottom: '20px', border: '1px solid #ccc', padding: '10px'}}>
            <h3>Добавить тип продукта</h3>
            <input placeholder="Название типа" value={newTypeName} onChange={e => setNewTypeName(e.target.value)} required />
            <div>
              <label><input type="checkbox" checked={newTypeAttributes.length} onChange={e => setNewTypeAttributes({...newTypeAttributes, length: e.target.checked})} /> Длина</label>
              <label><input type="checkbox" checked={newTypeAttributes.width} onChange={e => setNewTypeAttributes({...newTypeAttributes, width: e.target.checked})} /> Ширина</label>
              <label><input type="checkbox" checked={newTypeAttributes.thickness} onChange={e => setNewTypeAttributes({...newTypeAttributes, thickness: e.target.checked})} /> Толщина</label>
              <label><input type="checkbox" checked={newTypeAttributes.shape} onChange={e => setNewTypeAttributes({...newTypeAttributes, shape: e.target.checked})} /> Форма</label>
              <label><input type="checkbox" checked={newTypeAttributes.weight} onChange={e => setNewTypeAttributes({...newTypeAttributes, weight: e.target.checked})} /> Вес</label>
            </div>
            <button type="submit">Создать тип</button>
          </form>

          <form onSubmit={addProduct} style={{marginBottom: '20px', border: '1px solid #ccc', padding: '10px'}}>
            <h3>Добавить товар</h3>
            <input placeholder="Название" value={newProductName} onChange={e => setNewProductName(e.target.value)} required />
            <input type="number" placeholder="Количество" value={newProductQuantity} onChange={e => setNewProductQuantity(e.target.value)} />
            
            <select value={newProductTypeId} onChange={e => setNewProductTypeId(e.target.value)}>
              <option value="">Выберите тип</option>
              {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>

            {selectedType?.required_attributes?.length && (
              <input type="number" step="0.1" placeholder="Длина" value={newProductLength} onChange={e => setNewProductLength(e.target.value)} />
            )}
            {selectedType?.required_attributes?.width && (
              <input type="number" step="0.1" placeholder="Ширина" value={newProductWidth} onChange={e => setNewProductWidth(e.target.value)} />
            )}
            {selectedType?.required_attributes?.thickness && (
              <input type="number" step="0.1" placeholder="Толщина" value={newProductThickness} onChange={e => setNewProductThickness(e.target.value)} />
            )}
            {selectedType?.required_attributes?.shape && (
              <input placeholder="Форма" value={newProductShape} onChange={e => setNewProductShape(e.target.value)} />
            )}
            {selectedType?.required_attributes?.weight && (
              <input type="number" step="0.1" placeholder="Вес" value={newProductWeight} onChange={e => setNewProductWeight(e.target.value)} />
            )}

            <button type="submit">Создать</button>
          </form>

          <button className="login-button" onClick={fetchProducts}>Показать товары</button>
  const deleteProduct = async (id) => {
    try {
      const response = await fetch(`http://localhost:8000/products/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
      if (!response.ok) throw new Error('Ошибка удаления товара')
      fetchProducts()
    } catch (err) {
      alert(err.message)
    }
  }

  const deleteProductType = async (id) => {
    try {
      const response = await fetch(`http://localhost:8000/products/types/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      })
      if (!response.ok) throw new Error('Ошибка удаления типа (возможно, он используется)')
      fetchTypes()
    } catch (err) {
      alert(err.message)
    }
  }

  // ... (JSX list updates)
          <ul>
            {products.map((p, i) => (
              <li key={i}>
                {p.name} ({p.quantity}) - {p.product_type?.name || 'Без типа'}
                <button onClick={() => deleteProduct(p.id)}>Удалить</button>
              </li>
            ))}
          </ul>
          
          <h3>Типы продуктов</h3>
          <ul>
            {types.map(t => (
              <li key={t.id}>
                {t.name}
                <button onClick={() => deleteProductType(t.id)}>Удалить</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default App
