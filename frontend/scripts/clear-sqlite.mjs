import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const backendDir = path.join(repoRoot, "backend");
const configPath = path.join(backendDir, "scraper_config.json");
const defaultDbPath = path.join(backendDir, "checkpoints", "seen_leads.sqlite3");

async function readConfiguredDbPath() {
  try {
    const raw = await fs.readFile(configPath, "utf8");
    const parsed = JSON.parse(raw);
    const configuredPath = parsed?.dedupe_db_path;
    if (typeof configuredPath !== "string" || configuredPath.trim() === "") {
      return defaultDbPath;
    }
    const resolvedPath = path.resolve(backendDir, configuredPath);
    const relativeToRepo = path.relative(repoRoot, resolvedPath);
    if (relativeToRepo.startsWith("..") || path.isAbsolute(relativeToRepo)) {
      throw new Error(
        `Configured dedupe_db_path resolves outside the repository: ${configuredPath}`,
      );
    }
    return resolvedPath;
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return defaultDbPath;
    }
    if (error instanceof SyntaxError) {
      throw new Error(`Could not parse ${path.relative(repoRoot, configPath)}.`);
    }
    throw error;
  }
}

async function ensureWithinRepo(targetPath) {
  const resolvedPath = path.resolve(targetPath);
  const relativeToRepo = path.relative(repoRoot, resolvedPath);
  if (relativeToRepo.startsWith("..") || path.isAbsolute(relativeToRepo)) {
    throw new Error(`Refusing to delete a path outside the repository: ${targetPath}`);
  }
  return resolvedPath;
}

async function removeIfPresent(targetPath) {
  const safePath = await ensureWithinRepo(targetPath);
  try {
    await fs.unlink(safePath);
    return true;
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return false;
    }
    throw error;
  }
}

const dbPath = await readConfiguredDbPath();
const sqlitePaths = [dbPath, `${dbPath}-shm`, `${dbPath}-wal`, `${dbPath}-journal`];

const removed = [];
for (const sqlitePath of sqlitePaths) {
  if (await removeIfPresent(sqlitePath)) {
    removed.push(path.relative(repoRoot, sqlitePath));
  }
}

if (removed.length === 0) {
  console.log(`No SQLite dedupe files found at ${path.relative(repoRoot, dbPath)}.`);
} else {
  console.log("Removed SQLite dedupe files:");
  for (const removedPath of removed) {
    console.log(`- ${removedPath}`);
  }
}
