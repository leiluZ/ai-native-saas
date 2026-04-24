import http from "node:http";

const port = Number(process.env.API_PORT || 4000);

const server = http.createServer((_req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify({ service: "api", status: "ok" }));
});

server.listen(port, () => {
  // Basic startup log for local debugging.
  console.log(`[api] listening on :${port}`);
});
