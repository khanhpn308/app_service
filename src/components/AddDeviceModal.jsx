import React, { useState } from 'react';
import { X, Cpu, AlertCircle } from 'lucide-react';
import { apiFetch } from '../lib/api';

const AddDeviceModal = ({ onClose, onAdd }) => {
  const [deviceId] = useState(() => Math.floor(Date.now() % 1000000));
  const [formData, setFormData] = useState({
    name: '',
    type: 'Temperature',
    location: '',
    password: '',
    topic: '',
    publishTopic: '',
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  const deviceTypes = [
    { value: 'Temperature', label: 'Nhiệt độ (Temperature)' },
    { value: 'Power', label: 'Công suất (Power)' },
    { value: 'Vibration', label: 'Độ rung (Vibration)' },
    { value: 'GPS', label: 'Định vị (GPS)' },
    { value: 'gateway', label: 'Gateway' },
  ];

  const gatewayReceiveTopic = `gateway/${deviceId}/backend_receive`;
  const gatewaySendTopic = `gateway/${deviceId}/backend_send`;

  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.name) {
      newErrors.name = 'Device name is required';
    }
    
    if (!formData.location) {
      newErrors.location = 'Location is required';
    }
    
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((current) => {
      if (name !== 'type') return { ...current, [name]: value };
      if (value === 'gateway') {
        return {
          ...current,
          type: value,
          topic: current.topic.trim() || gatewayReceiveTopic,
          publishTopic: current.publishTopic.trim() || gatewaySendTopic,
        };
      }
      return {
        ...current,
        type: value,
        topic: current.topic === gatewayReceiveTopic ? '' : current.topic,
        publishTopic: current.publishTopic === gatewaySendTopic ? '' : current.publishTopic,
      };
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (validateForm()) {
      setSubmitting(true);
      setSubmitError('');
      try {
        // DB schema: device_id (INT), devicename (VARCHAR), password, status, user_device_asignment_id (NOT NULL)
        const unit =
          formData.type === 'Temperature'
            ? '°C'
            : formData.type === 'Power'
              ? 'V/A'
              : formData.type === 'Vibration'
                ? 'mm/s'
                : formData.type === 'GPS'
                  ? ''
                  : 'units';

        const created = await apiFetch('/api/devices', {
          method: 'POST',
          body: JSON.stringify({
            device_id: deviceId,
            devicename: formData.name,
            password: formData.password,
            status: 'active',
            user_device_asignment_id: 0,
            location: formData.location,
            device_type: formData.type,
            topic:
              formData.topic.trim() ||
              (formData.type === 'gateway' ? gatewayReceiveTopic : null),
            publish_topic:
              formData.publishTopic.trim() ||
              (formData.type === 'gateway' ? gatewaySendTopic : null),
          }),
        });

        // Keep existing UI shape via onAdd (readings filled from live payload later, not DB)
        onAdd({
          device_id: created?.device_id ?? deviceId,
          devicename: created?.devicename ?? formData.name,
          status: created?.status ?? 'active',
          device_type: created?.device_type ?? formData.type,
          location: created?.location ?? formData.location,
          type: formData.type,
          lastUpdate: '—',
          value: '—',
          unit,
        });
      } catch (err) {
        setSubmitError(err.message || 'Add device failed');
      } finally {
        setSubmitting(false);
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-device-title"
        className="bg-card rounded-2xl shadow-2xl max-w-md w-full border border-border max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Cpu className="h-6 w-6 text-primary" />
            </div>
            <h2 id="add-device-title" className="text-xl font-bold text-foreground">Add New Device</h2>
          </div>
          <button
            type="button"
            aria-label="Close add device dialog"
            onClick={onClose}
            className="p-2 hover:bg-card rounded-lg transition-colors duration-200"
          >
            <X className="h-5 w-5 text-muted-foreground" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {submitError && (
            <div className="p-3 rounded-lg bg-red-900/40 border border-red-700 text-red-200 text-sm">
              {submitError}
            </div>
          )}
          {/* Device Name */}
          <div>
            <label htmlFor="add-device-name" className="block text-sm font-medium text-foreground/90 mb-2">
              Device Name<span aria-hidden="true"> *</span>
            </label>
            <input
              id="add-device-name"
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className={`w-full px-4 py-3 bg-card border ${
                errors.name ? 'border-red-500' : 'border-border'
              } rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200`}
              placeholder="e.g., Temperature Sensor A"
            />
            {errors.name && (
              <div className="flex items-center mt-2 text-red-400 text-sm">
                <AlertCircle className="h-4 w-4 mr-1" />
                {errors.name}
              </div>
            )}
          </div>

          {/* Device Type */}
          <div>
            <label htmlFor="add-device-type" className="block text-sm font-medium text-foreground/90 mb-2">
              Device Type<span aria-hidden="true"> *</span>
            </label>
            <select
              id="add-device-type"
              name="type"
              value={formData.type}
              onChange={handleChange}
              className="w-full px-4 py-3 bg-card border border-border rounded-lg text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200"
            >
              {deviceTypes.map((type) => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
          </div>

          {formData.type === 'gateway' && (
            <p className="text-sm text-muted-foreground" role="status">
              Device ID: {deviceId}
            </p>
          )}

          {/* Location */}
          <div>
            <label htmlFor="add-device-location" className="block text-sm font-medium text-foreground/90 mb-2">
              Location<span aria-hidden="true"> *</span>
            </label>
            <input
              id="add-device-location"
              type="text"
              name="location"
              value={formData.location}
              onChange={handleChange}
              className={`w-full px-4 py-3 bg-card border ${
                errors.location ? 'border-red-500' : 'border-border'
              } rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200`}
              placeholder="e.g., Building A - Floor 1"
            />
            {errors.location && (
              <div className="flex items-center mt-2 text-red-400 text-sm">
                <AlertCircle className="h-4 w-4 mr-1" />
                {errors.location}
              </div>
            )}
          </div>

          {/* Password */}
          <div>
            <label htmlFor="add-device-password" className="block text-sm font-medium text-foreground/90 mb-2">
              Device Password<span aria-hidden="true"> *</span>
            </label>
            <input
              id="add-device-password"
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className={`w-full px-4 py-3 bg-card border ${
                errors.password ? 'border-red-500' : 'border-border'
              } rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200`}
              placeholder="Enter device password"
            />
            {errors.password && (
              <div className="flex items-center mt-2 text-red-400 text-sm">
                <AlertCircle className="h-4 w-4 mr-1" />
                {errors.password}
              </div>
            )}
          </div>

          <div>
            <label htmlFor="add-device-topic" className="block text-sm font-medium text-foreground/90 mb-2">
              MQTT Topic backend nhận
            </label>
            <input
              id="add-device-topic"
              type="text"
              name="topic"
              value={formData.topic}
              onChange={handleChange}
              className="w-full px-4 py-3 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200"
              placeholder={formData.type === 'gateway' ? gatewayReceiveTopic : 'devices/101/telemetry'}
            />
            {formData.type === 'gateway' && (
              <p className="mt-1 text-xs text-muted-foreground">Gateway publish ACK và telemetry lên topic này.</p>
            )}
          </div>

          <div>
            <label htmlFor="add-device-publish-topic" className="block text-sm font-medium text-foreground/90 mb-2">
              MQTT Topic backend gửi
            </label>
            <input
              id="add-device-publish-topic"
              type="text"
              name="publishTopic"
              value={formData.publishTopic}
              onChange={handleChange}
              className="w-full px-4 py-3 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200"
              placeholder={formData.type === 'gateway' ? gatewaySendTopic : 'devices/101/downlink'}
            />
            {formData.type === 'gateway' && (
              <p className="mt-1 text-xs text-muted-foreground">Gateway subscribe topic này để nhận cấu hình Anchor.</p>
            )}
          </div>

          {/* Buttons */}
          <div className="flex space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 bg-card hover:bg-muted text-foreground font-semibold rounded-lg transition-colors duration-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-3 bg-primary hover:bg-primary/90 text-foreground font-semibold rounded-lg transition-all duration-200 shadow-lg shadow-blue-500/50 disabled:opacity-60"
            >
              {submitting ? 'Adding...' : 'Add Device'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddDeviceModal;
