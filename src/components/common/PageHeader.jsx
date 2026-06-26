/**
 * Tiêu đề trang chuẩn: <h1> + mô tả + slot action bên phải.
 * Dùng design token (text-foreground / text-muted-foreground) thay vì hardcode slate.
 *
 * @param {string} title - Tiêu đề trang (render trong <h1>).
 * @param {string} [description] - Mô tả phụ dưới tiêu đề.
 * @param {React.ReactNode} [actions] - Nút/badge hiển thị bên phải (desktop) hoặc xuống dòng (mobile).
 */
export function PageHeader({ title, description, actions }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">{title}</h1>
        {description && <p className="text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}

export default PageHeader;
