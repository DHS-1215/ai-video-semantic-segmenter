"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiClientError,
  getJobs,
  getSegments,
  getTranscript,
  getVideo,
  runMockPipeline,
  type ProcessingJob,
  type SemanticSegment,
  type TranscriptSegment,
  type Video,
} from "@/lib/api";
import { formatDateTime, formatSeconds } from "@/lib/format";

type VideoDetailState = {
  video: Video | null;
  transcript: TranscriptSegment[];
  segments: SemanticSegment[];
  jobs: ProcessingJob[];
};

const initialState: VideoDetailState = {
  video: null,
  transcript: [],
  segments: [],
  jobs: [],
};

type StepItem = {
  label: string;
  completed: boolean;
};

export default function VideoDetailPage() {
  const params = useParams<{ id: string }>();
  const videoId = typeof params.id === "string" ? params.id : "";

  const [detailState, setDetailState] = useState<VideoDetailState>(initialState);
  const [expandedSegmentIds, setExpandedSegmentIds] = useState<
    Record<string, boolean>
  >({});
  const [isLoading, setIsLoading] = useState(true);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  async function loadVideoData(options?: { preserveData?: boolean }) {
    if (!videoId) {
      setErrorMessage("\u65e0\u6548\u7684\u89c6\u9891 ID\u3002");
      setIsLoading(false);
      return;
    }

    if (!options?.preserveData) {
      setIsLoading(true);
    }

    try {
      const [video, transcript, segments, jobs] = await Promise.all([
        getVideo(videoId),
        getTranscript(videoId),
        getSegments(videoId),
        getJobs(videoId),
      ]);
      setDetailState({ video, transcript, segments, jobs });
      setErrorMessage(null);
    } catch (error) {
      if (error instanceof ApiClientError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(
          "\u52a0\u8f7d\u89c6\u9891\u8be6\u60c5\u5931\u8d25\u3002",
        );
      }
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadVideoData();
  }, [videoId]);

  function toggleTranscriptText(segmentId: string) {
    setExpandedSegmentIds((current) => ({
      ...current,
      [segmentId]: !current[segmentId],
    }));
  }

  async function handleRunMockPipeline() {
    if (!videoId) {
      return;
    }

    const hasExistingResults =
      detailState.transcript.length > 0 || detailState.segments.length > 0;

    if (
      hasExistingResults &&
      !window.confirm(
        "\u91cd\u65b0\u8fd0\u884c\u4f1a\u8986\u76d6\u5f53\u524d mock \u8f6c\u5199\u548c\u8bed\u4e49\u5206\u6bb5\u7ed3\u679c\uff0c\u662f\u5426\u7ee7\u7eed\uff1f",
      )
    ) {
      return;
    }

    setIsRunningPipeline(true);
    setActionMessage(null);
    setErrorMessage(null);

    try {
      const result = await runMockPipeline(videoId);
      setActionMessage(
        `Mock pipeline \u5df2\u5b8c\u6210\uff1a\u751f\u6210 ${result.transcript_segments_created} \u6761\u8f6c\u5199\uff0c${result.semantic_segments_created} \u4e2a\u8bed\u4e49\u5206\u6bb5\u3002`,
      );
      setExpandedSegmentIds({});
      await loadVideoData({ preserveData: true });
    } catch (error) {
      if (error instanceof ApiClientError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(
          "\u8fd0\u884c Mock Pipeline \u5931\u8d25\u3002",
        );
      }
    } finally {
      setIsRunningPipeline(false);
    }
  }

  const { video, transcript, segments, jobs } = detailState;
  const hasTranscript = transcript.length > 0;
  const hasSegments = segments.length > 0;
  const hasExistingResults = hasTranscript || hasSegments;
  const shouldShowGenerationGuide = !hasTranscript && !hasSegments;
  const pipelineButtonLabel = hasExistingResults
    ? "\u91cd\u65b0\u8fd0\u884c Mock Pipeline"
    : "\u8fd0\u884c Mock Pipeline";

  const steps: StepItem[] = [
    {
      label: "\u89c6\u9891\u5df2\u4e0a\u4f20",
      completed: Boolean(video),
    },
    {
      label: "\u8f6c\u5199\u6587\u672c\u5df2\u751f\u6210",
      completed: hasTranscript,
    },
    {
      label: "\u8bed\u4e49\u5206\u6bb5\u5df2\u751f\u6210",
      completed: hasSegments,
    },
  ];

  return (
    <main className="app-shell">
      <section className="page-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Video Detail</p>
            <h1 className="section-title">{"\u89c6\u9891\u8be6\u60c5"}</h1>
            <p className="supporting-text">
              {
                "\u67e5\u770b\u4e0a\u4f20\u72b6\u6001\u3001\u5904\u7406\u4efb\u52a1\u3001\u8f6c\u5199\u5185\u5bb9\u548c\u8bed\u4e49\u5206\u6bb5\u7ed3\u679c\u3002"
              }
            </p>
          </div>
          <div className="button-row">
            <Link className="secondary-link" href="/videos">
              {"\u8fd4\u56de\u89c6\u9891\u5217\u8868"}
            </Link>
            <Link className="secondary-link" href="/">
              {"\u8fd4\u56de\u4e0a\u4f20\u9875"}
            </Link>
          </div>
        </div>

        {isLoading ? (
          <div className="empty-state">
            {"\u6b63\u5728\u52a0\u8f7d\u89c6\u9891\u8be6\u60c5..."}
          </div>
        ) : null}

        {!isLoading && errorMessage ? (
          <p className="error-banner">{errorMessage}</p>
        ) : null}

        {!isLoading && video ? (
          <>
            {actionMessage ? <p className="success-banner">{actionMessage}</p> : null}

            <div className="page-card detail-card">
              <div className="detail-header">
                <div>
                  <h2 className="card-title">{video.filename}</h2>
                  <p className="supporting-text">
                    {
                      "\u5f53\u524d\u9636\u6bb5\u5c55\u793a\u7684\u662f mock pipeline \u751f\u6210\u7684\u4e2d\u6587\u6a21\u62df\u6570\u636e\u3002"
                    }
                  </p>
                  <div className="step-flow" aria-label="pipeline-progress">
                    {steps.map((step, index) => (
                      <div className="step-fragment" key={step.label}>
                        <span
                          className={`step-item ${
                            step.completed ? "step-complete" : "step-pending"
                          }`}
                        >
                          <span className="step-icon">
                            {step.completed ? "\u2713" : "\u2022"}
                          </span>
                          <span>{step.label}</span>
                        </span>
                        {index < steps.length - 1 ? (
                          <span className="step-arrow" aria-hidden="true">
                            {"\u2192"}
                          </span>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
                <button
                  className="primary-button"
                  disabled={isRunningPipeline}
                  onClick={handleRunMockPipeline}
                  type="button"
                >
                  {isRunningPipeline
                    ? "\u8fd0\u884c\u4e2d..."
                    : pipelineButtonLabel}
                </button>
              </div>

              <div className="stats-grid">
                <div className="stat-card">
                  <span className="stat-label">\u72b6\u6001</span>
                  <span className={`status-pill status-${video.status}`}>
                    {video.status}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">\u521b\u5efa\u65f6\u95f4</span>
                  <span>{formatDateTime(video.created_at)}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">\u65f6\u957f</span>
                  <span>{formatSeconds(video.duration_seconds)}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">\u539f\u59cb\u5730\u5740</span>
                  <span className="truncate-text">{video.original_url}</span>
                </div>
              </div>
            </div>

            {shouldShowGenerationGuide ? (
              <div className="empty-state guide-card">
                {
                  "\u5f53\u524d\u89c6\u9891\u8fd8\u6ca1\u6709\u751f\u6210\u8f6c\u5199\u548c\u8bed\u4e49\u5206\u6bb5\u3002\u70b9\u51fb\u201c\u8fd0\u884c Mock Pipeline\u201d\u751f\u6210\u4e2d\u6587\u6a21\u62df\u7ed3\u679c\uff0c\u7528\u4e8e\u9a8c\u8bc1\u4ea7\u54c1\u6d41\u7a0b\u3002"
                }
              </div>
            ) : null}

            <section className="content-section">
              <div className="section-subheading">
                <h2 className="card-title">\u5904\u7406\u4efb\u52a1</h2>
                <span className="section-count">{jobs.length} {"\u6761"}</span>
              </div>
              {jobs.length === 0 ? (
                <div className="empty-state">
                  {"\u5f53\u524d\u6ca1\u6709\u5904\u7406\u4efb\u52a1\u3002"}
                </div>
              ) : (
                <div className="stack-list">
                  {jobs.map((job) => (
                    <article className="page-card compact-card" key={job.id}>
                      <div className="job-row">
                        <div>
                          <strong>{job.job_type}</strong>
                          <p className="muted-row">{formatDateTime(job.created_at)}</p>
                        </div>
                        <span className={`status-pill status-${job.status}`}>
                          {job.status}
                        </span>
                      </div>
                      {job.error_message ? (
                        <p className="error-inline">{job.error_message}</p>
                      ) : null}
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="content-section">
              <div className="section-subheading">
                <h2 className="card-title">\u8f6c\u5199\u6587\u672c</h2>
                <span className="section-count">
                  {transcript.length} {"\u6761"}
                </span>
              </div>
              {transcript.length === 0 ? (
                <div className="empty-state">
                  {"\u8fd8\u6ca1\u6709\u8f6c\u5199\u7ed3\u679c\uff0c\u5148\u8fd0\u884c Mock Pipeline\u3002"}
                </div>
              ) : (
                <div className="stack-list">
                  {transcript.map((segment) => (
                    <article className="page-card compact-card" key={segment.id}>
                      <div className="transcript-meta">
                        <span className="time-chip">
                          {formatSeconds(segment.start_time)} -{" "}
                          {formatSeconds(segment.end_time)}
                        </span>
                        <span className="muted-row">
                          {segment.speaker ?? "\u672a\u6807\u6ce8\u8bf4\u8bdd\u4eba"}
                        </span>
                      </div>
                      <p className="body-text">{segment.text}</p>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="content-section">
              <div className="section-subheading">
                <h2 className="card-title">\u8bed\u4e49\u5206\u6bb5</h2>
                <span className="section-count">
                  {segments.length} {"\u4e2a"}
                </span>
              </div>
              {segments.length === 0 ? (
                <div className="empty-state">
                  {"\u8fd8\u6ca1\u6709\u8bed\u4e49\u5206\u6bb5\u7ed3\u679c\uff0c\u5148\u8fd0\u884c Mock Pipeline\u3002"}
                </div>
              ) : (
                <div className="segment-grid">
                  {segments.map((segment) => {
                    const isExpanded = Boolean(expandedSegmentIds[segment.id]);

                    return (
                      <article className="page-card segment-card" key={segment.id}>
                        <div className="segment-header">
                          <div>
                            <h3>{segment.title}</h3>
                            <p className="muted-row">
                              {formatSeconds(segment.start_time)} -{" "}
                              {formatSeconds(segment.end_time)}
                            </p>
                          </div>
                          <span className="confidence-badge">
                            {"\u7f6e\u4fe1\u5ea6"} {segment.confidence.toFixed(2)}
                          </span>
                        </div>
                        <dl className="segment-meta">
                          <div>
                            <dt>{"\u4e3b\u9898"}</dt>
                            <dd>{segment.topic}</dd>
                          </div>
                          <div>
                            <dt>{"\u5173\u952e\u8bcd"}</dt>
                            <dd>{segment.keywords.join("\u3001")}</dd>
                          </div>
                          <div>
                            <dt>{"\u6458\u8981"}</dt>
                            <dd>{segment.summary}</dd>
                          </div>
                          <div>
                            <dt>Reason</dt>
                            <dd>{segment.reason}</dd>
                          </div>
                        </dl>
                        <div className="button-row transcript-toggle-row">
                          <button
                            className="secondary-button"
                            onClick={() => toggleTranscriptText(segment.id)}
                            type="button"
                          >
                            {isExpanded
                              ? "\u6536\u8d77\u539f\u6587"
                              : "\u5c55\u5f00\u539f\u6587"}
                          </button>
                        </div>
                        {isExpanded ? (
                          <div className="transcript-block">
                            <strong>{"\u5bf9\u5e94\u539f\u6587"}</strong>
                            <p className="body-text preserve-line-breaks">
                              {segment.transcript_text}
                            </p>
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}
