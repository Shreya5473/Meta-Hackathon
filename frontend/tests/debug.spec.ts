import { test, expect } from '@playwright/test';

test('check console errors on clicking trading', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => {
        console.log(`PAGE ERROR: ${error.name} - ${error.message}`);
        errors.push(error.message);
    });
    page.on('console', msg => {
        if (msg.type() === 'error')
            console.log(`CONSOLE ERROR: ${msg.text()}`);
        errors.push(msg.text());
    });

    await page.goto('http://localhost:5173');

    // Wait for the app to load
    await page.waitForSelector('text=EARTH PULSE');

    // Click the TRADING button
    await page.getByText('TRADING').click();

    // Wait to see if error happens
    await page.waitForTimeout(2000);

    if (errors.length > 0) {
        console.log('Test caught errors:', errors);
        process.exit(1);
    }
});
