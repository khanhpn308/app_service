import { Badge } from "@/components/ui/badge";
import { TableCell, TableRow } from "@/components/ui/table";
import { DevicePublic } from "@/types/device";

interface DeviceTableRowProps {
  device: DevicePublic;
  onClick: (id: number) => void;
}

export const DeviceTableRow = ({ device, onClick }: DeviceTableRowProps) => {
  return (
    <TableRow 
      className="cursor-pointer hover:bg-muted/50 transition-colors"
      onClick={() => onClick(device.device_id)}
    >
      <TableCell className="font-medium">{device.device_id}</TableCell>
      <TableCell>{device.devicename || "—"}</TableCell>
      <TableCell>
        <Badge variant={device.status === "active" ? "default" : "secondary"}>
          {device.status === "active" ? "Hoạt động" : "Ngừng"}
        </Badge>
      </TableCell>
      <TableCell>{device.location || "—"}</TableCell>
      <TableCell>{device.device_type || "—"}</TableCell>
      <TableCell className="font-mono text-xs">{device.topic || "—"}</TableCell>
    </TableRow>
  );
};
