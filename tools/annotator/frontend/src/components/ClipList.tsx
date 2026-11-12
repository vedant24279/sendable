import { useMemo, useState } from 'react';
import type { FC } from 'react';
import { useAnnotatorStore } from '../store';
import { useLabelStore } from '../labelStore';

export const ClipList: FC = () => {
  const clips = useAnnotatorStore((s) => s.clips);
  const selectedClipId = useAnnotatorStore((s) => s.selectedClipId);
  const selectClip = useAnnotatorStore((s) => s.selectClip);
  const loadingClips = useAnnotatorStore((s) => s.loadingClips);
  const error = useAnnotatorStore((s) => s.error);
  const loadClips = useAnnotatorStore((s) => s.loadClips);
  const currentLabel = useLabelStore((s) => s.label);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'none' | 'draft' | 'final' | 'flagged'>('all');
  const [sortBy, setSortBy] = useState<'default' | 'system_residual'>('default');

  const filteredClips = useMemo(() => {
    const list = clips.filter((c) => {
      const matchesSearch = c.clip_id.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === 'all' || c.label_status === statusFilter;
      return matchesSearch && matchesStatus;
    });

    if (sortBy === 'system_residual') {
      list.sort((a, b) => {
        const resA = a.system_residual_px != null ? a.system_residual_px : -1;
        const resB = b.system_residual_px != null ? b.system_residual_px : -1;
        return resB - resA;
      });
    }

    return list;
  }, [clips, search, statusFilter, sortBy]);

  return (
    <aside className="clip-list-pane">
      <div className="clip-list-header">
        <h2 className="pane-title">Clips ({clips.length})</h2>
        <div className="clip-filters">
          <input
            type="text"
            className="search-input"
            placeholder="Search clip id..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          >
            <option value="all">All statuses</option>
            <option value="none">None</option>
            <option value="draft">Draft</option>
            <option value="final">Final</option>
            <option value="flagged">Flagged</option>
          </select>
          <select
            className="filter-select sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            title="Sort clips list"
          >
            <option value="default">Default order</option>
            <option value="system_residual">By system residual (high to low)</option>
          </select>
        </div>
      </div>

      <div className="clip-list-scroll">
        {loadingClips && <div className="loading-indicator">Loading clips...</div>}
        {error && (
          <div className="error-banner">
            <div className="error-title">⚠️ Backend Disconnected</div>
            <p className="error-desc">Unable to reach API on 127.0.0.1:8765</p>
            <button className="retry-btn" onClick={() => void loadClips()}>
              Retry Connection
            </button>
          </div>
        )}
        {!loadingClips && !error && filteredClips.length === 0 && (
          <div className="empty-message">No matching delivery clips</div>
        )}
        {filteredClips.map((clip) => {
          const isSelected = clip.clip_id === selectedClipId;
          const hasGt =
            clip.has_gt_calibration ||
            (clip.clip_id === selectedClipId && Boolean(currentLabel?.calibration_gt));

          return (
            <div
              key={clip.clip_id}
              className={`clip-item ${isSelected ? 'selected' : ''}`}
              onClick={() => void selectClip(clip.clip_id)}
            >
              <div className="clip-row-main">
                <span className="clip-title">{clip.clip_id}</span>
                {hasGt && (
                  <span className="calib-badge" title="Has ground-truth calibration">
                    C
                  </span>
                )}
                {clip.frame_count_mismatch && (
                  <span className="badge-warning-icon" title="Frame count mismatch with video metadata!">
                    ⚠️
                  </span>
                )}
                <span className={`status-pill status-${clip.label_status}`}>
                  {clip.label_status}
                </span>
              </div>
              <div className="clip-row-sub">
                <span className={`ball-badge ball-${clip.ball_type || 'unknown'}`}>
                  {clip.ball_type || 'N/A'}
                </span>
                <span className="clip-meta-frames">{clip.frame_count} frames</span>
                {clip.system_residual_px != null && (
                  <span className="clip-residual-tag" title="System stump residual">
                    {clip.system_residual_px.toFixed(1)} px
                  </span>
                )}
                <span className={`results-badge ${clip.has_results ? 'has-results' : 'no-results'}`}>
                  {clip.has_results ? 'Results' : 'No Res'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="clip-list-footer">
        <span className="hint-text">Use <kbd>[</kbd> and <kbd>]</kbd> to switch clips</span>
      </div>
    </aside>
  );
};
