import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DevicePublic } from "@/types/device";
import { DeviceTableRow } from "./DeviceTableRow";
import { DeviceTableSkeleton } from "./DeviceTableSkeleton";

interface DeviceTableProps {
  devices: DevicePublic[];
  isLoading: boolean;
  onRowClick: (id: number) => void;
}

export const DeviceTable = ({ devices, isLoading, onRowClick }: DeviceTableProps) => {
  if (isLoading) return <DeviceTableSkeleton />;

  return (
    <div className="rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[100px]">ID</TableHead>
            <TableHead>Tên thiết bị</TableHead>
            <TableHead>Trạng thái</TableHead>
            <TableHead>Vị trí</TableHead>
            <TableHead>Loại</TableHead>
            <TableHead>Topic</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {devices.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                Không tìm thấy thiết bị nào.
              </TableCell>
            </TableRow>
          ) : (
            devices.map((device) => (
              <DeviceTableRow 
                key={device.device_id} 
                device={device} 
                onClick={onRowClick} 
              />
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
};
