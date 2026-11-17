const BASE_URL = '';

function getToken() {
  return localStorage.getItem('admin_token') || '';
}

async function apiRequest(path, options = {}) {
  const headers = {
    ...options.headers
  };
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;

  // Не устанавливаем Content-Type для FormData — браузер добавит boundary автоматически
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(BASE_URL + path, {
    ...options,
    headers
  });

  let data = null;
  try { data = await res.json(); } catch (e) { data = {}; }

  if (!res.ok) {
    const err = new Error(data.error || 'Ошибка сервера ' + res.status);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

// =============== ПУБЛИЧНЫЙ КАТАЛОГ ===============

async function loadPublicProducts() {
  return await apiRequest('/api/products');
}

// =============== АДМИНКА ===============

async function adminLogin(username, password) {
  const data = await apiRequest('/api/admin/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
  localStorage.setItem('admin_token', data.token);
  localStorage.setItem('admin_user', data.username);
  localStorage.setItem('admin_role', data.role || 'user');
  return data;
}

async function adminRegister(username, password, confirmPassword) {
  const data = await apiRequest('/api/admin/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, confirm_password: confirmPassword })
  });
  return data;
}

async function adminLogout() {
  localStorage.removeItem('admin_token');
  localStorage.removeItem('admin_user');
}

async function adminGetProducts() {
  return await apiRequest('/api/admin/products');
}

async function adminAddProduct(product) {
  // product — это FormData, не сериализуем в JSON
  return await apiRequest('/api/admin/products', {
    method: 'POST',
    body: product
  });
}

async function adminUpdateProduct(id, product) {
  return await apiRequest('/api/admin/products/' + id, {
    method: 'PUT',
    body: JSON.stringify(product)
  });
}

async function adminDeleteProduct(id) {
  return await apiRequest('/api/admin/products/' + id, {
    method: 'DELETE'
  });
}

function isAdminLoggedIn() {
  return !!getToken();
}

function getUserRole() {
  return localStorage.getItem('admin_role') || 'user';
}

function isUserAdmin() {
  return getUserRole() === 'admin';
}
