export type DeviceStatus = 'active' | 'deactive';

export interface DevicePublic {
  device_id: number;
  devicename: string | null;
  status: DeviceStatus | null;
  location: string | null;
  device_type: string | null;
  topic: string | null;
  publish_topic: string | null;
}

export interface DeviceAuthorizedUser {
  user_id: number;
  username: string;
  fullname: string;
  expired_at: string | null;
}

export interface DeviceDetailPublic extends DevicePublic {
  password?: string | null;
  user_device_asignment_id?: number | null;
  authorized_users?: DeviceAuthorizedUser[];
}
