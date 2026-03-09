const express = require('express');
const router = express.Router();
const { generatePvSimulationPdf } = require('../generators/pv-simulation');

router.post('/pv-simulation', async (req, res) => {
  try {
    const data = req.body;

    if (!data || !data.name) {
      return res.status(400).json({ error: 'Missing required field: name' });
    }

    const pdfBuffer = await generatePvSimulationPdf(data);

    res.set({
      'Content-Type': 'application/pdf',
      'Content-Disposition': `attachment; filename="Rapport_PV_${data.name}.pdf"`,
      'Content-Length': pdfBuffer.length,
    });

    res.send(pdfBuffer);
  } catch (err) {
    console.error('Report generation failed:', err);
    res.status(500).json({ error: 'Report generation failed', details: err.message });
  }
});

module.exports = router;
