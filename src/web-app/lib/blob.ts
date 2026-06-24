import { BlobServiceClient } from "@azure/storage-blob";
import { DefaultAzureCredential } from "@azure/identity";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";

import { config, isLocalEnvironment } from "./config";
import { DownloadedBlob } from "./types";

let cachedBlobServiceClient: BlobServiceClient | null = null;

function getBlobServiceClient(): BlobServiceClient {
  if (cachedBlobServiceClient) {
    return cachedBlobServiceClient;
  }

  if (config.azuriteConnectionString) {
    cachedBlobServiceClient = BlobServiceClient.fromConnectionString(config.azuriteConnectionString);
    return cachedBlobServiceClient;
  }

  if (!config.servingBlobEndpoint) {
    throw new Error("SERVING_BLOB_ENDPOINT is required to download serving images.");
  }

  cachedBlobServiceClient = new BlobServiceClient(
    config.servingBlobEndpoint.replace(/\/+$/u, ""),
    new DefaultAzureCredential(),
  );
  return cachedBlobServiceClient;
}

function safeBlobPath(articleId: string, imagePath: string): string | null {
  const parts = [articleId, imagePath]
    .join("/")
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length < 2 || parts.some((part) => part === "." || part === "..")) {
    return null;
  }

  return parts.join("/");
}

function getContentType(blobPath: string): string {
  const extension = path.extname(blobPath).toLowerCase();
  switch (extension) {
    case ".png":
      return "image/png";
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".gif":
      return "image/gif";
    case ".svg":
      return "image/svg+xml";
    case ".webp":
      return "image/webp";
    default:
      return "application/octet-stream";
  }
}

async function isRegularFile(candidate: string): Promise<boolean> {
  try {
    return (await stat(candidate)).isFile();
  } catch {
    return false;
  }
}

function localServingRoots(): string[] {
  const candidates = [
    config.localServingRoot,
    "/app/kb/serving",
    path.resolve(process.cwd(), "../../kb/serving"),
    path.resolve(process.cwd(), "kb/serving"),
  ].filter((entry): entry is string => Boolean(entry));

  return [...new Set(candidates.map((entry) => path.resolve(entry)))];
}

async function downloadLocalServingImage(blobPath: string): Promise<DownloadedBlob | null> {
  if (!isLocalEnvironment()) {
    return null;
  }

  for (const root of localServingRoots()) {
    const candidate = path.resolve(root, blobPath);
    const relative = path.relative(root, candidate);
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      continue;
    }

    if (await isRegularFile(candidate)) {
      return {
        contentType: getContentType(candidate),
        data: await readFile(candidate),
      };
    }
  }

  return null;
}

async function downloadServingBlob(blobPath: string): Promise<DownloadedBlob | null> {
  const client = getBlobServiceClient()
    .getContainerClient(config.servingContainerName)
    .getBlobClient(blobPath);

  if (!(await client.exists())) {
    return null;
  }

  const response = await client.download();
  const data = await response.blobBody?.then((blob) => blob.arrayBuffer());
  if (!data) {
    return null;
  }

  return {
    contentType: response.contentType || getContentType(blobPath),
    data: new Uint8Array(data),
  };
}

export async function downloadServingImage(
  articleId: string,
  imagePath: string,
): Promise<DownloadedBlob | null> {
  const blobPath = safeBlobPath(articleId, imagePath);
  if (!blobPath) {
    return null;
  }

  try {
    const blob = await downloadServingBlob(blobPath);
    if (blob) {
      return blob;
    }
  } catch (error) {
    if (!isLocalEnvironment()) {
      throw error;
    }
  }

  return downloadLocalServingImage(blobPath);
}