import { useCallback, useEffect, useMemo, useState } from "react";

import Card from "@mui/material/Card";
import Grid from "@mui/material/Grid";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDBadge from "components/MDBadge";
import MDAlert from "components/MDAlert";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";
import VerticalBarChart from "examples/Charts/BarCharts/VerticalBarChart";

import { LiveIndicator, MetricCard } from "components/EflShared";

import { usePipeline } from "context/PipelineContext";
import { getDashboardSummary } from "services/endpoints";
import colors from "assets/theme/base/colors";

const CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"];
const POLL_MS = 5000;

function formatMetric(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const n = Number(value);
  if (n <= 1 && n >= 0) {
    return n.toFixed(digits);
  }
  return String(n);
}

function relativeTime(iso, nowMs) {
  if (!iso) return "";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "";
  const sec = Math.max(0, Math.floor((nowMs - then) / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 48) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  return `${days}d ago`;
}

function Dashboard() {
  const {
    connected,
    stagesComplete,
    pipelineReady,
    setPipelineReady,
    liveActivityFeed,
    mergeSummaryActivity,
    hydrateFromStatus,
  } = usePipeline();

  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const fetchSummary = useCallback(async () => {
    try {
      const data = await getDashboardSummary();
      setSummary(data);
      setError(null);
      if (typeof data.pipeline_ready === "boolean") {
        setPipelineReady(data.pipeline_ready);
      }
      mergeSummaryActivity(data.recent_activity);
      await hydrateFromStatus();
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        "Could not load dashboard summary. Is the API running?";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
  }, [mergeSummaryActivity, setPipelineReady, hydrateFromStatus]);

  useEffect(() => {
    fetchSummary();

    const poll = setInterval(fetchSummary, POLL_MS);
    return () => clearInterval(poll);
  }, [fetchSummary]);

  useEffect(() => {
    const tick = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);

  const ready =
    typeof pipelineReady === "boolean" ? pipelineReady : Boolean(summary?.pipeline_ready);

  const cefrChart = useMemo(() => {
    const dist = summary?.cefr_distribution || {};
    return {
      labels: CEFR_ORDER,
      datasets: [
        {
          label: "Resources",
          color: "primary",
          data: CEFR_ORDER.map((lvl) => Number(dist[lvl] || 0)),
        },
      ],
    };
  }, [summary]);

  const evalSnapshot = summary?.last_evaluation;
  const hasEval = Boolean(evalSnapshot);

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={1.5}
          mb={3}
          px={0.5}
        >
          <MDBox>
            <MDTypography variant="h4" fontWeight="bold">
              Dashboard
            </MDTypography>
            <MDTypography variant="button" color="text">
              Live pipeline and database monitoring
            </MDTypography>
          </MDBox>
          <MDBox display="flex" alignItems="center" gap={1.5}>
            <LiveIndicator connected={connected} />
            <MDBadge
              badgeContent={ready ? "Pipeline Ready" : "Pipeline Not Ready"}
              color={ready ? "success" : "warning"}
              variant="contained"
              container
            />
          </MDBox>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error" dismissible>
              {error}
            </MDAlert>
          </MDBox>
        )}

        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} sm={6} lg={3}>
            <MetricCard label="Total Resources" value={String(summary?.total_resources ?? "—")} />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <MetricCard label="Stages Complete" value={`${stagesComplete}/14`} />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <MetricCard
              label="FAISS Vectors Indexed"
              value={
                summary?.faiss_ntotal === null || summary?.faiss_ntotal === undefined
                  ? "—"
                  : String(summary.faiss_ntotal)
              }
            />
          </Grid>
          <Grid item xs={12} sm={6} lg={3}>
            <MetricCard
              label="Searches (Last 24h)"
              value={String(summary?.last_search_count_24h ?? "—")}
            />
          </Grid>
        </Grid>

        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} lg={7}>
            <VerticalBarChart
              icon={{ color: "primary", component: "bar_chart" }}
              title="CEFR distribution"
              description={
                Object.keys(summary?.cefr_distribution || {}).length
                  ? "From EDA stage report"
                  : "Run the EDA stage to populate CEFR distribution"
              }
              height="16.5rem"
              chart={cefrChart}
            />
          </Grid>
          <Grid item xs={12} lg={5}>
            <Card sx={{ height: "100%" }}>
              <MDBox p={2}>
                <MDTypography variant="h6" mb={1.5}>
                  Recent Activity
                </MDTypography>
                {liveActivityFeed.length === 0 ? (
                  <MDTypography variant="button" color="text">
                    No recent activity yet. Pipeline events, searches, and duplicate flags will
                    appear here live.
                  </MDTypography>
                ) : (
                  <MDBox
                    component="ul"
                    m={0}
                    p={0}
                    sx={{ listStyle: "none", maxHeight: "16rem", overflowY: "auto" }}
                  >
                    {liveActivityFeed.map((item) => (
                      <MDBox
                        component="li"
                        key={`${item.timestamp}-${item.message}`}
                        display="flex"
                        justifyContent="space-between"
                        alignItems="flex-start"
                        py={1}
                        sx={{
                          borderBottom: `1px solid ${colors.grey[300]}`,
                          "&:last-child": { borderBottom: "none" },
                        }}
                      >
                        <MDTypography
                          variant="caption"
                          fontWeight="medium"
                          sx={{ color: colors.text.main, pr: 1 }}
                        >
                          {item.message}
                        </MDTypography>
                        <MDTypography
                          variant="caption"
                          sx={{ color: colors.text.focus, whiteSpace: "nowrap" }}
                        >
                          {relativeTime(item.timestamp, nowMs)}
                        </MDTypography>
                      </MDBox>
                    ))}
                  </MDBox>
                )}
              </MDBox>
            </Card>
          </Grid>
        </Grid>

        <MDBox mb={1}>
          <MDTypography variant="h6" mb={1.5}>
            Latest evaluation
          </MDTypography>
          {!hasEval ? (
            <MDAlert color="info">Run the Evaluate stage to see metrics here</MDAlert>
          ) : (
            <Grid container spacing={3}>
              <Grid item xs={12} sm={6} lg={3}>
                <MetricCard
                  label="Precision@10"
                  value={formatMetric(evalSnapshot.sbert_precision_at_10)}
                />
              </Grid>
              <Grid item xs={12} sm={6} lg={3}>
                <MetricCard
                  label="Recall@10"
                  value={formatMetric(evalSnapshot.sbert_recall_at_10)}
                />
              </Grid>
              <Grid item xs={12} sm={6} lg={3}>
                <MetricCard label="MAP" value={formatMetric(evalSnapshot.sbert_map)} />
              </Grid>
              <Grid item xs={12} sm={6} lg={3}>
                <MetricCard label="F1" value={formatMetric(evalSnapshot.sbert_f1_macro)} />
              </Grid>
            </Grid>
          )}
        </MDBox>
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default Dashboard;
