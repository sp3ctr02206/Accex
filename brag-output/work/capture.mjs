// node capture.mjs stills 0.5 3.2 ...   -> stills/t_<time>.png
// node capture.mjs video                -> video.mp4 (silent), every frame piped to ffmpeg
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";

const FPS = 30, DURATION = 20, W = 1920, H = 1080;
const here = path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, "$1"));
const page_url = pathToFileURL(path.join(here, "composition", "index.html")).href;

const browser = await puppeteer.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  args: [`--window-size=${W},${H}`, "--hide-scrollbars", "--force-color-profile=srgb", "--disable-gpu-vsync"],
});
const page = await browser.newPage();
await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
await page.goto(page_url, { waitUntil: "load" });
await page.evaluate(() => window.ready);

const [mode, ...rest] = process.argv.slice(2);
async function shot(t, type = "png") {
  await page.evaluate((t) => window.render(t), t);
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  return page.screenshot({ type, ...(type === "jpeg" ? { quality: 96 } : {}), optimizeForSpeed: false });
}

if (mode === "stills") {
  mkdirSync(path.join(here, "stills"), { recursive: true });
  for (const s of rest) {
    const buf = await shot(parseFloat(s));
    const { writeFileSync } = await import("node:fs");
    writeFileSync(path.join(here, "stills", `t_${s}.png`), buf);
  }
} else {
  const out = path.join(here, "video.mp4");
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p", "-r", String(FPS), out],
    { stdio: ["pipe", "inherit", "inherit"] });
  const total = FPS * DURATION;
  for (let f = 0; f < total; f++) {
    const buf = await shot(f / FPS, "png");
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
    if (f % 60 === 0) process.stdout.write(`frame ${f}/${total}\n`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on("close", r));
  console.log("wrote", out);
}
await browser.close();
