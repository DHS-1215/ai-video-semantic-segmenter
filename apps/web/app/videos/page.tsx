"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiClientError, listVideos, type Video } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

function getVideoStatusLabel(status: string): string {
  if (status === "completed") {
    return "\u5df2\u5b8c\u6210";
  }

  if (status === "uploaded" || status === "pending") {
    return "\u5f85\u5904\u7406";
  }

  if (status === "failed") {
    return "\u5931\u8d25";
  }

  return status;
}

export default function VideosPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadVideos() {
      try {
        const data = await listVideos();
        if (!isActive) {
          return;
        }
        setVideos(data);
        setErrorMessage(null);
      } catch (error) {
        if (!isActive) {
          return;
        }
        if (error instanceof ApiClientError) {
          setErrorMessage(error.message);
        } else {
          setErrorMessage(
            "\u52a0\u8f7d\u89c6\u9891\u5217\u8868\u5931\u8d25\u3002",
          );
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadVideos();

    return () => {
      isActive = false;
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="page-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Video Library</p>
            <h1 className="section-title">{"\u89c6\u9891\u5217\u8868"}</h1>
            <p className="supporting-text">
              {
                "\u67e5\u770b\u5df2\u4e0a\u4f20\u7684\u89c6\u9891\uff0c\u5e76\u8fdb\u5165\u8be6\u60c5\u9875\u8fd0\u884c mock pipeline \u6216\u68c0\u67e5\u8f6c\u5199\u4e0e\u8bed\u4e49\u5206\u6bb5\u7ed3\u679c\u3002"
              }
            </p>
          </div>
          <Link className="secondary-link" href="/">
            {"\u8fd4\u56de\u4e0a\u4f20\u9875"}
          </Link>
        </div>

        {isLoading ? (
          <div className="empty-state">
            {"\u6b63\u5728\u52a0\u8f7d\u89c6\u9891\u5217\u8868..."}
          </div>
        ) : null}

        {!isLoading && errorMessage ? (
          <p className="error-banner">{errorMessage}</p>
        ) : null}

        {!isLoading && !errorMessage && videos.length === 0 ? (
          <div className="empty-state">
            {
              "\u8fd8\u6ca1\u6709\u89c6\u9891\u3002\u5148\u56de\u5230\u4e0a\u4f20\u9875\u6dfb\u52a0\u4e00\u4e2a\u6f14\u793a\u89c6\u9891\u3002"
            }
          </div>
        ) : null}

        {!isLoading && !errorMessage && videos.length > 0 ? (
          <div className="page-card list-card">
            <div className="table-header table-grid">
              <span>{"\u6587\u4ef6\u540d"}</span>
              <span>{"\u72b6\u6001"}</span>
              <span>{"\u521b\u5efa\u65f6\u95f4"}</span>
              <span>{"\u64cd\u4f5c"}</span>
            </div>
            {videos.map((video) => (
              <div className="table-row table-grid" key={video.id}>
                <span className="table-primary">{video.filename}</span>
                <span>
                  <span className={`status-pill status-${video.status}`}>
                    {getVideoStatusLabel(video.status)}
                  </span>
                </span>
                <span>{formatDateTime(video.created_at)}</span>
                <span>
                  <Link className="inline-link" href={`/videos/${video.id}`}>
                    {"\u67e5\u770b\u8be6\u60c5"}
                  </Link>
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}
