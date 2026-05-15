document.addEventListener("DOMContentLoaded", function () {
    loadDashboardData();
});

async function loadDashboardData() {
    try {
        const response = await fetch("/data/sources/latest");

        if (!response.ok) {
            throw new Error("Could not load dashboard data");
        }

        const sources = await response.json();

        updateSummaryCards(sources);
        updateSourcesTable(sources);
        updateRecentActivity(sources);

        const selectedSource = sources.find(source => getStatus(source) === "warning") || sources[0];

        if (selectedSource) {
            showSourceDetails(selectedSource);
        }

    } catch (error) {
        console.error(error);

        document.getElementById("sources-table-body").innerHTML = `
            <tr>
                <td colspan="8">Could not load monitoring data.</td>
            </tr>
        `;

        document.getElementById("recent-activity-body").innerHTML = `
            <tr>
                <td colspan="4">Could not load recent activity.</td>
            </tr>
        `;
    }
}

function updateSummaryCards(sources) {
    const totalSources = sources.length;
    const onlineSources = sources.filter(source => getStatus(source) === "online").length;
    const warningSources = sources.filter(source => getStatus(source) === "warning").length;
    const offlineSources = sources.filter(source => getStatus(source) === "offline").length;

    document.getElementById("total-sources").textContent = totalSources;
    document.getElementById("online-sources").textContent = onlineSources;
    document.getElementById("warning-sources").textContent = warningSources;
    document.getElementById("offline-sources").textContent = offlineSources;
}

function updateSourcesTable(sources) {
    const tableBody = document.getElementById("sources-table-body");

    if (!sources || sources.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8">No monitoring data available.</td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = "";

    sources.forEach(source => {
        const status = getStatus(source);
        const warningMessage = getWarningMessage(source);

        const row = document.createElement("tr");
        row.classList.add("source-row");

        row.innerHTML = `
            <td>${source.device_name || "Unknown"}</td>
            <td>Server</td>
            <td><span class="status-badge status-${status}">${capitalize(status)}</span></td>
            <td>${formatTimestamp(source.timestamp)}</td>
            <td>${source.cpu_usage ?? 0}%</td>
            <td>${source.memory_usage ?? 0}%</td>
            <td>${source.disk_usage ?? 0}%</td>
            <td>${warningMessage}</td>
        `;

        row.addEventListener("click", function () {
            showSourceDetails(source);
        });

        tableBody.appendChild(row);
    });
}

function showSourceDetails(source) {
    const detailsBox = document.getElementById("source-details");
    const status = getStatus(source);

    detailsBox.innerHTML = `
        <p><strong>Source Name:</strong> ${source.device_name || "Unknown"}</p>
        <p><strong>Type:</strong> Server</p>
        <p><strong>Status:</strong> <span class="status-badge status-${status}">${capitalize(status)}</span></p>
        <p><strong>CPU Usage:</strong> ${source.cpu_usage ?? 0}%</p>
        <p><strong>Memory Usage:</strong> ${source.memory_usage ?? 0}%</p>
        <p><strong>Disk Usage:</strong> ${source.disk_usage ?? 0}%</p>
        <p><strong>Last Update:</strong> ${formatTimestamp(source.timestamp)}</p>
        <p><strong>Warning:</strong> ${getWarningMessage(source)}</p>
    `;
}

function updateRecentActivity(sources) {
    const activityBody = document.getElementById("recent-activity-body");

    if (!sources || sources.length === 0) {
        activityBody.innerHTML = `
            <tr>
                <td colspan="4">No recent activity available.</td>
            </tr>
        `;
        return;
    }

    activityBody.innerHTML = "";

    sources.slice(0, 5).forEach(source => {
        const status = getStatus(source);
        const eventMessage = createEventMessage(source);

        const row = document.createElement("tr");

        row.innerHTML = `
            <td>${formatTimestamp(source.timestamp)}</td>
            <td>${source.device_name || "Unknown"}</td>
            <td>${eventMessage}</td>
            <td><span class="status-badge status-${status}">${capitalize(status)}</span></td>
        `;

        activityBody.appendChild(row);
    });
}

function getStatus(source) {
    return (source.status || "unknown").toLowerCase();
}

function getWarningMessage(source) {
    if (source.warning_message) {
        return source.warning_message;
    }

    if (source.disk_usage >= 90) {
        return "Disk usage is high";
    }

    if (source.memory_usage >= 85) {
        return "Memory usage is high";
    }

    if (source.cpu_usage >= 85) {
        return "CPU usage is high";
    }

    if (getStatus(source) === "offline") {
        return "Source is offline";
    }

    if (getStatus(source) === "warning") {
        return "Source needs attention";
    }

    return "-";
}

function createEventMessage(source) {
    const status = getStatus(source);

    if (status === "warning") {
        return getWarningMessage(source);
    }

    if (status === "offline") {
        return "Source is not responding";
    }

    return "Data received";
}

function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "Unknown";
    }

    const date = new Date(timestamp);

    if (isNaN(date)) {
        return timestamp;
    }

    return date.toLocaleString();
}

function capitalize(text) {
    if (!text) {
        return "Unknown";
    }

    return text.charAt(0).toUpperCase() + text.slice(1);
}