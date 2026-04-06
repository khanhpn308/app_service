/**
 * Điểm vào SPA (Single Page Application) — mount React vào `#root`.
 *
 * - `StrictMode`: gọi effect hai lần ở dev để phát hiện side-effect (React 18).
 * - Import `global.css`: token Tailwind / style toàn cục.
 */
import React from 'react';
import ReactDOM from 'react-dom/client';

import './styles/global.css';

import App from './App.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
