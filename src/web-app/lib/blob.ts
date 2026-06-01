import { BlobServiceClient } from "@azure/storage-blob";
import { DefaultAzureCredential } from "@azure/identity";

import { config } from "./config";
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

export async function downloadServingImage(
  articleId: string,
  imagePath: string,
): Promise<DownloadedBlob | null> {
  const blobPath = safeBlobPath(articleId, imagePath);
  if (!blobPath) {
    return null;
  }

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
    contentType: response.contentType || "application/octet-stream",
    data: new Uint8Array(data),
  };
}