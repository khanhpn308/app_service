# `components/ui` — shadcn/ui

Các file trong thư mục này là **primitive UI** theo [shadcn/ui](https://ui.shadcn.com/) (Radix UI + Tailwind). Không chứa nghiệp vụ IoT; tái sử dụng giữa các trang.

- **Cách đọc**: xem props TypeScript ở đầu mỗi file; hàm export mặc định là component.
- **Khi sửa**: giữ API ổn định để không phá layout; ưu tiên chỉnh theme/spacing ở `global.css` hoặc token nếu có.

Chi tiết thuật ngữ và luồng app nằm ở `docs/architecture/codebase-walkthrough.md`.
