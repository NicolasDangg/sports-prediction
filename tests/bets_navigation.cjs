// Run against a local dashboard with Playwright available via NODE_PATH.
const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require("playwright");

async function main() {
  process.loadEnvFile(path.join(__dirname, "../dashboard/.env.local"));
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(10000);
    const base = process.env.BETS_TEST_URL || "http://localhost:3100";
    const response = await page.request.post(`${base}/api/login`, {
      data: { password: process.env.DASHBOARD_PASSWORD, next: "/bets" },
    });
    assert.equal(response.status(), 200, "local dashboard login");
    await page.goto(`${base}/bets`);
    const status = page.getByRole("tablist", { name: "Bet status" });
    const sport = page.getByRole("tablist", { name: "Sport", exact: true });
    async function selected(group, name) {
      await group.getByRole("tab", { name, selected: true }).waitFor();
    }
    await selected(status, /^Open/);
    for (const mobile of [false, true]) {
      await page.setViewportSize({ width: mobile ? 390 : 1280, height: 900 });
      await status.getByRole("tab", { name: /^Settled/ }).click();
      await sport.getByRole("tab", { name: "ATP", exact: true }).click();
      const bet = page.locator('main a[href^="/bets/"]:visible').first();
      await bet.click();
      await page.waitForURL(/\/bets\/[^/]+$/);
      await page.getByRole("link", { name: "Bets", exact: true }).last().click();
      await page.waitForURL(/\/bets$/);
      await selected(status, /^Settled/);
      await selected(sport, "ATP");
      await bet.click();
      await page.waitForURL(/\/bets\/[^/]+$/);
      await page.goBack();
      await selected(status, /^Settled/);
      await selected(sport, "ATP");
      await page.reload();
      await selected(status, /^Settled/);
      await selected(sport, "ATP");
    }
    await status.getByRole("tab", { name: /^All/ }).click();
    await sport.getByRole("tab", { name: "EPL", exact: true }).click();
    await page.reload();
    await selected(status, /^All/);
    await selected(sport, "EPL");
    await page.evaluate(() => sessionStorage.setItem("bets-filters", "invalid JSON"));
    await page.reload();
    await selected(status, /^Open/);
    await selected(sport, "Both");
    await page.evaluate(() => sessionStorage.setItem("bets-filters", JSON.stringify({ status: "bad", sport: "bad" })));
    await page.reload();
    await selected(status, /^Open/);
    await selected(sport, "Both");
    await page.addInitScript(() => {
      Storage.prototype.getItem = Storage.prototype.setItem = () => { throw new Error("Storage blocked"); };
    });
    await page.reload();
    await status.getByRole("tab", { name: /^Settled/ }).click();
    await selected(status, /^Settled/);
    console.log("Bets navigation passed: desktop/mobile, link/back, reload, both filters, invalid/blocked storage.");
  } finally {
    await browser.close();
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
