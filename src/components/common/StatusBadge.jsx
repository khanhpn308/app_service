import { cn } from '@/lib/utils';
import { isOnline } from '@/lib/deviceStatus';

/**
 * Badge trạng thái thiết bị: chấm tròn + nhãn ONLINE/OFFLINE.
 * Nhận status thô (active/deactive hoặc online/offline) và tự chuẩn hoá qua isOnline().
 * Màu online=xanh / offline=đỏ là màu semantic — giữ nguyên, không token hoá.
 *
 * @param {string} status - Trạng thái thô từ API hoặc đã normalize.
 * @param {string} [className]
 */
export function StatusBadge({ status, className }) {
  const online = isOnline(status);
  return (
    <span className={cn('flex items-center gap-2', className)}>
      <span
        className={cn(
          'w-2 h-2 rounded-full',
          online ? 'bg-green-500 animate-pulse' : 'bg-red-500',
        )}
      />
      <span
        className={cn(
          'text-sm font-medium',
          online ? 'text-green-500' : 'text-red-500',
        )}
      >
        {online ? 'ONLINE' : 'OFFLINE'}
      </span>
    </span>
  );
}

export default StatusBadge;
