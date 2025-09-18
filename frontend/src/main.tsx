import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import { SavedQueries } from './components/SavedQueries.tsx'
import './index.css'

// Simple routing based on pathname
const Router = () => {
  const path = window.location.pathname;

  if (path === '/saved' || path === '/saved/' || path === '/saved/index.html') {
    return <SavedQueries />;
  }

  return <App />;
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Router />
  </React.StrictMode>,
)