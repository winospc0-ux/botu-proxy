addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  const url = new URL(request.url);

  // If ?url= param is provided, use it directly
  const targetParam = url.searchParams.get('url');
  if (targetParam) {
    return proxyFetch(targetParam, request);
  }

  // Otherwise, treat as HTTP forward proxy (absolute URI in request line)
  let target = url.pathname + url.search;
  if (!target.startsWith('http://') && !target.startsWith('https://')) {
    return new Response('Proxy usage: ?url= or absolute URI', { status: 400 });
  }

  return proxyFetch(target, request);
}

async function proxyFetch(target, request) {
  const headers = new Headers(request.headers);
  headers.set('Host', new URL(target).host);

  try {
    const resp = await fetch(target, {
      method: request.method,
      headers: headers,
      body: ['GET', 'HEAD'].includes(request.method) ? null : request.body,
      redirect: 'follow',
    });
    return new Response(resp.body, {
      status: resp.status,
      headers: resp.headers,
    });
  } catch (e) {
    return new Response(e.message, { status: 500 });
  }
}
