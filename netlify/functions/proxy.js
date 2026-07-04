exports.handler = async (event) => {
  const target = event.queryStringParameters?.url;
  if (!target) {
    return { statusCode: 400, body: '?url= مطلوب' };
  }

  try {
    const resp = await fetch(target, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36',
      },
      redirect: 'follow',
    });

    const body = await resp.text();
    return {
      statusCode: resp.status,
      headers: {
        'Content-Type': resp.headers.get('content-type') || 'text/plain',
      },
      body,
    };
  } catch (e) {
    return { statusCode: 500, body: `Proxy error: ${e.message}` };
  }
};
