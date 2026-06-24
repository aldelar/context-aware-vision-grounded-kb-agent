import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const originalEnv = {
  AZURITE_CONNECTION_STRING: process.env.AZURITE_CONNECTION_STRING,
  ENVIRONMENT: process.env.ENVIRONMENT,
  LOCAL_SERVING_ROOT: process.env.LOCAL_SERVING_ROOT,
  SERVING_BLOB_ENDPOINT: process.env.SERVING_BLOB_ENDPOINT,
};

async function loadBlobModule() {
  vi.resetModules();
  return import("../lib/blob");
}

describe("downloadServingImage", () => {
  let tempRoot: string;

  beforeEach(async () => {
    tempRoot = await mkdtemp(path.join(os.tmpdir(), "kb-agent-serving-"));
    process.env.ENVIRONMENT = "dev";
    process.env.LOCAL_SERVING_ROOT = tempRoot;
    process.env.AZURITE_CONNECTION_STRING = "";
    process.env.SERVING_BLOB_ENDPOINT = "";
  });

  afterEach(async () => {
    await rm(tempRoot, { force: true, recursive: true });
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
    vi.resetModules();
  });

  it("falls back to local kb/serving files in dev when blob storage is unavailable", async () => {
    const imagePath = path.join(tempRoot, "article-1", "images", "diagram.png");
    await mkdir(path.dirname(imagePath), { recursive: true });
    await writeFile(imagePath, Buffer.from("png-bytes"));

    const { downloadServingImage } = await loadBlobModule();
    const result = await downloadServingImage("article-1", "images/diagram.png");

    expect(result?.contentType).toBe("image/png");
    expect(Buffer.from(result?.data ?? []).toString()).toBe("png-bytes");
  });

  it("rejects traversal paths before checking local files", async () => {
    await writeFile(path.join(tempRoot, "outside.png"), Buffer.from("secret"));

    const { downloadServingImage } = await loadBlobModule();
    const result = await downloadServingImage("article-1", "../outside.png");

    expect(result).toBeNull();
  });
});