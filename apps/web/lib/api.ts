export type ApiErrorPayload = {
  code: string;
  message: string;
};

type ApiSuccessResponse<T> = {
  success: true;
  data: T;
};

type ApiFailureResponse = {
  success: false;
  error: ApiErrorPayload;
};

type ApiResponse<T> = ApiSuccessResponse<T> | ApiFailureResponse;

export type VideoListItem = {
  id: string;
  filename: string;
  original_url: string;
  preview_url: string | null;
  duration_seconds: number | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Video = VideoListItem & {
  original_object_name: string | null;
  audio_url: string | null;
  audio_object_name: string | null;
};

export type VideoUploadResult = {
  video_id: string;
  status: string;
  filename: string;
  original_url: string;
};

export type TranscriptSegment = {
  id: string;
  start_time: number;
  end_time: number;
  speaker: string | null;
  text: string;
  sort_order: number;
  created_at: string;
};

export type SemanticSegment = {
  id: string;
  start_time: number;
  end_time: number;
  title: string;
  summary: string;
  topic: string;
  keywords: string[];
  transcript_text: string;
  confidence: number;
  reason: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type ProcessingJob = {
  id: string;
  video_id: string;
  job_type: string;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type MockPipelineResult = {
  video_id: string;
  transcript_segments_created: number;
  semantic_segments_created: number;
  job_status: string;
};

export type AudioExtractionResult = {
  video_id: string;
  job_status: string;
  audio_url: string;
  audio_object_name: string;
  duration_seconds: number;
};

export class ApiClientError extends Error {
  code: string;
  status: number;

  constructor(status: number, error: ApiErrorPayload) {
    super(error.message);
    this.code = error.code;
    this.status = status;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiClientError(0, {
      code: "network_error",
      message:
        "\u65e0\u6cd5\u8fde\u63a5\u540e\u7aef\u670d\u52a1\uff0c\u8bf7\u786e\u8ba4 API \u5df2\u542f\u52a8\u3002",
    });
  }

  let payload: ApiResponse<T>;
  try {
    payload = (await response.json()) as ApiResponse<T>;
  } catch {
    throw new ApiClientError(response.status, {
      code: "invalid_response",
      message:
        "\u540e\u7aef\u8fd4\u56de\u4e86\u65e0\u6cd5\u89e3\u6790\u7684\u54cd\u5e94\u3002",
    });
  }

  if (!response.ok || !payload.success) {
    const error =
      "error" in payload
        ? payload.error
        : {
            code: "unknown_error",
            message: "\u8bf7\u6c42\u5931\u8d25\u3002",
          };
    throw new ApiClientError(response.status, error);
  }

  return payload.data;
}

export async function uploadVideo(file: File): Promise<VideoUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  return request<VideoUploadResult>("/api/videos/upload", {
    method: "POST",
    body: formData,
  });
}

export async function listVideos(): Promise<VideoListItem[]> {
  return request<VideoListItem[]>("/api/videos");
}

export async function getVideo(videoId: string): Promise<Video> {
  return request<Video>(`/api/videos/${videoId}`);
}

export async function getTranscript(
  videoId: string,
): Promise<TranscriptSegment[]> {
  return request<TranscriptSegment[]>(`/api/videos/${videoId}/transcript`);
}

export async function runMockPipeline(
  videoId: string,
): Promise<MockPipelineResult> {
  return request<MockPipelineResult>(
    `/api/videos/${videoId}/jobs/mock-pipeline`,
    {
      method: "POST",
    },
  );
}

export async function extractAudio(
  videoId: string,
): Promise<AudioExtractionResult> {
  return request<AudioExtractionResult>(
    `/api/videos/${videoId}/jobs/extract-audio`,
    {
      method: "POST",
    },
  );
}

export async function getSegments(
  videoId: string,
): Promise<SemanticSegment[]> {
  return request<SemanticSegment[]>(`/api/videos/${videoId}/segments`);
}

export async function getJobs(videoId: string): Promise<ProcessingJob[]> {
  return request<ProcessingJob[]>(`/api/videos/${videoId}/jobs`);
}
