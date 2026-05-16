let allHistoryRecords = [];

document.addEventListener("DOMContentLoaded", function () {
    loadHistoryData();

    const filterForm = document.getElementById("history-filter-form");
    const resetButton = document.getElementById("reset-filter-button");

    filterForm.addEventListener("submit", function (event) {
        event.preventDefault();
        applyFilters();
    });

    resetButton.addEventListener("click", function () {
        resetFilters();
    });
});

async function loadHistoryData() {
    try {
        const response = await fetch("/data/history");

        if (!response.ok) {
            throw new Error("Could not load history data");
        }

        allHistoryRecords = await response.json();

        fillSourceFilter(allHistoryRecords);
        displayHistoryRecords(allHistoryRecords);

    } catch (error) {
        console.error(error);

        document.getElementById("history-table-body").innerHTML = `
            <tr>
                <td colspan="7">Could not load historical data.</td>
            </tr>
        `;
    }
}

function fillSourceFilter(records) {
    const sourceFilter = document.getElementById("source-filter");
    const existingSources = new Set();

    records.forEach(record => {
        if (record.device_name) {
            existingSources.add(record.device_name);
        }
    });

    existingSources.forEach(sourceName => {
        const option = document.createElement("option");
        option.value = sourceName;
        option.textContent = sourceName;
        sourceFilter.appendChild(option);
    });
}

function applyFilters() {
    const selectedSource = document.getElementById("source-filter").value;
    const selectedStatus = document.getElementById("status-filter").value;
    const selectedMetric = document.getElementById("metric-filter").value;
    const selectedOperator = document.getElementById("operator-filter").value;
    const selectedNumber = document.getElementById("number-filter").value;
    const startDate = document.getElementById("start-date-filter").value;
    const endDate = document.getElementById("end-date-filter").value;

    const filteredRecords = allHistoryRecords.filter(record => {
        const sourceMatch = selectedSource === "all" || record.device_name === selectedSource;
        const statusMatch = selectedStatus === "all" || getStatus(record) === selectedStatus.toLowerCase();
        const dateMatch = isInsideDateRange(record.timestamp, startDate, endDate);
        const numberMatch = checkNumberFilter(record, selectedMetric, selectedOperator, selectedNumber);

        return sourceMatch && statusMatch && dateMatch && numberMatch;
    });

    displayHistoryRecords(filteredRecords);
}

function checkNumberFilter(record, selectedMetric, selectedOperator, selectedNumber) {
    if (selectedMetric === "all") {
        return true;
    }

    if (selectedOperator === "none" || selectedNumber === "") {
        return true;
    }

    const recordValue = Number(record[selectedMetric]);
    const filterValue = Number(selectedNumber);

    if (isNaN(recordValue) || isNaN(filterValue)) {
        return false;
    }

    if (selectedOperator === "greater") {
        return recordValue > filterValue;
    }

    if (selectedOperator === "less") {
        return recordValue < filterValue;
    }

    if (selectedOperator === "equal") {
        return recordValue === filterValue;
    }

    return true;
}

function resetFilters() {
    document.getElementById("source-filter").value = "all";
    document.getElementById("status-filter").value = "all";
    document.getElementById("metric-filter").value = "all";
    document.getElementById("operator-filter").value = "none";
    document.getElementById("number-filter").value = "";
    document.getElementById("start-date-filter").value = "";
    document.getElementById("end-date-filter").value = "";

    displayHistoryRecords(allHistoryRecords);
}

function displayHistoryRecords(records) {
    const tableBody = document.getElementById("history-table-body");
    const historyCount = document.getElementById("history-count");

    historyCount.textContent = `${records.length} records`;

    if (!records || records.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7">No historical records found.</td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = "";

    records.forEach(record => {
        const status = getStatus(record);
        const warningMessage = getWarningMessage(record);

        const row = document.createElement("tr");

        row.innerHTML = `
            <td>${formatTimestamp(record.timestamp)}</td>
            <td>${record.device_name || "Unknown"}</td>
            <td>${record.cpu_usage ?? 0}%</td>
            <td>${record.memory_usage ?? 0}%</td>
            <td>${record.disk_usage ?? 0}%</td>
            <td><span class="status-badge status-${status}">${capitalize(status)}</span></td>
            <td>${warningMessage}</td>
        `;

        tableBody.appendChild(row);
    });
}

function isInsideDateRange(timestamp, startDate, endDate) {
    if (!startDate && !endDate) {
        return true;
    }

    if (!timestamp) {
        return false;
    }

    const recordDate = new Date(timestamp);

    if (isNaN(recordDate)) {
        return false;
    }

    if (startDate) {
        const start = new Date(startDate);
        start.setHours(0, 0, 0, 0);

        if (recordDate < start) {
            return false;
        }
    }

    if (endDate) {
        const end = new Date(endDate);
        end.setHours(23, 59, 59, 999);

        if (recordDate > end) {
            return false;
        }
    }

    return true;
}

function getStatus(record) {
    const status = (record.status || "unknown").toLowerCase();

    if (status === "ok" || status === "healthy" || status === "online") {
        return "online";
    }

    if (status === "warning" || status === "warn" || status === "caution") {
        return "warning";
    }

    if (status === "offline" || status === "error" || status === "failed" || status === "down") {
        return "offline";
    }

    return "unknown";
}

function getWarningMessage(record) {
    if (record.warning_message) {
        return record.warning_message;
    }

    if (record.disk_usage >= 90) {
        return "Disk usage is high";
    }

    if (record.memory_usage >= 85) {
        return "Memory usage is high";
    }

    if (record.cpu_usage >= 85) {
        return "CPU usage is high";
    }

    if (getStatus(record) === "offline") {
        return "Source is offline";
    }

    if (getStatus(record) === "warning") {
        return "Source needs attention";
    }

    return "-";
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