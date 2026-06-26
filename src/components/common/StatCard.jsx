/**
 * Thẻ KPI: tiêu đề + giá trị lớn + icon (nền nhạt theo màu) + subtitle.
 * Tách từ bản inline trong Home.jsx — GIỮ NGUYÊN API props để thay 1-1.
 *
 * Nền card dùng token (bg-card/border-border); riêng `color` là màu semantic
 * (vd 'text-blue-500', 'text-green-500') do caller truyền — KHÔNG token hoá
 * vì mỗi KPI mang ý nghĩa màu riêng (online=xanh, offline=đỏ...).
 *
 * @param {string} title
 * @param {string|number} value
 * @param {React.ComponentType} icon - Component icon (lucide-react).
 * @param {string} color - Class màu chữ Tailwind, vd 'text-blue-500'.
 * @param {string} [subtitle]
 */
export function StatCard({ title, value, icon: Icon, color, subtitle }) {
  return (
    <div className="bg-card text-card-foreground rounded-xl p-6 border border-border shadow-lg hover:shadow-xl transition-all duration-200">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-muted-foreground text-sm font-medium mb-2">{title}</p>
          <p className={`text-3xl font-bold ${color}`}>{value}</p>
          {subtitle && <p className="text-muted-foreground text-xs mt-2">{subtitle}</p>}
        </div>
        <div className={`p-3 rounded-lg ${color.replace('text', 'bg').replace('500', '500/20')}`}>
          <Icon className={`h-6 w-6 ${color}`} />
        </div>
      </div>
    </div>
  );
}

export default StatCard;
