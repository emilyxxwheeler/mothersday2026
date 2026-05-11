import { kv } from '@vercel/kv';

const EMPTY_PAYLOAD = {
  added: [],
  modifications: {},
  deleted: [],
  onboardingState: null,
  onboardingCompleted: false,
  schemaVersion: 1,
};

function sanitizeProfile(p) {
  const s = String(p || 'jane').toLowerCase().replace(/[^a-z0-9-]/g, '');
  return s.slice(0, 32) || 'jane';
}

function setCors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-store');
}

export default async function handler(req, res) {
  setCors(res);

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

  const profile = sanitizeProfile(req.query.profile);
  const key = `${profile}:overrides`;

  if (req.method === 'GET') {
    const stored = await kv.get(key);
    return res.status(200).json(stored || EMPTY_PAYLOAD);
  }

  if (req.method === 'POST') {
    let body = req.body;
    if (typeof body === 'string') {
      try { body = JSON.parse(body); }
      catch { return res.status(400).json({ error: 'Invalid JSON' }); }
    }
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      return res.status(400).json({ error: 'Body must be a JSON object' });
    }
    await kv.set(key, body);
    return res.status(200).json({ ok: true });
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
