# Claude Widget — Architecture Diagrams

---

## 1. System Architecture

High-level view of the two independent components and how they communicate over localhost.

```mermaid
flowchart LR
    subgraph Browser["Chrome Browser"]
        CA["claude.ai\n/settings/usage"]
        CE["Chrome Extension\nbackground.js\n(service worker)"]
    end

    subgraph Machine["Local Machine (Windows)"]
        direction TB
        SRV["HTTP Server\n127.0.0.1:8765\n(app.py)"]
        UI["Tkinter Widget\nframeless · always-on-top"]
        STATE[("Shared State\npercentage\ntime_left\nneeds_refresh")]
        SRV -- "reads / writes" --> STATE
        UI -- "reads every 500 ms" --> STATE
    end

    CE -->|"GET /poll"| SRV
    SRV -->|"{ needs_refresh: true/false }"| CE
    CE -->|"opens hidden tab + scrapes DOM"| CA
    CA -->|"innerText → % used, resets in …"| CE
    CE -->|"POST /update\n{ percentage, time_left }"| SRV
```

---

## 2. Poll / Scrape / Update Sequence

One full refresh cycle, from the service worker waking up to the widget displaying new data.

```mermaid
sequenceDiagram
    participant SW as background.js
    participant SRV as HTTP Server :8765
    participant TAB as claude.ai/settings/usage
    participant UI as Tkinter Widget

    Note over SRV,UI: App starts — needs_refresh = true

    loop ~1 s while SW awake · 1 min via chrome.alarms
        SW->>SRV: GET /poll
        SRV-->>SW: { needs_refresh: true }

        SW->>TAB: chrome.tabs.create (active: false)
        TAB-->>SW: tab loaded — executeScript reads body.innerText
        Note over SW: Retries every 500 ms until<br/>"\\d+% used" found (max 15 s)
        SW->>SRV: POST /update { percentage:"42", time_left:"3:15" }
        SRV-->>SW: { status: "ok" }
        Note over SRV: needs_refresh = false<br/>last_update_ts = now<br/>next_refresh_ts = now + 10 min

        loop Every 500 ms
            UI->>UI: update_ui() → display 42% · 3:15
        end
    end
```

---

## 3. Widget Refresh State Machine

How `needs_refresh` moves through states driven by the timer, the user, and incoming updates.

```mermaid
stateDiagram-v2
    [*] --> Stale : App launch\n(needs_refresh = true)

    Stale --> Fetching : Extension reads needs_refresh=true\nand opens scrape tab

    Fetching --> Fresh : POST /update received\n(needs_refresh = false)

    Fresh --> Stale : User clicks [MMmSSs] button

    Fresh --> AutoRefresh : 10-minute timer fires\n(next_refresh_ts reached)

    AutoRefresh --> Stale : on_refresh_click()\nsets needs_refresh = true\nauto_refresh = true

    Stale --> Fetching : Extension next poll cycle

    note right of Fetching
        UI dims the timer label
        and shows --% / --:--
        while waiting
    end note

    note right of AutoRefresh
        Completed refresh adds
        random 0–17 s jitter to
        prevent thundering-herd
        if many instances run
    end note
```

---

## 4. File & Responsibility Map

Source files, what each owns, and the runtime boundary between the two processes.

```mermaid
flowchart TD
    subgraph repo["claude_widget/"]
        ROOT_FILES["Launch.bat\nREADME.md\nchange log.txt"]

        subgraph ext["chrome_extension/"]
            MANIFEST["manifest.json\nMV3 · host perms\nalarms · scripting · tabs"]
            BGS["background.js\n• keepAlive alarm\n• pollWidget loop\n• getUsageByTab scraper\n• parseText regex"]
        end

        subgraph widget["desktop_widget/"]
            APP["app.py\n• ClaudeWidget (Tk)\n• LocalRequestHandler (HTTP)\n• shared state dict\n• position persistence"]
            SPEC["ClaudeWidget.spec\nPyInstaller config"]
            BUILDBAT["build.bat\ncompiles → dist/ClaudeWidget.exe"]
            DIST["dist/\nClaudeWidget.exe\nwidget_config.json ← position"]
        end
    end

    MANIFEST --> BGS
    SPEC --> BUILDBAT --> DIST
    APP -->|"bundles into"| DIST
    ROOT_FILES -->|"Launch.bat starts"| APP
```
