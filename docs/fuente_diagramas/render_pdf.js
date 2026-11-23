const { chromium } = require('playwright');
const dir = process.argv[2];
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('file://' + dir + '/dcu.html');
  const secs = await p.$$('section.pag');
  for (let i = 0; i < secs.length; i++) await (await secs[i].$('svg')).screenshot({ path: dir + '/pag' + i + '.png' });
  if (process.argv[3]) {
    await p.pdf({ path: process.argv[3], printBackground: true, preferCSSPageSize: true });
  }
  console.log(secs.length);
  await b.close();
})();
