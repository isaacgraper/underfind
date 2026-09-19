import React from 'react';
import { ActiveTab } from '../../types';
import './Navbar.styles.css';

export interface NavbarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onTabChange }) => {
  return (
    <header className="site-header">
      <nav className="nav-tabs" aria-label="Navegação Principal">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => onTabChange('dashboard')}
        >
          Dashboard
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'shorts' ? 'active' : ''}`}
          onClick={() => onTabChange('shorts')}
        >
          Descobridor de Shorts Virais
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'trending' ? 'active' : ''}`}
          onClick={() => onTabChange('trending')}
        >
          Trending
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'ideas' ? 'active' : ''}`}
          onClick={() => onTabChange('ideas')}
        >
          Quadro de Ideias
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => onTabChange('search')}
        >
          Explorer
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'mcp' ? 'active' : ''}`}
          onClick={() => onTabChange('mcp')}
        >
          MCP
        </button>
      </nav>
    </header>
  );
};
