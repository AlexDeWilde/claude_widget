// background.js

// Swallow benign chrome.* rejections (e.g. "Tabs cannot be edited right now")
// so the service worker can't die mid-poll and strand isPolling=true.
self.addEventListener('unhandledrejection', (event) => {
    event.preventDefault();
});

// Keep the service worker alive by waking it up every minute
chrome.alarms.create("keepAlive", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(() => {
    pollWidget();
});

let isPolling = false;
const SCRAPE_TIMEOUT_MS = 25000;
const READY_POLL_MS = 500;
const READY_MAX_TRIES = 30; // 30 * 500ms = 15s of readiness polling

function pollWidget() {
    if (isPolling) return;
    isPolling = true;

    fetch("http://127.0.0.1:8765/poll")
        .then(res => res.json())
        .then(async data => {
            if (data.needs_refresh) {
                let usage = await getUsageByTab();
                await fetch("http://127.0.0.1:8765/update", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(usage)
                });
            }
        })
        .catch(e => {
            // Widget server offline or scrape failed
        })
        .finally(() => {
            isPolling = false;
            // Quick 1s poll for responsiveness while SW is awake
            setTimeout(pollWidget, 1000);
        });
}

// Start polling immediately when script loads
pollWidget();

function getUsageByTab() {
    return new Promise((resolve) => {
        let settled = false;
        let createdTabId = null;
        let updateListener = null;
        let timeoutId = null;

        const cleanup = (result) => {
            if (settled) return;
            settled = true;
            if (timeoutId) clearTimeout(timeoutId);
            if (updateListener) {
                try { chrome.tabs.onUpdated.removeListener(updateListener); } catch (e) {}
            }
            if (createdTabId !== null) {
                try { chrome.tabs.remove(createdTabId, () => void chrome.runtime.lastError); } catch (e) {}
            }
            resolve(result);
        };

        const fail = () => cleanup({ percentage: "--", time_left: "--:--" });

        // Hard timeout — guarantees the promise always settles
        timeoutId = setTimeout(fail, SCRAPE_TIMEOUT_MS);

        chrome.tabs.create({ url: "https://claude.ai/settings/usage", active: false }, (tab) => {
            if (chrome.runtime.lastError || !tab) { fail(); return; }
            createdTabId = tab.id;

            const parseText = (text) => {
                let percentage = "--";
                let time_left = "--:--";
                let pMatch = text.match(/CURRENT SESSION.*?(\d+)%\s*used/is) || text.match(/(\d+)%\s*used/i);
                if (pMatch) percentage = pMatch[1];
                let resetStrMatch = text.match(/resets in(.*?)(?=\n|$)/i);
                if (resetStrMatch) {
                    let s = resetStrMatch[1];
                    let hMatch = s.match(/(\d+)\s*hr/i);
                    let mMatch = s.match(/(\d+)\s*min/i);
                    let h = hMatch ? hMatch[1] : "0";
                    let m = mMatch ? mMatch[1].padStart(2, '0') : "00";
                    time_left = `${h}:${m}`;
                }
                return { percentage, time_left };
            };

            const tryScrape = (attempt) => {
                if (settled) return;
                chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: () => document.body ? document.body.innerText : ""
                }, (results) => {
                    if (settled) return;
                    if (chrome.runtime.lastError) { fail(); return; }

                    const text = (results && results[0] && results[0].result) || "";
                    const ready = /\d+%\s*used/i.test(text);

                    if (ready) {
                        cleanup(parseText(text));
                        return;
                    }
                    if (attempt + 1 >= READY_MAX_TRIES) {
                        // Give up: parse whatever we have (likely "--")
                        cleanup(parseText(text));
                        return;
                    }
                    setTimeout(() => tryScrape(attempt + 1), READY_POLL_MS);
                });
            };

            const executeAndClose = () => {
                // Small initial delay so SPA has a chance to mount before first probe
                setTimeout(() => tryScrape(0), 1000);
            };

            // If the user closes the background tab manually, fail fast instead of hanging
            const removedListener = (closedId) => {
                if (closedId === tab.id) {
                    chrome.tabs.onRemoved.removeListener(removedListener);
                    if (!settled) fail();
                }
            };
            chrome.tabs.onRemoved.addListener(removedListener);

            // Sometimes the tab loads incredibly fast from cache and misses the listener!
            if (tab.status === 'complete') {
                executeAndClose();
            } else {
                updateListener = (tabId, info) => {
                    if (tabId === tab.id && info.status === 'complete') {
                        chrome.tabs.onUpdated.removeListener(updateListener);
                        updateListener = null;
                        executeAndClose();
                    }
                };
                chrome.tabs.onUpdated.addListener(updateListener);
            }
        });
    });
}
