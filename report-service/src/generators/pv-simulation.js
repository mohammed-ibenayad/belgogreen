/**
 * PV Simulation PDF Generator
 * Renders Nunjucks templates → HTML → Puppeteer → PDF
 */
const nunjucks = require('nunjucks');
const path = require('path');
const fs = require('fs');
const { getBrowser } = require('../utils/browser');

const TEMPLATES_DIR = path.join(__dirname, '..', 'templates');
const STYLES_DIR = path.join(TEMPLATES_DIR, 'pv-simulation', 'styles');

async function generatePvSimulationPdf(data) {
  // Read CSS file
  const cssPath = path.join(STYLES_DIR, 'report.css');
  const css = fs.readFileSync(cssPath, 'utf-8');

  // Build footer HTML
  const footerParts = [];
  if (data.company && data.company.name) footerParts.push(data.company.name);
  const sp = data.salesperson || {};
  if (sp.phone || (data.company && data.company.phone)) {
    footerParts.push(`☎ ${sp.phone || data.company.phone}`);
  }
  if (sp.email || (data.company && data.company.email)) {
    footerParts.push(`✉ ${sp.email || data.company.email}`);
  }
  const footerLine = footerParts.join(' | ');

  // Render HTML with Nunjucks
  const html = nunjucks.render('pv-simulation/report.njk', {
    data: {
      ...data,
      section_titles: data.section_titles || {},
      bilan: data.bilan || {},
    },
  });

  // Wrap with full HTML including inline CSS (Puppeteer needs self-contained HTML)
  const fullHtml = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <style>${css}</style>
</head>
<body>
${html}
</body>
</html>`;

  // Generate PDF with Puppeteer
  const browser = await getBrowser();
  const page = await browser.newPage();

  try {
    await page.setContent(fullHtml, { waitUntil: 'networkidle0', timeout: 15000 });
    await page.emulateMediaType('print');

    const pdfBuffer = await page.pdf({
      format: 'A4',
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: `
        <div style="
          width: 100%;
          padding: 0 20mm;
          font-family: Inter, Helvetica Neue, Helvetica, Arial, sans-serif;
          font-size: 8pt;
          color: #616161;
          display: flex;
          justify-content: space-between;
          border-top: 1.5px solid #4A9B5D;
          padding-top: 2mm;
        ">
          <span>${footerLine}</span>
          <span>Page <span class="pageNumber"></span> / <span class="totalPages"></span></span>
        </div>`,
      margin: {
        top: '25mm',
        right: '20mm',
        bottom: '22mm',
        left: '20mm',
      },
    });

    return Buffer.from(pdfBuffer);
  } finally {
    await page.close();
  }
}

module.exports = { generatePvSimulationPdf };
