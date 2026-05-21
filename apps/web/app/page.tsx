"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiClientError, uploadVideo } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleUpload() {
    if (!selectedFile) {
      setErrorMessage(
        "\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u89c6\u9891\u6587\u4ef6\u3002",
      );
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);

    try {
      const result = await uploadVideo(selectedFile);
      router.push(`/videos/${result.video_id}`);
    } catch (error) {
      if (error instanceof ApiClientError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage(
          "\u4e0a\u4f20\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002",
        );
      }
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="page-panel hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">MVP Frontend</p>
          <h1>AI {"\u89c6\u9891\u8bed\u4e49\u5206\u6bb5\u7cfb\u7edf"}</h1>
          <p className="lead">
            {
              "\u4e0a\u4f20\u957f\u89c6\u9891\u540e\uff0c\u7cfb\u7edf\u4f1a\u7406\u89e3\u89c6\u9891\u4e2d\u7684\u8bf4\u8bdd\u5185\u5bb9\uff0c\u5e76\u6309\u5b8c\u6574\u8bdd\u9898\u62c6\u5206\u4e3a\u8bed\u4e49\u7247\u6bb5\u3002"
            }
          </p>
          <p className="supporting-text">
            {
              "\u5f53\u524d\u524d\u7aef\u63a5\u5165\u7684\u662f mock pipeline\uff0c\u7528\u4e8e\u6f14\u793a\u4e2d\u6587\u54c1\u724c\u90e8\u573a\u666f\u4e0b\u7684\u4e0a\u4f20\u3001\u8f6c\u5199\u3001\u8bed\u4e49\u5206\u6bb5\u4e0e\u7ed3\u679c\u67e5\u8be2\u95ed\u73af\u3002"
            }
          </p>
          <p className="supporting-text hero-note">
            {
              "\u5f53\u524d\u7248\u672c\u4f7f\u7528 Mock Pipeline \u751f\u6210\u4e2d\u6587\u6a21\u62df\u8f6c\u5199\u548c\u8bed\u4e49\u5206\u6bb5\uff0c\u7528\u4e8e\u9a8c\u8bc1\u4ea7\u54c1\u6d41\u7a0b\uff1b\u771f\u5b9e ASR \u548c LLM \u4f1a\u5728\u540e\u7eed\u9636\u6bb5\u63a5\u5165\u3002"
            }
          </p>
        </div>

        <div className="page-card upload-card">
          <label className="field-label" htmlFor="video-upload">
            {"\u9009\u62e9\u89c6\u9891\u6587\u4ef6"}
          </label>
          <input
            id="video-upload"
            className="file-input"
            type="file"
            accept=".mp4,.mov,.webm,.mkv,video/mp4,video/quicktime,video/webm,video/x-matroska"
            onChange={(event) => {
              setSelectedFile(event.target.files?.[0] ?? null);
              setErrorMessage(null);
            }}
          />
          <p className="field-hint">
            {
              "\u652f\u6301 mp4\u3001mov\u3001webm\u3001mkv\u3002\u4e0a\u4f20\u6210\u529f\u540e\u4f1a\u81ea\u52a8\u8df3\u8f6c\u5230\u89c6\u9891\u8be6\u60c5\u9875\u3002"
            }
          </p>

          {selectedFile ? (
            <div className="inline-note">
              {"\u5df2\u9009\u62e9\uff1a"}
              <strong>{selectedFile.name}</strong>
            </div>
          ) : null}

          {errorMessage ? <p className="error-banner">{errorMessage}</p> : null}

          <div className="button-row">
            <button
              className="primary-button"
              disabled={isUploading || !selectedFile}
              onClick={handleUpload}
              type="button"
            >
              {isUploading
                ? "\u4e0a\u4f20\u4e2d..."
                : "\u4e0a\u4f20\u89c6\u9891"}
            </button>
            <Link className="secondary-link" href="/videos">
              {"\u67e5\u770b\u89c6\u9891\u5217\u8868"}
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
