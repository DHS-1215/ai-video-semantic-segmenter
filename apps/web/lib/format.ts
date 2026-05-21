export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "\u672a\u77e5";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "\u672a\u77e5";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "\u672a\u77e5";
  }

  const totalSeconds = Math.max(0, Math.round(value));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  return `${minutes.toString().padStart(2, "0")}:${seconds
    .toString()
    .padStart(2, "0")}`;
}
