import {test,expect} from '@playwright/test';

test('all 55 inputs, real prediction, stale state, explanations and export',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:1100});
  await page.goto('/');await expect(page.getByText('Models ready')).toBeVisible();
  const names=new Set<string>();
  for(const group of ['Profile','History','Symptoms','Examination','ECG & echo','Laboratory']){
    await page.getByRole('tab',{name:group,exact:true}).click();
    for(const id of await page.locator('.field input,.field select').evaluateAll(elements=>elements.map(e=>e.id)))names.add(id);
  }
  expect(names.size).toBe(55);
  await page.getByRole('tab',{name:'Profile',exact:true}).click();
  await expect(page.getByRole('button',{name:'Export assessment'})).toBeDisabled();
  const resultPromise=page.waitForResponse('/api/predict');
  await page.getByRole('button',{name:'Run assessment'}).click();
  const result=await (await resultPromise).json();
  await expect(page.locator('.prediction-item').first()).toContainText((result.predictions.CAD.probability*100).toFixed(1));
  await expect(page.getByRole('button',{name:'Export assessment'})).toBeEnabled();
  await expect(page.locator('.viewer-loading')).toHaveCount(0,{timeout:40000});
  await expect(page.locator('canvas')).toBeVisible();
  await page.getByRole('button',{name:'View all 55 inputs'}).click();
  await expect(page.locator('.evidence-row')).toHaveCount(55);
  const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Export assessment'}).click();
  expect((await downloadPromise).suggestedFilename()).toBe('coronary-assessment.json');
  await page.getByRole('button',{name:'Show strongest inputs'}).click();
  await page.screenshot({path:'test-results/desktop.png',fullPage:true});
  await page.locator('#field-Age').fill('72');
  await expect(page.getByText('Inputs changed · previous results')).toBeVisible();
  await expect(page.getByRole('button',{name:'Export assessment'})).toBeDisabled();
  await page.getByRole('button',{name:'Run assessment'}).click();
  await expect(page.getByText('Assessment complete',{exact:true})).toBeVisible();
  await page.locator('.anatomy-targets').getByRole('button',{name:'LCX',exact:true}).click();
  await expect(page.getByRole('heading',{name:'What contributes to LCX?'})).toBeVisible();
  await page.getByRole('button',{name:'See through'}).click();
  await expect(page.getByRole('button',{name:'Solid heart'})).toBeVisible();
  expect(errors).toEqual([]);
});

test('mobile layout and model information keyboard handling',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');
  await expect(page.getByText('Models ready')).toBeAttached();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Model & data'}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.screenshot({path:'test-results/mobile.png',fullPage:true});
});

test('service errors are actionable and never produce fabricated scores',async({page})=>{
  await page.goto('/');await expect(page.getByText('Models ready')).toBeVisible();
  await page.route('**/api/predict',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'The prediction service is unavailable. Start the API and try again.'})}));
  await page.getByRole('button',{name:'Run assessment'}).click();
  await expect(page.locator('.error-banner')).toContainText('prediction service is unavailable');
  await expect(page.locator('.no-score')).toHaveCount(4);
});
