const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Test English Version
  console.log('Testing English version...');
  await page.goto('file://' + process.cwd() + '/docs/index.html?lang=en');
  await page.waitForTimeout(2000); // Wait for Mermaid to render
  await page.screenshot({ path: 'en_version.png', fullPage: true });

  // Test Chinese Version
  console.log('Testing Chinese version...');
  await page.goto('file://' + process.cwd() + '/docs/index.html?lang=zh');
  await page.waitForTimeout(2000); // Wait for Mermaid to render
  await page.screenshot({ path: 'zh_version.png', fullPage: true });

  await browser.close();
  console.log('Screenshots saved: en_version.png, zh_version.png');
})();
