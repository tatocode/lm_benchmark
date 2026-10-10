"use client";

import * as React from "react";
import { Check, ImagePlus, Loader2, Trash2, Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { assetUrl, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { ImageMeta } from "@/lib/types";

interface ImagePickerProps {
  value: string;
  onChange: (imageId: string) => void;
  className?: string;
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function ImagePicker({ value, onChange, className }: ImagePickerProps) {
  const { t } = useI18n();
  const [images, setImages] = React.useState<ImageMeta[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.listImages();
      setImages(list);
      return list;
    } catch (e) {
      setError(String(e));
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  // 视觉测试必须有且仅有一张被选中的图片：加载完成或所选图片失效时自动回退。
  React.useEffect(() => {
    if (loading || !images.length) return;
    if (images.some((i) => i.id === value)) return;
    const fallback = images.find((i) => i.source === "builtin") ?? images[0];
    onChange(fallback.id);
  }, [images, loading, value, onChange]);

  const selected = images.find((i) => i.id === value);
  const builtins = images.filter((i) => i.source === "builtin");
  const uploads = images.filter((i) => i.source === "upload");

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setError("");
    if (!file.type.startsWith("image/")) {
      setError(t("image.errType"));
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setError(t("image.errSize"));
      return;
    }
    setUploading(true);
    try {
      const dataUrl = await fileToDataUrl(file);
      const semi = dataUrl.indexOf(";");
      const comma = dataUrl.indexOf(",");
      const mime = dataUrl.slice(5, semi) || "image/jpeg";
      const base64 = dataUrl.slice(comma + 1);
      const img = await api.uploadImage(file.name, mime, base64);
      await refresh();
      onChange(img.id);
    } catch (e) {
      setError(String(e));
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const removeImage = async (id: string) => {
    setError("");
    try {
      await api.deleteImage(id);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  const renderTile = (img: ImageMeta) => {
    const on = img.id === value;
    return (
      <div key={img.id} className="group relative">
        <button
          type="button"
          onClick={() => onChange(img.id)}
          className={cn(
            "block w-full cursor-pointer overflow-hidden rounded-lg border transition-all",
            on
              ? "border-primary ring-2 ring-primary"
              : "hover:border-primary/50 hover:shadow-sm",
          )}
        >
          <span className="relative block aspect-[4/3] bg-muted">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={assetUrl(img.url)}
              alt={img.name}
              loading="lazy"
              className="h-full w-full object-cover"
            />
            {on ? (
              <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground shadow">
                <Check className="h-3.5 w-3.5" />
              </span>
            ) : null}
          </span>
          <span className="block truncate px-2 py-1 text-left text-[11px]">
            {img.name}
          </span>
        </button>
        {img.source === "upload" ? (
          <button
            type="button"
            title={t("image.delete")}
            onClick={() => void removeImage(img.id)}
            className="absolute right-1.5 top-1.5 hidden h-5 w-5 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow group-hover:flex"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        ) : null}
      </div>
    );
  };

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-sm font-medium">
          <ImagePlus className="h-4 w-4 text-muted-foreground" />
          {t("image.title")}
          <Badge variant="secondary" className="font-normal">
            {t("image.count", { n: images.length })}
          </Badge>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? <Loader2 className="animate-spin" /> : <Upload />}
          {uploading ? t("image.uploading") : t("image.upload")}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => void onFile(e.target.files?.[0])}
        />
      </div>

      {error ? <p className="text-xs text-destructive">{error}</p> : null}

      <div className="grid gap-3 sm:grid-cols-[1.1fr_2fr]">
        <div className="space-y-1.5">
          <div className="flex aspect-[4/3] items-center justify-center overflow-hidden rounded-lg border bg-muted/40">
            {selected ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={assetUrl(selected.url)}
                alt={selected.name}
                className="h-full w-full object-contain"
              />
            ) : loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : (
              <span className="text-xs text-muted-foreground">{t("image.none")}</span>
            )}
          </div>
          <div className="text-xs">
            <div className="font-medium">{selected?.name ?? "—"}</div>
            {selected?.credit ? (
              <div className="truncate text-muted-foreground">{selected.credit}</div>
            ) : null}
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <div className="mb-1.5 text-xs font-medium text-muted-foreground">
              {t("image.builtin")}
            </div>
            <div className="grid grid-cols-3 gap-2">
              {builtins.map(renderTile)}
            </div>
          </div>
          {uploads.length ? (
            <div>
              <div className="mb-1.5 text-xs font-medium text-muted-foreground">
                {t("image.mine")}
              </div>
              <div className="grid grid-cols-3 gap-2">{uploads.map(renderTile)}</div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
