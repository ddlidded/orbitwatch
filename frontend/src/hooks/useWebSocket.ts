import { useEffect, useRef, useState } from 'react';

export default function useWebSocket(
  onMessage: (data: any) => void,
  subscriptions: string[]
) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number>(0);

  useEffect(() => {
    let ws: WebSocket | null = null;

    const connect = () => {
      ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/live`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectRef.current = 0;
        subscriptions.forEach((channel) => ws?.send(`subscribe:${channel}`));
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          onMessage(msg);
        } catch (e) {
          console.warn('WS parse error', e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectRef.current = Math.min(reconnectRef.current + 1, 10);
        setTimeout(connect, Math.min(1000 * reconnectRef.current, 10000));
      };

      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();
    return () => ws?.close();
  }, [subscriptions.join(','), onMessage]);

  return connected;
}
