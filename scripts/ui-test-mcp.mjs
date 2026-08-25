/*
 * WisPay UI smoke review for the chrome-devtools MCP.
 *
 * Run this file by passing its body to the pi mcpScript tool. Start Reflex
 * first with:
 *   uv run reflex run --frontend-port 3000 --backend-port 8000 --backend-host 127.0.0.1
 *
 * Keep ROUTES aligned with the pages/components changed in the feature slice.
 */

const BASE_URL = "http://127.0.0.1:3000";
const ROUTES = ["/", "/requests", "/404", "/500", "/503"];
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];

const call = async (path, args = {}) => {
  const result = await tools.call(path, args);
  if (!result.ok) throw new Error(`${path}: ${result.error.message}`);
  return result.data;
};

const itemsFrom = (value) => {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.requests)) return value.requests;
  if (Array.isArray(value?.messages)) return value.messages;
  return [];
};

const pageList = await call("chrome-devtools_list_pages");
const existingPage = itemsFrom(pageList)[0];
const page = existingPage
  ? existingPage
  : await call("chrome-devtools_new_page", { url: `${BASE_URL}/` });
const pageId = page?.pageId ?? page?.id;
if (pageId !== undefined) await call("chrome-devtools_select_page", { pageId });

const results = [];
for (const route of ROUTES) {
  for (const viewport of VIEWPORTS) {
    await call("chrome-devtools_resize_page", viewport);
    await call("chrome-devtools_navigate_page", {
      type: "url",
      url: `${BASE_URL}${route}`,
      timeout: 30000,
    });

    const safeRoute = route === "/" ? "home" : route.slice(1).replaceAll("/", "-");
    const prefix = `test-results/ui-mcp/${safeRoute}-${viewport.name}`;
    const snapshot = await call("chrome-devtools_take_snapshot", {
      verbose: false,
      filePath: `${prefix}.a11y.txt`,
    });
    await call("chrome-devtools_take_screenshot", {
      format: "png",
      fullPage: true,
      filePath: `${prefix}.png`,
    });

    const consoleMessages = itemsFrom(
      await call("chrome-devtools_list_console_messages", { types: ["error"] }),
    );
    const networkRequests = itemsFrom(await call("chrome-devtools_list_network_requests"));
    const failedRequests = networkRequests.filter((request) => {
      const status = request.status ?? request.responseStatus;
      return typeof status === "number" && status >= 400;
    });

    results.push({
      route,
      viewport: viewport.name,
      consoleErrors: consoleMessages.length,
      failedRequests: failedRequests.length,
      snapshotSaved: `${prefix}.a11y.txt`,
      screenshotSaved: `${prefix}.png`,
      snapshotPreview: typeof snapshot === "string" ? snapshot.slice(0, 300) : undefined,
    });
  }
}

const failures = results.filter((result) => result.consoleErrors || result.failedRequests);
emit({ results, failures });
if (failures.length) throw new Error(`${failures.length} UI smoke checks reported failures`);
emit({ ok: true, checked: results.length, results });
