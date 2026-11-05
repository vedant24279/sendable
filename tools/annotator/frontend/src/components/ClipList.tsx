import { useMemo, useState } from 'react';
import type { FC } from 'react';
import { useAnnotatorStore } from '../store';

export const ClipList: FC = () => {
  const clips = useAnnotatorStore((s) => s.clips);
  const selectedClipId = useAnnotatorStore((s) => s.selectedClipId);
  const selectClip = useAnnotatorStore((s) => s.selectClip);
  const loadingClips = useAnnotatorStore((s) => s.loadingClips);
  const error = useAnnotatorStore((s) => s.error);
  const loadClips = useAnnotatorStore((s) => s.loadClips);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'none' | 'draft' | 'final' | 'flagged'>('all');

  const filteredClips = useMemo(() => {
    return clips.filter((c) => {
      const matchesSearch = c.clip_id.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === 'all' || c.label_status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [clips, search, statusFilter]);

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
          return (
            <div
              key={clip.clip_id}
              className={`clip-item ${isSelected ? 'selected' : ''}`}
              onClick={() => void selectClip(clip.clip_id)}
            >
              <div className="clip-row-main">
                <span className="clip-title">{clip.clip_id}</span>
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
