import { cn } from '@/lib/utils';

/**
 * Khung card/section chuẩn dùng design token (bg-card + border-border + shadow).
 * Thay cho pattern lặp `bg-slate-800 rounded-xl border border-slate-700 shadow-lg`.
 *
 * Mọi prop khác (onClick, role...) được forward xuống <div>.
 *
 * @param {string} [className] - Class bổ sung (merge qua cn()).
 */
export function Panel({ className, children, ...props }) {
  return (
    <div
      className={cn(
        'bg-card text-card-foreground rounded-xl border border-border shadow-lg',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export default Panel;
