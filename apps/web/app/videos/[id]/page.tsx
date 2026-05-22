"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiClientError,
  extractAudio,
  generateSemanticSegments,
  getJobs,
  getSegments,
  getTranscript,
  getVideo,
  runMockPipeline,
  transcribeAudio,
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
  const [isExtractingAudio, setIsExtractingAudio] = useState(false);
  const [isTranscribingAudio, setIsTranscribingAudio] = useState(false);
  const [isGeneratingSemanticSegments, setIsGeneratingSemanticSegments] =
    useState(false);
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
        setErrorMessage("\u52a0\u8f7d\u89c6\u9891\u8be6\u60c5\u5931\u8d25\u3002");
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
        setErrorMessage("\u8fd0\u884c Mock Pipeline \u5931\u8d25\u3002");
      }
    } finally {
      setIsRunningPipeline(false);
    }
  }

  async function handleExtractAudio() {
    if (!videoId) {
      return;
    }

    setIsExtractingAudio(true);
    setActionMessage(null);
    setErrorMessage(null);

    try {
      const result = await extractAudio(videoId);
      setActionMessage(
        `\u97f3\u9891\u63d0\u53d6\u5b8c\u6210\uff1a\u5df2\u751f\u6210 audio.wav\uff0c\u65f6\u957f ${formatSeconds(result.duration_seconds)}\u3002`,
      );
      await loadVideoData({ preserveData: true });
    } catch (error) {
      if (error instanceof ApiClientError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("\u63d0\u53d6\u97f3\u9891\u5931\u8d25\u3002");
      }
    } finally {
      setIsExtractingAudio(false);
    }
  }

  async function handleTranscribeAudio() {
    if (!videoId) {
      return;
    }

    if (
      transcript.length > 0 &&
      !window.confirm(
        "\u91cd\u65b0\u751f\u6210\u4f1a\u8986\u76d6\u5f53\u524d\u8f6c\u5199\u6587\u672c\uff0c\u662f\u5426\u7ee7\u7eed\uff1f",
      )
    ) {
      return;
    }

    setIsTranscribingAudio(true);
    setActionMessage(null);
    setErrorMessage(null);

    try {
      const result = await transcribeAudio(videoId);
      setActionMessage(
        `\u8f6c\u5199\u5df2\u5b8c\u6210\uff1a\u751f\u6210 ${result.transcript_segments_created} \u6761\u8f6c\u5199\u6587\u672c\u3002`,
      );
      await loadVideoData({ preserveData: true });
    } catch (error) {
      if (error instanceof ApiClientError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("\u751f\u6210\u8f6c\u5199\u5931\u8d25\u3002");
      }
    } finally {
      setIsTranscribingAudio(false);
    }
  }

  async function handleGenerateSemanticSegments() {
    if (!videoId) {
      return;
    }

    if (
      segments.length > 0 &&
      !window.confirm(
        "\u91cd\u65b0\u751f\u6210\u4f1a\u8986\u76d6\u5f53\u524d\u8bed\u4e49\u5206\u6bb5\u7ed3\u679c\uff0c\u662f\u5426\u7ee7\u7eed\uff1f",
      )
    ) {
      return;
    }

    setIsGeneratingSemanticSegments(true);
    setActionMessage(null);
    setErrorMessage(null);

    try {
      const result = await generateSemanticSegments(videoId);
      setActionMessage(
        `\u8bed\u4e49\u5206\u6bb5\u5df2\u5b8c\u6210\uff1a\u751f\u6210 ${result.semantic_segments_created} \u4e2a\u8bed\u4e49\u5206\u6bb5\u3002`,
      );
      setExpandedSegmentIds({});
      await loadVideoData({ preserveData: true });
    } catch (error) {
      if (error instanceof ApiClientError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("\u751f\u6210\u8bed\u4e49\u5206\u6bb5\u5931\u8d25\u3002");
      }
    } finally {
      setIsGeneratingSemanticSegments(false);
    }
  }

  function getJobTypeLabel(job: ProcessingJob): string {
    if (job.job_type === "extract_audio") {
      return "\u63d0\u53d6\u97f3\u9891";
    }

    if (job.job_type === "transcribe_audio") {
      return "\u751f\u6210\u8f6c\u5199";
    }

    if (job.job_type === "semantic_segment") {
      return "\u751f\u6210\u8bed\u4e49\u5206\u6bb5";
    }

    return job.job_type;
  }

  function getJobStatusLabel(job: ProcessingJob): string {
    if (job.job_type === "extract_audio") {
      if (job.status === "completed") {
        return "\u97f3\u9891\u63d0\u53d6\u5b8c\u6210";
      }

      if (job.status === "failed") {
        return "\u97f3\u9891\u63d0\u53d6\u5931\u8d25";
      }

      if (job.status === "running") {
        return "\u97f3\u9891\u63d0\u53d6\u4e2d";
      }

      return job.status;
    }

    if (job.job_type === "transcribe_audio") {
      if (job.status === "completed") {
        return "\u8f6c\u5199\u5b8c\u6210";
      }

      if (job.status === "failed") {
        return "\u8f6c\u5199\u5931\u8d25";
      }

      if (job.status === "running") {
        return "\u8f6c\u5199\u4e2d";
      }

      if (job.status === "pending") {
        return "\u7b49\u5f85\u8f6c\u5199";
      }
    }

    if (job.job_type === "semantic_segment") {
      if (job.status === "completed") {
        return "\u8bed\u4e49\u5206\u6bb5\u5b8c\u6210";
      }

      if (job.status === "failed") {
        return "\u8bed\u4e49\u5206\u6bb5\u5931\u8d25";
      }

      if (job.status === "running") {
        return "\u8bed\u4e49\u5206\u6bb5\u4e2d";
      }

      if (job.status === "pending") {
        return "\u7b49\u5f85\u8bed\u4e49\u5206\u6bb5";
      }
    }

    return job.status;
  }

  const { video, transcript, segments, jobs } = detailState;
  const hasTranscript = transcript.length > 0;
  const hasSegments = segments.length > 0;
  const hasExistingResults = hasTranscript || hasSegments;
  const shouldShowGenerationGuide = !hasTranscript && !hasSegments;
  const canExtractAudio = Boolean(video?.original_object_name);
  const canTranscribeAudio = Boolean(video?.audio_object_name);
  const canGenerateSemanticSegments = transcript.length > 0;
  const hasExtractedAudio = Boolean(video?.audio_object_name);
  const pipelineButtonLabel = hasExistingResults
    ? "\u91cd\u65b0\u8fd0\u884c Mock Pipeline"
    : "\u8fd0\u884c Mock Pipeline";
  const transcriptionButtonLabel = hasTranscript
    ? "\u91cd\u65b0\u751f\u6210\u8f6c\u5199"
    : "\u751f\u6210\u8f6c\u5199";
  const semanticSegmentationButtonLabel = hasSegments
    ? "\u91cd\u65b0\u751f\u6210\u8bed\u4e49\u5206\u6bb5"
    : "\u751f\u6210\u8bed\u4e49\u5206\u6bb5";

  const steps: StepItem[] = [
    {
      label: "\u89c6\u9891\u5df2\u4e0a\u4f20",
      completed: Boolean(video),
    },
    {
      label: "\u97f3\u9891\u5df2\u63d0\u53d6",
      completed: hasExtractedAudio,
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
                <div className="detail-actions">
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
                  <button
                    className="secondary-button"
                    disabled={!canExtractAudio || isExtractingAudio}
                    onClick={handleExtractAudio}
                    type="button"
                  >
                    {isExtractingAudio
                      ? "\u63d0\u53d6\u4e2d..."
                      : "\u63d0\u53d6\u97f3\u9891"}
                  </button>
                  <button
                    className="secondary-button"
                    disabled={!canTranscribeAudio || isTranscribingAudio}
                    onClick={handleTranscribeAudio}
                    type="button"
                  >
                    {isTranscribingAudio
                      ? "\u751f\u6210\u8f6c\u5199\u4e2d..."
                      : transcriptionButtonLabel}
                  </button>
                  <button
                    className="secondary-button"
                    disabled={
                      !canGenerateSemanticSegments || isGeneratingSemanticSegments
                    }
                    onClick={handleGenerateSemanticSegments}
                    type="button"
                  >
                    {isGeneratingSemanticSegments
                      ? "\u751f\u6210\u8bed\u4e49\u5206\u6bb5\u4e2d..."
                      : semanticSegmentationButtonLabel}
                  </button>
                  {!canExtractAudio ? (
                    <p className="detail-action-hint">
                      {
                        "\u5386\u53f2\u4e0a\u4f20\u8bb0\u5f55\u7f3a\u5c11 original_object_name\uff0c\u8bf7\u91cd\u65b0\u4e0a\u4f20\u89c6\u9891\u3002"
                      }
                    </p>
                  ) : null}
                  {!canTranscribeAudio ? (
                    <p className="detail-action-hint">
                      {"\u8bf7\u5148\u63d0\u53d6\u97f3\u9891\u3002"}
                    </p>
                  ) : null}
                  {!canGenerateSemanticSegments ? (
                    <p className="detail-action-hint">
                      {"\u8bf7\u5148\u751f\u6210\u8f6c\u5199\u3002"}
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="stats-grid">
                <div className="stat-card">
                  <span className="stat-label">{"\u72b6\u6001"}</span>
                  <span className={`status-pill status-${video.status}`}>
                    {video.status}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">{"\u521b\u5efa\u65f6\u95f4"}</span>
                  <span>{formatDateTime(video.created_at)}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">{"\u65f6\u957f"}</span>
                  <span>{formatSeconds(video.duration_seconds)}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">{"\u539f\u59cb\u5730\u5740"}</span>
                  <span className="truncate-text">{video.original_url}</span>
                </div>
              </div>

              <div className="metadata-grid">
                <div className="stat-card">
                  <span className="stat-label">original_object_name</span>
                  <span className="truncate-text">
                    {video.original_object_name ??
                      "\u5386\u53f2\u4e0a\u4f20\u8bb0\u5f55\u7f3a\u5c11 original_object_name"}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">audio_url</span>
                  <span className="truncate-text">
                    {video.audio_url ?? "\u5c1a\u672a\u63d0\u53d6\u97f3\u9891"}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">audio_object_name</span>
                  <span className="truncate-text">
                    {video.audio_object_name ?? "\u5c1a\u672a\u63d0\u53d6\u97f3\u9891"}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-label">duration_seconds</span>
                  <span>
                    {hasExtractedAudio
                      ? formatSeconds(video.duration_seconds)
                      : "\u5c1a\u672a\u63d0\u53d6\u97f3\u9891"}
                  </span>
                </div>
              </div>
            </div>

            {shouldShowGenerationGuide ? (
              <div className="empty-state guide-card">
                {
                  "\u5f53\u524d\u89c6\u9891\u8fd8\u6ca1\u6709\u751f\u6210\u8f6c\u5199\u548c\u8bed\u4e49\u5206\u6bb5\u3002\u53ef\u4ee5\u5148\u63d0\u53d6\u97f3\u9891\u518d\u751f\u6210\u8f6c\u5199\uff0c\u4e5f\u53ef\u4ee5\u76f4\u63a5\u8fd0\u884c Mock Pipeline \u9a8c\u8bc1\u6f14\u793a\u6d41\u7a0b\u3002"
                }
              </div>
            ) : null}

            <section className="content-section">
              <div className="section-subheading">
                <h2 className="card-title">{"\u5904\u7406\u4efb\u52a1"}</h2>
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
                          <strong>{getJobTypeLabel(job)}</strong>
                          <p className="muted-row">{formatDateTime(job.created_at)}</p>
                        </div>
                        <span className={`status-pill status-${job.status}`}>
                          {getJobStatusLabel(job)}
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
                <h2 className="card-title">{"\u8f6c\u5199\u6587\u672c"}</h2>
                <span className="section-count">
                  {transcript.length} {"\u6761"}
                </span>
              </div>
              {transcript.length === 0 ? (
                <div className="empty-state">
                  {
                    "\u8fd8\u6ca1\u6709\u8f6c\u5199\u7ed3\u679c\uff0c\u53ef\u4ee5\u5148\u63d0\u53d6\u97f3\u9891\u5e76\u751f\u6210\u8f6c\u5199\uff0c\u6216\u8005\u8fd0\u884c Mock Pipeline\u3002"
                  }
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
                <h2 className="card-title">{"\u8bed\u4e49\u5206\u6bb5"}</h2>
                <span className="section-count">
                  {segments.length} {"\u4e2a"}
                </span>
              </div>
              {segments.length === 0 ? (
                <div className="empty-state">
                  {
                    "\u8fd8\u6ca1\u6709\u8bed\u4e49\u5206\u6bb5\u7ed3\u679c\uff0c\u53ef\u4ee5\u5148\u751f\u6210\u8f6c\u5199\u518d\u8fd0\u884c\u8bed\u4e49\u5206\u6bb5\uff0c\u6216\u8005\u76f4\u63a5\u8fd0\u884c Mock Pipeline\u3002"
                  }
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
