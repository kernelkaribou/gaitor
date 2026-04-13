import './app.css';
import App from './App.svelte';
import { mount } from 'svelte';
import { connectWebSocket } from './lib/websocket.js';

const app = mount(App, { target: document.getElementById('app') });

connectWebSocket();

export default app;
