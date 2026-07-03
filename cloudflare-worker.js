export default {
  async fetch(request) {
    const url = new URL(request.url);
    const apiUrl = `https://api.telegram.org${url.pathname}${url.search}`;

    const modifiedHeaders = new Headers(request.headers);
    modifiedHeaders.set("Host", "api.telegram.org");

    return fetch(apiUrl, {
      method: request.method,
      headers: modifiedHeaders,
      body: request.body,
    });
  },
};
