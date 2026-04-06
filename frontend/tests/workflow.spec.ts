import { test, expect } from '@playwright/test';

test('load app, switch mode, select asset', async ({ page }) => {
    await page.goto('/');

    // Expect title
    await expect(page.getByText('GEOTRADE').first()).toBeVisible();

    // App should load mock data natively
    await expect(page.getByText('Global Tension Index')).toBeVisible();

    // Mode switching
    await page.getByText('EARTH PULSE').click();
    // We can't easily assert the canvas change without image comparison,
    // but we can ensure the button registered the click (it has specific style or simply didn't crash).

    await page.getByText('ATTRACTOR').click();

    // Left Panel interactions
    await page.getByText('Equities').click();

    // Since we use a canvas, we simulate selecting an asset in the Right Panel's list directly 
    // if signal card has an action, but RightPanel already shows XAU/USD
    await page.getByText('XAU/USD').first().click();

    // Switch to Portfolio tab
    await page.getByText('PORTFOLIO').click();
    await expect(page.getByText('Stress Test')).toBeVisible();
});
