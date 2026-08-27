import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AddDeviceModal from './AddDeviceModal';
import { apiFetch } from '../lib/api';

vi.mock('../lib/api', () => ({ apiFetch: vi.fn() }));

describe('AddDeviceModal Gateway creation', () => {
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(1700000123456);
    apiFetch.mockReset();
    apiFetch.mockImplementation(async (_path, options) => {
      const body = JSON.parse(options.body);
      return {
        device_id: body.device_id,
        devicename: body.devicename,
        status: body.status,
        location: body.location,
        device_type: body.device_type,
        topic: body.topic,
        publish_topic: body.publish_topic,
      };
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('shows Gateway defaults and submits them with the generated device ID', async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn();
    render(<AddDeviceModal onClose={vi.fn()} onAdd={onAdd} />);

    expect(screen.getByRole('button', { name: 'Close add device dialog' })).toBeTruthy();
    await user.selectOptions(screen.getByRole('combobox'), 'gateway');

    expect(screen.getByRole('dialog', { name: 'Add New Device' })).toBeTruthy();
    expect(screen.getByText('Device ID: 123456')).toBeTruthy();
    expect(screen.getByLabelText('MQTT Topic backend nhận').value).toBe(
      'gateway/123456/backend_receive',
    );
    expect(screen.getByLabelText('MQTT Topic backend gửi').value).toBe(
      'gateway/123456/backend_send',
    );

    await user.type(screen.getByLabelText(/^Device Name/), 'Gateway Floor 1');
    await user.type(screen.getByLabelText(/^Location/), 'Floor_1');
    await user.type(screen.getByLabelText(/^Device Password/), 'secret123');
    await user.click(screen.getByRole('button', { name: 'Add Device' }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const [path, options] = apiFetch.mock.calls[0];
    expect(path).toBe('/api/devices');
    expect(JSON.parse(options.body)).toMatchObject({
      device_id: 123456,
      device_type: 'gateway',
      topic: 'gateway/123456/backend_receive',
      publish_topic: 'gateway/123456/backend_send',
    });
    expect(onAdd).toHaveBeenCalledTimes(1);
  });
});
