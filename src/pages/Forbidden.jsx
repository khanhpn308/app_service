import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

export default function Forbidden() {
  const navigate = useNavigate();
  return (
    <div className="max-w-lg mx-auto text-center py-12 space-y-4">
      <ShieldAlert className="h-16 w-16 text-amber-500 mx-auto" />
      <h1 className="text-2xl font-bold text-foreground">403 Forbidden</h1>
      <p className="text-muted-foreground">Bạn không có quyền truy cập trang này.</p>
      <button
        type="button"
        onClick={() => navigate('/home')}
        className="px-6 py-2 bg-primary hover:bg-primary/90 text-foreground rounded-lg transition-colors duration-200"
      >
        Về trang Home
      </button>
    </div>
  );
}

