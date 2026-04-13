// Templater user script — maakt HTTP requests via Node.js https module.
// Node modules zijn beschikbaar in user scripts, niet in template inline code.
// Gebruik in template: await tp.user.claude_api(apiKey, prompt)

const https = require('https');

module.exports = async function(apiKey, prompt) {
  const body = JSON.stringify({
    model: "claude-sonnet-4-6",
    max_tokens: 4096,
    messages: [{ role: "user", content: prompt }]
  });

  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: 'api.anthropic.com',
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'Content-Length': Buffer.byteLength(body)
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch(e) { reject(new Error('JSON parse fout: ' + e.message)); }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
};
