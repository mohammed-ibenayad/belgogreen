const express = require('express');
const nunjucks = require('nunjucks');
const path = require('path');
const { getBrowser, closeBrowser } = require('./utils/browser');
const reportsRouter = require('./routes/reports');

const app = express();
const PORT = process.env.PORT || 3002;
const API_KEY = process.env.API_KEY;

// Parse JSON bodies up to 50MB (reports contain base64 images)
app.use(express.json({ limit: '50mb' }));

// API key authentication middleware
function authMiddleware(req, res, next) {
  if (!API_KEY) return next(); // Skip auth if no key configured

  const auth = req.headers.authorization;
  if (!auth || auth !== `Bearer ${API_KEY}`) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

// Configure Nunjucks
const templatesDir = path.join(__dirname, 'templates');
const env = nunjucks.configure(templatesDir, {
  autoescape: true,
  noCache: process.env.NODE_ENV !== 'production',
});

// Custom filters
env.addFilter('formatNumber', (val, decimals = 2) => {
  if (val == null || val === '' || val === 0) return '—';
  return Number(val).toLocaleString('fr-BE', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
});

env.addFilter('formatInt', (val) => {
  if (val == null || val === '') return '—';
  return Number(val).toLocaleString('fr-BE', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'belgogreen-report-service' });
});

// Report routes (with auth)
app.use('/api/reports', authMiddleware, reportsRouter);

// Pre-launch browser on startup
async function start() {
  try {
    await getBrowser();
    console.log('Chromium browser launched successfully');
  } catch (err) {
    console.error('Failed to launch Chromium:', err.message);
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Report service listening on port ${PORT}`);
  });
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('Shutting down...');
  await closeBrowser();
  process.exit(0);
});

process.on('SIGINT', async () => {
  await closeBrowser();
  process.exit(0);
});

start();
