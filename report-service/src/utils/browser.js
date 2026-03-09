/**
 * Puppeteer browser pool — reuses a single Chromium instance
 */
const puppeteer = require('puppeteer');

let browser = null;

async function getBrowser() {
  if (browser && browser.connected) {
    return browser;
  }

  browser = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--font-render-hinting=none',
    ],
  });

  browser.on('disconnected', () => {
    browser = null;
  });

  return browser;
}

async function closeBrowser() {
  if (browser) {
    await browser.close();
    browser = null;
  }
}

module.exports = { getBrowser, closeBrowser };
