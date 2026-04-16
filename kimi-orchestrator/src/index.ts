import { createApp } from "./app.js";

const app = createApp();
const PORT = Number(process.env.PORT || "4000");

app.listen(PORT, "0.0.0.0", () => {
  console.log(`Kimi Orchestrator listening on http://0.0.0.0:${PORT}`);
});
