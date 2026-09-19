import { io } from 'socket.io-client';

let socket = null;

export const getSocket = () => {
  if (!socket) {
    const socketUrl = import.meta.env?.VITE_SOCKET_URL || import.meta.env?.VITE_API_URL || '/';
    socket = io(socketUrl, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
    });
  }
  return socket;
};
