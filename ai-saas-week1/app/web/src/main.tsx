const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element #root not found");
}

root.innerHTML = `
  <main style="font-family: sans-serif; padding: 24px;">
    <h1>ai-saas-week1 web is running</h1>
    <p>If you can see this page, Vite is serving correctly.</p>
  </main>
`;
