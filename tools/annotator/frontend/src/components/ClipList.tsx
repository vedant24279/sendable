import { FC, useMemo, useRef, useState, useEffect } from 'react';
import { useAnnotatorStore } from '../store';
import { useLabelStore } from '../labelStore';
import { timeAgo, sortRecents, sliceRecents } from '../lib/libraryUtils';

export const ClipList: FC = () => {
  const clips = useAnnotatorStore((s) => s.clips);
  const selectedClipId = useAnnotatorStore((s) => s.selectedClipId);
  const selectClip = useAnnotatorStore((s) => s.selectClip);
  const loadingClips = useAnnotatorStore((s) => s.loadingClips);
  const error = useAnnotatorStore((s) => s.error);
  const loadClips = useAnnotatorStore((s) => s.loadClips);
  const currentLabel = useLabelStore((s) => s.label);

  const libraryFolder = useAnnotatorStore((s) => s.libraryFolder);
  const activeTab = useAnnotatorStore((s) => s.activeTab);
  const setActiveTab = useAnnotatorStore((s) => s.setActiveTab);
  const showAllRecents = useAnnotatorStore((s) => s.showAllRecents);
  const setShowAllRecents = useAnnotatorStore((s) => s.setShowAllRecents);
  const hideClipAction = useAnnotatorStore((s) => s.hideClipAction);
  const filePickerTrigger = useAnnotatorStore((s) => s.filePickerTrigger);
  const uploadFiles = useAnnotatorStore((s) => s.uploadFiles);
  const uploadState = useAnnotatorStore((s) => s.uploadState);
  const dismissUploadModal = useAnnotatorStore((s) => s.dismissUploadModal);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'none' | 'draft' | 'final' | 'flagged'>('all');
  const [sortBy, setSortBy] = useState<'default' | 'system_residual'>('default');
  const [isDragOver, setIsDragOver] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Trigger file picker on hotkey O
  useEffect(() => {
    if (filePickerTrigger > 0) {
      fileInputRef.current?.click();
    }
  }, [filePickerTrigger]);

  const hasDebugClips = useMemo(() => clips.some((c) => c.pool === 'debug'), [clips]);
  const libraryClips = useMemo(() => clips.filter((c) => c.pool !== 'debug'), [clips]);

  // Handle file picker selection
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      void uploadFiles(files);
      e.target.value = '';
    }
  };

  // Drag and drop events
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragOver) setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only clear if leaving the pane
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files);
      void uploadFiles(files);
    }
  };

  // Filtered & sorted clips according to activeTab
  const { displayClips, hasMoreRecents, totalRecentsCount } = useMemo(() => {
    let poolClips = clips;
    if (activeTab === 'recents') {
      poolClips = sortRecents(libraryClips);
    } else if (activeTab === 'library') {
      poolClips = libraryClips;
    } else if (activeTab === 'debug') {
      poolClips = clips.filter((c) => c.pool === 'debug');
    }

    const filtered = poolClips.filter((c) => {
      const name = (c.display_name || c.clip_id).toLowerCase();
      const matchesSearch = name.includes(search.toLowerCase()) || c.clip_id.toLowerCase().includes(search.toLowerCase());
      const matchesStatus = statusFilter === 'all' || c.label_status === statusFilter;
      return matchesSearch && matchesStatus;
    });

    if (activeTab === 'debug' && sortBy === 'system_residual') {
      filtered.sort((a, b) => {
        const resA = a.system_residual_px != null ? a.system_residual_px : -1;
        const resB = b.system_residual_px != null ? b.system_residual_px : -1;
        return resB - resA;
      });
    }

    if (activeTab === 'recents') {
      const sliced = sliceRecents(filtered, showAllRecents, 20);
      return {
        displayClips: sliced.visible,
        hasMoreRecents: sliced.hasMore,
        totalRecentsCount: filtered.length,
      };
    }

    return {
      displayClips: filtered,
      hasMoreRecents: false,
      totalRecentsCount: filtered.length,
    };
  }, [clips, libraryClips, activeTab, search, statusFilter, sortBy, showAllRecents]);

  const isEmptyLibrary = libraryClips.length === 0 && (activeTab === 'recents' || activeTab === 'library');

  return (
    <aside
      className={`clip-list-pane ${isDragOver ? 'drag-over-active' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        accept="video/*,.mkv"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileInputChange}
      />

      {/* Drag & Drop Visual Overlay */}
      {isDragOver && (
        <div className="drop-target-overlay">
          <div className="drop-target-content">
            <span className="drop-icon">📥</span>
            <span className="drop-text">Drop videos to add</span>
          </div>
        </div>
      )}

      {/* Header with "Add videos" action */}
      <div className="clip-list-header">
        <div className="clip-header-top">
          <h2 className="pane-title">Deliveries</h2>
          <button
            className="btn-add-videos"
            onClick={() => fileInputRef.current?.click()}
            title="Add videos to library (O)"
          >
            + Add videos
          </button>
        </div>

        {/* Tab Bar: Recents, Library, Debug (only when debug clips exist) */}
        <div className="library-tabs">
          <button
            className={`lib-tab ${activeTab === 'recents' ? 'active' : ''}`}
            onClick={() => setActiveTab('recents')}
          >
            Recents
          </button>
          <button
            className={`lib-tab ${activeTab === 'library' ? 'active' : ''}`}
            onClick={() => setActiveTab('library')}
          >
            Library ({libraryClips.length})
          </button>
          {hasDebugClips && (
            <button
              className={`lib-tab ${activeTab === 'debug' ? 'active' : ''}`}
              onClick={() => setActiveTab('debug')}
            >
              Debug
            </button>
          )}
        </div>

        {/* Filters */}
        <div className="clip-filters">
          <input
            type="text"
            className="search-input"
            placeholder="Search name or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="filter-select-row">
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
            {activeTab === 'debug' && (
              <select
                className="filter-select sort-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                title="Sort clips list"
              >
                <option value="default">Default order</option>
                <option value="system_residual">By residual</option>
              </select>
            )}
          </div>
        </div>
      </div>

      {/* Clip List or Empty State */}
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

        {!loadingClips && !error && isEmptyLibrary && (
          <div className="empty-library-container">
            <button className="btn-choose-videos" onClick={() => fileInputRef.current?.click()}>
              📁 Choose video files
            </button>
            <p className="empty-library-desc">
              Videos are copied to <code>{libraryFolder || '<library folder>'}</code> (outside the repo)
            </p>
          </div>
        )}

        {!loadingClips && !error && !isEmptyLibrary && displayClips.length === 0 && (
          <div className="empty-message">No matching deliveries</div>
        )}

        {!loadingClips &&
          !error &&
          !isEmptyLibrary &&
          displayClips.map((clip) => {
            const isSelected = clip.clip_id === selectedClipId;
            const hasGt =
              clip.has_gt_calibration ||
              (clip.clip_id === selectedClipId && Boolean(currentLabel?.calibration_gt));
            const displayName = clip.display_name || clip.clip_id;
            const timeStr = timeAgo(clip.last_opened_at || clip.added_at);
            const isLibraryClip = clip.pool !== 'debug';

            return (
              <div
                key={clip.clip_id}
                className={`clip-item ${isSelected ? 'selected' : ''}`}
                onClick={() => void selectClip(clip.clip_id)}
                title={displayName}
              >
                <div className="clip-row-main">
                  <span className="clip-title truncate" title={displayName}>
                    {displayName}
                  </span>
                  <div className="clip-badges-right">
                    {hasGt && (
                      <span className="calib-badge" title="Has ground-truth calibration">
                        C
                      </span>
                    )}
                    {clip.warnings && clip.warnings.length > 0 && (
                      <span
                        className="badge-warning-icon"
                        title={`Warnings: ${clip.warnings.join(', ')}`}
                      >
                        ⚠️
                      </span>
                    )}
                    {clip.frame_count_mismatch && (
                      <span
                        className="badge-warning-icon"
                        title="Frame count mismatch with video metadata!"
                      >
                        ⚠️
                      </span>
                    )}
                    <span className={`status-pill status-${clip.label_status}`}>
                      {clip.label_status}
                    </span>
                    {isLibraryClip && (
                      <button
                        className="btn-hide-clip"
                        onClick={(e) => {
                          e.stopPropagation();
                          void hideClipAction(clip.clip_id);
                        }}
                        title="Hide video from library"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </div>

                <div className="clip-row-sub">
                  <span className="clip-meta-frames">{clip.frame_count}f</span>
                  {timeStr && <span className="clip-time-ago">{timeStr}</span>}
                  {clip.pool === 'debug' && clip.ball_type && (
                    <span className={`ball-badge ball-${clip.ball_type}`}>
                      {clip.ball_type}
                    </span>
                  )}
                  {clip.system_residual_px != null && (
                    <span className="clip-residual-tag" title="System stump residual">
                      {clip.system_residual_px.toFixed(1)} px
                    </span>
                  )}
                </div>
              </div>
            );
          })}

        {activeTab === 'recents' && (hasMoreRecents || (showAllRecents && totalRecentsCount > 20)) && (
          <div className="recents-toggle-row">
            <button
              className="btn-toggle-recents"
              onClick={() => setShowAllRecents(!showAllRecents)}
            >
              {showAllRecents ? 'Show less' : `Show all (${totalRecentsCount})`}
            </button>
          </div>
        )}
      </div>

      {/* Upload Progress & Results Modal */}
      {uploadState.showResultsModal && (
        <div className="upload-modal-container">
          <div className="upload-modal-header">
            <h4 className="upload-modal-title">
              {uploadState.uploading
                ? `Uploading (${uploadState.currentIdx}/${uploadState.total})...`
                : 'Upload Complete'}
            </h4>
            {!uploadState.uploading && (
              <button className="upload-modal-close" onClick={dismissUploadModal}>
                ✕
              </button>
            )}
          </div>

          {uploadState.uploading && (
            <div className="upload-progress-box">
              <div className="progress-bar-bg">
                <div
                  className="progress-bar-fill"
                  style={{ width: `${uploadState.progressPct}%` }}
                />
              </div>
              <span className="progress-text">
                {uploadState.currentFile} ({uploadState.progressPct}%)
              </span>
            </div>
          )}

          <div className="upload-results-list">
            {uploadState.results.map((r, i) => (
              <div key={i} className={`upload-res-item upload-res-${r.status}`}>
                <span className="res-icon">
                  {r.status === 'added' ? '✅' : r.status === 'duplicate' ? 'ℹ️' : '❌'}
                </span>
                <span className="res-filename truncate" title={r.name}>
                  {r.name}
                </span>
                <span className="res-msg">{r.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer showing Library Folder path */}
      <div className="clip-list-footer">
        <div className="library-path-row" title={libraryFolder}>
          <span className="library-path-label">Library:</span>
          <span className="library-path-val truncate">{libraryFolder || '...'}</span>
        </div>
        <span className="hint-text">
          Use <kbd>[</kbd> and <kbd>]</kbd> to switch • Press <kbd>O</kbd> to add
        </span>
      </div>
    </aside>
  );
};
