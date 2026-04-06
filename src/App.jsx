/**
 * Thành phần gốc của cây React — hiện chỉ bọc `IoTApp` (routing + auth).
 * Tách nhỏ để sau này có thể thêm provider toàn cục (theme, i18n) mà không đụng `main.jsx`.
 */
import React from 'react';
import IoTApp from './components/IoTApp.jsx';

export default function App() {
  return <IoTApp />;
}
