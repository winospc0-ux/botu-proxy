exports.handler = async (event) => {
  const target = event.queryStringParameters?.url;
  if (!target) return { statusCode: 400, body: '?url=' };

  try {
    const hdrs = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36',
    };
    if (event.headers?.cookie) hdrs['Cookie'] = event.headers.cookie;

    const resp = await fetch(target, { headers: hdrs, redirect: 'follow' });
    const body = await resp.text();
    return {
      statusCode: resp.status,
      headers: { 'Content-Type': resp.headers.get('content-type') || 'text/plain' },
      body,
    };
  } catch (e) {
    return { statusCode: 500, body: `Error: ${e.message}` };
  }
};
