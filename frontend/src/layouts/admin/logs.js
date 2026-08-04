import { useCallback, useEffect, useRef, useState } from "react";

import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { getAdminLogs } from "services/endpoints";
import colors from "assets/theme/base/colors";

const POLL_MS = 5000;

function AdminLogs() {
  const [lines, setLines] = useState([]);
  const [path, setPath] = useState("logs/efl_indexdb.log");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState === "visible"
  );
  const panelRef = useRef(null);
  const stickBottom = useRef(true);

  const fetchLogs = useCallback(async () => {
    try {
      const data = await getAdminLogs(200);
      setLines(Array.isArray(data?.lines) ? data.lines : []);
      if (data?.path) setPath(data.path);
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

  useEffect(() => {
    if (!stickBottom.current || !panelRef.current) return;
    panelRef.current.scrollTop = panelRef.current.scrollHeight;
  }, [lines]);

  const onScroll = () => {
    const el = panelRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    stickBottom.current = nearBottom;
  };

  const consoleBg = colors.grey[900];
  const consoleFg = colors.grey[300];
  const consoleMuted = colors.grey[500];

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox
          display="flex"
          flexWrap="wrap"
          alignItems="flex-start"
          justifyContent="space-between"
          gap={2}
          mb={2}
        >
          <MDBox>
            <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
              Admin Logs
            </MDTypography>
            <MDTypography variant="button" color="text">
              Live tail of <code>{path}</code>
              {!visible ? " · polling paused (tab hidden)" : " · refreshing every 5s"}
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
          <MDBox
            ref={panelRef}
            onScroll={onScroll}
            px={2}
            py={1.5}
            sx={{
              backgroundColor: consoleBg,
              color: consoleFg,
              fontFamily:
                'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
              fontSize: "0.75rem",
              lineHeight: 1.55,
              maxHeight: "70vh",
              minHeight: "20rem",
              overflowY: "auto",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {loading && lines.length === 0 ? (
              <MDTypography variant="caption" sx={{ color: consoleMuted, fontFamily: "inherit" }}>
                Loading log tail…
              </MDTypography>
            ) : lines.length === 0 ? (
              <MDTypography variant="caption" sx={{ color: consoleMuted, fontFamily: "inherit" }}>
                (empty log file)
              </MDTypography>
            ) : (
              lines.map((line, i) => (
                <MDBox
                  key={`${i}-${String(line).slice(0, 24)}`}
                  component="div"
                  sx={{ color: consoleFg }}
                >
                  {line}
                </MDBox>
              ))
            )}
          </MDBox>
        </Card>
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default AdminLogs;
