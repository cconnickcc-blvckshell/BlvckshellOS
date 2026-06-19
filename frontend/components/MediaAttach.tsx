"use client";

import { useRef } from "react";
import clsx from "clsx";

export interface ChatAttachment {
  type: "image" | "video" | "document";
  filename: string;
  media_type: string;
  data: string;
  previewUrl?: string;
}

export interface MediaAttachProps {
  attachments: ChatAttachment[];
  onChange: (attachments: ChatAttachment[]) => void;
  className?: string;
}

const ACCEPT = "image/*,video/*,.pdf,.txt,.md,.csv";

function classifyFile(file: File): ChatAttachment["type"] {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  return "document";
}

async function fileToAttachment(file: File): Promise<ChatAttachment> {
  const data = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.includes(",") ? result.split(",")[1] : result;
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  const type = classifyFile(file);
  return {
    type,
    filename: file.name,
    media_type: file.type || "application/octet-stream",
    data,
    previewUrl: type === "image" ? URL.createObjectURL(file) : undefined,
  };
}

export function MediaAttach({ attachments, onChange, className = "" }: MediaAttachProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  async function addFiles(files: FileList | File[]) {
    const list = Array.from(files);
    const next = [...attachments];
    for (const file of list) {
      next.push(await fileToAttachment(file));
    }
    onChange(next);
  }

  function removeAt(index: number) {
    const item = attachments[index];
    if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
    onChange(attachments.filter((_, i) => i !== index));
  }

  return (
    <div className={clsx("flex flex-col gap-2", className)}>
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {attachments.map((a, i) => (
            <span
              key={`${a.filename}-${i}`}
              className="flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 font-mono text-[10px] text-text-secondary"
            >
              {a.type === "image" && a.previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={a.previewUrl} alt="" className="h-5 w-5 rounded object-cover" />
              ) : (
                <span>{a.type === "video" ? "▶" : "📄"}</span>
              )}
              <span className="max-w-[120px] truncate">{a.filename}</span>
              <button
                type="button"
                onClick={() => removeAt(i)}
                className="text-text-secondary hover:text-error"
                aria-label={`Remove ${a.filename}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.length) void addFiles(e.target.files);
          e.target.value = "";
        }}
      />

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border font-mono text-sm text-text-secondary hover:border-primary hover:text-active"
        aria-label="Attach file"
        title="Attach image, video, or document"
      >
        ⌂
      </button>
    </div>
  );
}

export async function filesToAttachments(files: FileList): Promise<ChatAttachment[]> {
  return Promise.all(Array.from(files).map(fileToAttachment));
}
