
import { useEffect, useMemo, useRef, useState } from "react";

import Card from "@mui/material/Card";
import Grid from "@mui/material/Grid";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";
import DefaultLineChart from "examples/Charts/LineCharts/DefaultLineChart";
import VerticalBarChart from "examples/Charts/BarCharts/VerticalBarChart";

import { MetricCard } from "components/EflShared";
import { usePipeline } from "context/PipelineContext";
import { getAnalyticsSummary, getSearchesPerDay } from "services/endpoints";
import colors from "assets/theme/base/colors";

const FILTER_LABELS = [
  { key: "cefr_level", label: "CEFR level" },
  { key: "skill_type", label: "Skill type" },
  { key: "topic_domain", label: "Topic domain" },
];

function activityKey(item) {
  return `${item.type || ""}|${item.timestamp || ""}|${item.query || ""}|${
    item.result_count ?? ""
  }`;
}

function sumFilterCounts(valueMap) {
  if (!valueMap || typeof valueMap !== "object") return 0;
  return Object.values(valueMap).reduce((acc, n) => acc + (Number(n) || 0), 0);
}

function formatDayLabel(isoDate) {
  if (!isoDate) return "";
  const parts = String(isoDate).slice(0, 10).split("-");
  if (parts.length !== 3) return isoDate;
  return `${parts[1]}/${parts[2]}`;
}

function Analytics() {
  const { liveActivityFeed } = usePipeline();

  const [summary, setSummary] = useState(null);
  const [series, setSeries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [baseTotal, setBaseTotal] = useState(0);
  const [liveDelta, setLiveDelta] = useState(0);
  const seenSearchKeys = useRef(new Set());
  const primed = useRef(false);
  const feedRef = useRef(liveActivityFeed);
  feedRef.current = liveActivityFeed;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [sum, perDay] = await Promise.all([getAnalyticsSummary(), getSearchesPerDay(14)]);
        if (cancelled) return;
        setSummary(sum);
        setSeries(Array.isArray(perDay) ? perDay : sum?.searches_per_day || []);
        setBaseTotal(Number(sum?.total_searches) || 0);
        setLiveDelta(0);

        const seed = new Set();
        (feedRef.current || [])
          .filter((item) => item?.type === "search_event")
          .forEach((item) => seed.add(activityKey(item)));
        seenSearchKeys.current = seed;
        primed.current = true;
      } catch (err) {
        if (cancelled) return;
        const detail = err?.response?.data?.detail || err?.message || "Failed to load analytics";
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!primed.current) return;
    let added = 0;
    (liveActivityFeed || [])
      .filter((item) => item?.type === "search_event")
      .forEach((item) => {
        const key = activityKey(item);
        if (!seenSearchKeys.current.has(key)) {
          seenSearchKeys.current.add(key);
          added += 1;
        }
      });
    if (added > 0) {
      setLiveDelta((d) => d + added);
    }
  }, [liveActivityFeed]);

  const liveTotal = baseTotal + liveDelta;

  const lineChart = useMemo(() => {
    const rows = Array.isArray(series) ? series : [];
    return {
      labels: rows.map((r) => formatDayLabel(r.date)),
      datasets: [
        {
          label: "Searches",
          color: "primary",
          data: rows.map((r) => Number(r.count) || 0),
        },
      ],
    };
  }, [series]);

  const filterChart = useMemo(() => {
    const usage = summary?.filter_usage || {};
    return {
      labels: FILTER_LABELS.map((f) => f.label),
      datasets: [
        {
          label: "Times applied",
          color: "info",
          data: FILTER_LABELS.map((f) => sumFilterCounts(usage[f.key])),
        },
      ],
    };
  }, [summary]);

  const topQueries = summary?.top_queries || [];
  const zeroQueries = summary?.zero_result_queries || [];
  const mostViewed = summary?.most_viewed_resources || [];

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
              Search Analytics
            </MDTypography>
            <MDTypography variant="button" color="text">
              Usage insights from live search and resource views
            </MDTypography>
          </MDBox>
          <MDBox minWidth="11rem">
            <MetricCard
              label="Total searches"
              value={loading && !summary ? "…" : String(liveTotal)}
              delta={liveDelta > 0 ? `+${liveDelta} live` : undefined}
              positive
            />
          </MDBox>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        {loading && !summary && (
          <MDTypography variant="button" color="text" mb={2} display="block">
            Loading analytics…
          </MDTypography>
        )}

        <Grid container spacing={3} mb={3}>
          <Grid item xs={12}>
            <DefaultLineChart
              icon={{ color: "primary", component: "timeline" }}
              title="Searches per day"
              description="Last 14 days"
              height="16rem"
              chart={lineChart}
            />
          </Grid>
        </Grid>

        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} md={6}>
            <Card sx={{ height: "100%" }}>
              <MDBox p={2}>
                <MDTypography variant="h6" mb={1}>
                  Top Queries
                </MDTypography>
                {topQueries.length === 0 ? (
                  <MDTypography variant="button" color="text">
                    No search queries logged yet.
                  </MDTypography>
                ) : (
                  <List dense disablePadding>
                    {topQueries.map((row, i) => (
                      <ListItem
                        key={`${row.query}-${i}`}
                        disableGutters
                        secondaryAction={
                          <MDTypography variant="button" fontWeight="bold">
                            {row.count}
                          </MDTypography>
                        }
                        sx={{
                          borderBottom: `1px solid ${colors.grey[300]}`,
                          pr: 6,
                          "&:last-child": { borderBottom: "none" },
                        }}
                      >
                        <ListItemText
                          primary={
                            <MDTypography variant="button" fontWeight="medium">
                              {row.query || "—"}
                            </MDTypography>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </MDBox>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card sx={{ height: "100%" }}>
              <MDBox p={2}>
                <MDTypography variant="h6" mb={0.5}>
                  Zero-Result Queries
                </MDTypography>
                <MDTypography variant="caption" color="text" mb={1} display="block">
                  Queries that returned nothing — signal for missing corpus content
                </MDTypography>
                {zeroQueries.length === 0 ? (
                  <MDTypography variant="button" color="text">
                    No zero-result queries recorded.
                  </MDTypography>
                ) : (
                  <List dense disablePadding>
                    {zeroQueries.map((row, i) => (
                      <ListItem
                        key={`${row.query}-z-${i}`}
                        disableGutters
                        secondaryAction={
                          <MDTypography variant="button" fontWeight="bold">
                            {row.count}
                          </MDTypography>
                        }
                        sx={{
                          borderBottom: `1px solid ${colors.grey[300]}`,
                          pr: 6,
                          "&:last-child": { borderBottom: "none" },
                        }}
                      >
                        <ListItemText
                          primary={
                            <MDTypography variant="button" fontWeight="medium">
                              {row.query || "—"}
                            </MDTypography>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </MDBox>
            </Card>
          </Grid>
        </Grid>

        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} lg={6}>
            <VerticalBarChart
              icon={{ color: "info", component: "filter_list" }}
              title="Filter usage"
              description="How often each Smart Filter was applied"
              height="15rem"
              chart={filterChart}
            />
          </Grid>
          <Grid item xs={12} lg={6}>
            <Card sx={{ height: "100%" }}>
              <MDBox p={2}>
                <MDTypography variant="h6" mb={1.5}>
                  Most Viewed Resources
                </MDTypography>
                {mostViewed.length === 0 ? (
                  <MDTypography variant="button" color="text">
                    No resource views logged yet.
                  </MDTypography>
                ) : (
                  <MDBox sx={{ overflowX: "auto" }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Resource ID</TableCell>
                          <TableCell>Title</TableCell>
                          <TableCell align="right">Views</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {mostViewed.map((row) => (
                          <TableRow key={row.resource_id}>
                            <TableCell>
                              <MDTypography variant="caption" fontWeight="medium">
                                {row.resource_id}
                              </MDTypography>
                            </TableCell>
                            <TableCell>
                              <MDTypography variant="button">
                                {row.title || row.resource_id}
                              </MDTypography>
                            </TableCell>
                            <TableCell align="right">
                              <MDTypography variant="button" fontWeight="bold">
                                {row.views}
                              </MDTypography>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </MDBox>
                )}
              </MDBox>
            </Card>
          </Grid>
        </Grid>
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default Analytics;
