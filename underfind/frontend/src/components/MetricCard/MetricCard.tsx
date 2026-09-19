import React from 'react';
import './MetricCard.styles.css';

export interface MetricCardProps {
  label: string;
  badge?: string;
  badgeText?: string;
  badgeVariant?: 'viral' | 'blue' | 'neutral';
  value: string | number;
  unit?: string;
  caption: string;
  highlight?: boolean;
  trend?: 'up' | 'down';
  trendValue?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  badge,
  badgeText,
  badgeVariant = 'neutral',
  value,
  unit,
  caption,
  highlight = false,
  trend,
  trendValue,
}) => {
  const displayBadge = badge || badgeText;
  const badgeClass =
    badgeVariant === 'viral' || highlight
      ? 'pill-viral'
      : badgeVariant === 'blue'
      ? 'pill-blue'
      : 'pill-neutral';

  return (
    <div className={`metric-card ${highlight ? 'metric-card-highlight' : ''}`}>
      <div className="metric-header">
        <span className="metric-label">{label}</span>
        <div className="metric-header-right">
          {trend && (
            <span className={`metric-trend ${trend === 'up' ? 'trend-up' : 'trend-down'}`}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="7" y1="17" x2="17" y2="7" />
                <polyline points="7 7 17 7 17 17" />
              </svg>
              {trendValue && <span>{trendValue}</span>}
            </span>
          )}
          {displayBadge && <span className={`metric-pill ${badgeClass}`}>{displayBadge}</span>}
        </div>
      </div>

      <div className="metric-number">
        {value}
        {unit && <span className="metric-unit">{unit}</span>}
      </div>

      <p className="metric-caption">{caption}</p>
    </div>
  );
};
