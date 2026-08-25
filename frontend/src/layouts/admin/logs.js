import { useCallback, useEffect, useMemo, useState } from "react";

import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import Icon from "@mui/material/Icon";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";
import MDPagination from "components/MDPagination";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { getAdminLogs } from "services/endpoints";
import colors from "assets/theme/base/colors";

const POLL_MS = 5000;
const PAGE_SIZE = 10;
const FETCH_LINES = 100;

const LOGGER_LABELS = {
  api: "API server",
  embedder: "Embedding model",
  vector_store: "Vector index",
  websocket: "Live updates",
  metadata_store: "Resource library",
  duplicates: "Duplicate detection",
  "api.search": "Search",
  "api.resources": "Resources",
  "api.pipeline": "Pipeline",
  "api.admin": "Admin",
  "api.analytics": "Analytics",
  pipeline: "Pipeline",
  auth: "Authentication",
};

const LEVEL_COLOR = {
  DEBUG: "secondary",
  INFO: "info",
  WARNING: "warning",
  WARN: "warning",
  ERROR: "error",
  CRITICAL: "error",
};

const LEVEL_LABEL = {
  DEBUG: "Debug",
  INFO: "Info",
  WARNING: "Warning",
  WARN: "Warning",
  ERROR: "Error",
  CRITICAL: "Critical",
};

const LOG_RE =
  /^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?)\s+\[([A-Z]+)\]\s+([^\s—\-]+)\s*[—\-–]+\s*(.*)$/i;

function formatWhen(rawTs) {
  if (!rawTs) return "";
  const normalized = String(rawTs).replace(",", ".");
  const d = new Date(normalized.includes("T") ? normalized : normalized.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return String(rawTs);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

function humanizeLogger(name) {
  const raw = String(name || "").trim();
  const stripped = raw.replace(/^efl_indexdb\.?/i, "") || "app";
  if (LOGGER_LABELS[stripped]) return LOGGER_LABELS[stripped];
  if (LOGGER_LABELS[stripped.toLowerCase()]) return LOGGER_LABELS[stripped.toLowerCase()];
  return stripped
    .split(".")
    .map((part) => part.replace(/[_-]+/g, " "))
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" · ");
}

function humanizeMessage(message) {
  let text = String(message || "")
    .replace(/\ufeff/g, "")
    .replace(/[—–]/g, "-")
    .replace(/\s+/g, " ")
    .trim();

  if (!text) return "No details recorded.";

  // Soften common technical phrases
  text = text
    .replace(/\bntotal=(\d+)\b/gi, "$1 vectors")
    .replace(/\btombstoned=(\d+)\b/gi, "$1 removed")
    .replace(/\bdim=(\d+)\b/gi, "dimension $1")
    .replace(
      /\bWS connect \((\d+) clients?\)/gi,
      (_, n) => `Live connection opened (${n} client${Number(n) === 1 ? "" : "s"})`
    )
    .replace(/\bWS connect\b/gi, "Live connection opened")
    .replace(/\bWarm-up complete\b/gi, "Startup warm-up finished")
    .replace(/\bWarming SBERT embedder \+ FAISS index…?/gi, "Preparing search model and index…")
    .replace(/\bLoading SentenceTransformer\b/gi, "Loading embedding model")
    .replace(/\bLoaded sentence-transformers\//gi, "Loaded model ")
    .replace(/\bfrom local cache\b/gi, "from local cache")
    .replace(/\bSBERTEmbedder ready\b/gi, "Embedding model ready")
    .replace(/\bFAISSVectorStore ready\b/gi, "Search index ready")
    .replace(/\bLoaded FAISS index\b/gi, "Loaded search index")
    .replace(/\bfrom D:\\[^\s]+/gi, "")
    .replace(/\bfrom \/[\w./-]+/gi, "")
    .replace(/\bsentence-transformers\//gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();

  // Capitalize first letter for friendlier display
  if (text && /^[a-z]/.test(text)) {
    text = text.charAt(0).toUpperCase() + text.slice(1);
  }
  return text;
}

function parseLogLine(line, index) {
  const raw = String(line || "");
  const match = raw.match(LOG_RE);
  if (!match) {
    return {
      id: `raw-${index}`,
      when: "",
      level: "INFO",
      source: "System",
      message: humanizeMessage(raw) || raw || "Empty log line",
      raw,
    };
  }
  const [, ts, level, logger, message] = match;
  return {
    id: `${ts}-${index}-${logger}`,
    when: formatWhen(ts),
    level: String(level || "INFO").toUpperCase(),
    source: humanizeLogger(logger),
    message: humanizeMessage(message),
    raw,
  };
}

function AdminLogs() {
  const [entries, setEntries] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [visible, setVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState === "visible"
  );

  const fetchLogs = useCallback(async () => {
    try {
      const data = await getAdminLogs(FETCH_LINES);
      const lines = Array.isArray(data?.lines) ? data.lines : [];
      // Newest first for a readable activity-style list
      const parsed = lines.map((line, i) => parseLogLine(line, i)).reverse();
      setEntries(parsed);
      setError(null);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load logs";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const onVis = () => {
      setVisible(document.visibilityState === "visible");
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    if (!visible) return undefined;
    fetchLogs();
    const id = setInterval(fetchLogs, POLL_MS);
    return () => clearInterval(id);
  }, [visible, fetchLogs]);

  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE) || 1);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const pageEntries = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return entries.slice(start, start + PAGE_SIZE);
  }, [entries, page]);

  const renderPageButtons = () => {
    const buttons = [];
    const windowSize = 5;
    let start = Math.max(1, page - Math.floor(windowSize / 2));
    let end = Math.min(totalPages, start + windowSize - 1);
    start = Math.max(1, end - windowSize + 1);
    for (let p = start; p <= end; p += 1) {
      buttons.push(
        <MDPagination item key={p} active={p === page} onClick={() => setPage(p)}>
          {p}
        </MDPagination>
      );
    }
    return buttons;
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox
          display="flex"
          flexWrap="wrap"
          justifyContent="space-between"
          alignItems="flex-start"
          gap={2}
          mb={2}
        >
          <MDBox>
            <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
              System logs
            </MDTypography>
            <MDTypography variant="button" color="text">
              Recent activity in plain language · {PAGE_SIZE} per page
            </MDTypography>
          </MDBox>
          <MDButton
            variant="outlined"
            color="secondary"
            size="small"
            onClick={fetchLogs}
            disabled={!visible}
          >
            Refresh now
          </MDButton>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        <Card sx={{ overflow: "hidden" }}>
          <MDBox p={2}>
            {loading && entries.length === 0 ? (
              <MDTypography variant="button" color="text">
                Loading recent logs…
              </MDTypography>
            ) : entries.length === 0 ? (
              <MDTypography variant="button" color="text">
                No log entries yet.
              </MDTypography>
            ) : (
              <MDBox display="flex" flexDirection="column" gap={1.25}>
                {pageEntries.map((entry) => (
                  <MDBox
                    key={entry.id}
                    px={1.75}
                    py={1.35}
                    borderRadius="md"
                    sx={{
                      backgroundColor: colors.grey[100],
                      border: `1px solid ${colors.grey[300]}`,
                    }}
                  >
                    <MDBox display="flex" flexWrap="wrap" alignItems="center" gap={1} mb={0.75}>
                      <Chip
                        size="small"
                        color={LEVEL_COLOR[entry.level] || "default"}
                        label={LEVEL_LABEL[entry.level] || entry.level}
                        sx={{ height: 22 }}
                      />
                      <MDTypography variant="caption" fontWeight="medium" color="text">
                        {entry.source}
                      </MDTypography>
                      {entry.when && (
                        <MDTypography variant="caption" color="text" sx={{ ml: "auto" }}>
                          {entry.when}
                        </MDTypography>
                      )}
                    </MDBox>
                    <MDTypography variant="button" fontWeight="regular" sx={{ lineHeight: 1.45 }}>
                      {entry.message}
                    </MDTypography>
                  </MDBox>
                ))}
              </MDBox>
            )}
          </MDBox>

          {!loading && entries.length > 0 && (
            <MDBox
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              flexWrap="wrap"
              gap={1}
              p={2}
              sx={{ borderTop: `1px solid ${colors.grey[300]}` }}
            >
              <MDTypography variant="caption" color="text">
                Page {page} of {totalPages} · showing {pageEntries.length} of {entries.length}
              </MDTypography>
              <MDPagination variant="gradient" color="primary">
                <MDPagination
                  item
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  <Icon>chevron_left</Icon>
                </MDPagination>
                {renderPageButtons()}
                <MDPagination
                  item
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  <Icon>chevron_right</Icon>
                </MDPagination>
              </MDPagination>
            </MDBox>
          )}
        </Card>
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default AdminLogs;
