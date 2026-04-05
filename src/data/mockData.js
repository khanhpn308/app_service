// Mock data for IoT Management System

export const generateTemperatureData = () => {
  const data = [];
  const now = new Date();
  
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now - i * 60 * 60 * 1000);
    data.push({
      time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      value: 20 + Math.random() * 10 + Math.sin(i / 4) * 3
    });
  }
  
  return data;
};

export const generateHumidityData = () => {
  const data = [];
  const now = new Date();
  
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now - i * 60 * 60 * 1000);
    data.push({
      time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      value: 50 + Math.random() * 20 + Math.cos(i / 3) * 5
    });
  }
  
  return data;
};

export const mockDevices = [
  {
    id: 'DEV001',
    name: 'Temperature Sensor A',
    type: 'Temperature',
    status: 'online',
    location: 'Building A - Floor 1',
    lastUpdate: '2 minutes ago',
    password: 'temp_sensor_2024',
    value: 23.5,
    unit: '°C'
  },
  {
    id: 'DEV002',
    name: 'Humidity Sensor B',
    type: 'Humidity',
    status: 'online',
    location: 'Building A - Floor 2',
    lastUpdate: '5 minutes ago',
    password: 'humid_sensor_2024',
    value: 65,
    unit: '%'
  },
  {
    id: 'DEV003',
    name: 'Motion Detector C',
    type: 'Motion',
    status: 'offline',
    location: 'Building B - Entrance',
    lastUpdate: '2 hours ago',
    password: 'motion_det_2024',
    value: 0,
    unit: 'events'
  },
  {
    id: 'DEV004',
    name: 'Smart Thermostat D',
    type: 'Thermostat',
    status: 'online',
    location: 'Building B - Office',
    lastUpdate: '1 minute ago',
    password: 'thermo_stat_2024',
    value: 22,
    unit: '°C'
  },
  {
    id: 'DEV005',
    name: 'Air Quality Monitor E',
    type: 'Air Quality',
    status: 'online',
    location: 'Building C - Lab',
    lastUpdate: '3 minutes ago',
    password: 'air_quality_2024',
    value: 85,
    unit: 'AQI'
  },
  {
    id: 'DEV006',
    name: 'Light Controller F',
    type: 'Lighting',
    status: 'online',
    location: 'Building C - Hallway',
    lastUpdate: '30 seconds ago',
    password: 'light_ctrl_2024',
    value: 75,
    unit: '%'
  }
];

export const generateDeviceHistory = (deviceId) => {
  const history = [];
  const now = new Date();
  
  for (let i = 0; i < 20; i++) {
    const timestamp = new Date(now - i * 15 * 60 * 1000);
    const device = mockDevices.find(d => d.id === deviceId) || mockDevices[0];
    
    let value;
    switch (device.type) {
      case 'Temperature':
        value = (20 + Math.random() * 10).toFixed(1) + ' °C';
        break;
      case 'Humidity':
        value = (50 + Math.random() * 30).toFixed(1) + ' %';
        break;
      case 'Motion':
        value = Math.random() > 0.5 ? 'Detected' : 'No Motion';
        break;
      case 'Thermostat':
        value = (18 + Math.random() * 8).toFixed(1) + ' °C';
        break;
      case 'Air Quality':
        value = Math.floor(50 + Math.random() * 100) + ' AQI';
        break;
      case 'Lighting':
        value = Math.floor(Math.random() * 100) + ' %';
        break;
      default:
        value = 'N/A';
    }
    
    history.push({
      id: i + 1,
      parameterValue: value,
      timestamp: timestamp.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    });
  }
  
  return history;
};

export const mockUsers = [
  {
    id: 'user_001',
    name: 'John Smith',
    email: 'john.smith@iot.com',
    role: 'user',
    assignedDevices: ['DEV001', 'DEV002'],
    createdAt: '2024-01-15'
  },
  {
    id: 'user_002',
    name: 'Sarah Johnson',
    email: 'sarah.johnson@iot.com',
    role: 'user',
    assignedDevices: ['DEV003', 'DEV004'],
    createdAt: '2024-01-20'
  },
  {
    id: 'user_003',
    name: 'Michael Brown',
    email: 'michael.brown@iot.com',
    role: 'user',
    assignedDevices: ['DEV005'],
    createdAt: '2024-02-01'
  },
  {
    id: 'user_004',
    name: 'Emily Davis',
    email: 'emily.davis@iot.com',
    role: 'user',
    assignedDevices: ['DEV006'],
    createdAt: '2024-02-10'
  },
  {
    id: 'user_005',
    name: 'Robert Wilson',
    email: 'robert.wilson@iot.com',
    role: 'user',
    assignedDevices: [],
    createdAt: '2024-02-15'
  }
];

export const deviceStatsSummary = {
  total: mockDevices.length,
  online: mockDevices.filter(d => d.status === 'online').length,
  offline: mockDevices.filter(d => d.status === 'offline').length,
  uptime: '99.2%'
};

export const mockRecentAlerts = () => {
  const now = Date.now();
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const severities = ['info', 'warning', 'critical'];
  const messages = [
    'Motor temperature high',
    'Vibration exceeded threshold',
    'Device disconnected',
    'Power fluctuation detected',
    'Sensor calibration required',
    'Recovered: normal operating range',
  ];

  return Array.from({ length: 8 }).map((_, i) => {
    const device = pick(mockDevices);
    const severity = pick(severities);
    return {
      id: `ALERT_${i + 1}`,
      time: new Date(now - i * 7 * 60 * 1000).toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }),
      deviceId: device.id,
      severity,
      message: pick(messages),
    };
  });
};
