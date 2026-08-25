import { useCallback, useEffect, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Grid from "@mui/material/Grid";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { MetricCard, PIPELINE_STAGE_NAMES } from "components/EflShared";
import { usePipeline } from "context/PipelineContext";
import {
  adminOverview,
  adminRunAllPipeline,
  adminResetAllPipeline,
  rescanDuplicates,
} from "services/endpoints";
import colors from "assets/theme/base/colors";

function fmt(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const n = Number(value);
  if (Math.abs(n) <= 1 && String(value).includes(".")) {
    return n.toFixed(digits);
  }
  return String(value);
}

function stageDotColor(status) {
  switch (status) {
    case "COMPLETE":
      return colors.success.main;
    case "RUNNING":
      return colors.info.main;
    case "FAILED":
      return colors.error.main;
    default:
      return colors.grey[400];
  }
}

function PipelineStagesLine({ stages }) {
  const statusByName = Object.fromEntries(
    (stages || []).map((s) => [s.name, s.status || "PENDING"])
  );

  return (
    <Card sx={{ p: 2.5, mt: 3 }}>
      <MDTypography variant="h6" mb={2}>
        Pipeline stages
      </MDTypography>
      <MDBox sx={{ overflowX: "auto", pb: 1 }}>
        <MDBox
          display="flex"
          alignItems="flex-start"
          position="relative"
          minWidth={`${PIPELINE_STAGE_NAMES.length * 5.25}rem`}
          px={0.5}
        >
          <MDBox
            position="absolute"
            left="2.5rem"
            right="2.5rem"
            top="2.85rem"
            sx={{
              height: "2px",
              backgroundColor: colors.grey[300],
              zIndex: 0,
            }}
          />

          {PIPELINE_STAGE_NAMES.map((name) => {
            const status = statusByName[name] || "PENDING";
            const dot = stageDotColor(status);
            return (
              <MDBox
                key={name}
                flex={1}
                display="flex"
                flexDirection="column"
                alignItems="center"
                position="relative"
                zIndex={1}
                px={0.5}
                minWidth="5rem"
              >
                <MDTypography
                  variant="caption"
                  fontWeight="medium"
                  textAlign="center"
                  sx={{
                    color: colors.text.main,
                    lineHeight: 1.2,
                    minHeight: "2.4rem",
                    display: "flex",
                    alignItems: "flex-end",
                    justifyContent: "center",
                    mb: 1,
                  }}
                >
                  {name}
                </MDTypography>
                <MDBox
                  title={status}
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    backgroundColor: dot,
                    border: `2px solid ${colors.white.main}`,
                    boxShadow: `0 0 0 1px ${dot}`,
                    flexShrink: 0,
                  }}
                />
                <MDTypography
                  variant="caption"
                  mt={0.75}
                  textAlign="center"
                  sx={{
                    color: colors.text.secondary,
                    fontSize: "0.65rem",
                    textTransform: "capitalize",
                  }}
                >
                  {String(status).toLowerCase()}
                </MDTypography>
              </MDBox>
            );
          })}
        </MDBox>
      </MDBox>
    </Card>
  );
}

PipelineStagesLine.propTypes = {
  stages: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string,
      status: PropTypes.string,
    })
  ),
};

PipelineStagesLine.defaultProps = {
  stages: [],
};

function AdminOverview() {
  const { stages, hydrateFromStatus } = usePipeline();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionMsg, setActionMsg] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [resetOpen, setResetOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminOverview();
      setData(res);
      hydrateFromStatus();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load overview";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, [hydrateFromStatus]);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = async (key, fn, successText) => {
    setBusy(key);
    setActionError(null);
    setActionMsg(null);
    try {
      await fn();
      setActionMsg(successText);
      await load();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Action failed";
      setActionError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusy(null);
    }
  };

  const evalSnap = data?.last_evaluation || {};
  const cefrKeys = Object.keys(data?.cefr_distribution || {}).length;

  return (
    <DashboardLayout>
      <DashboardNavbar hideBreadcrumbs />
      <MDBox py={3}>
        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}
        {actionError && (
          <MDBox mb={2}>
            <MDAlert color="error">{actionError}</MDAlert>
          </MDBox>
        )}
        {actionMsg && (
          <MDBox mb={2}>
            <MDAlert color="success">{actionMsg}</MDAlert>
          </MDBox>
        )}

        <Card sx={{ p: 2, mb: 3 }}>
          <MDTypography variant="h6" mb={1.5}>
            Quick actions
          </MDTypography>
          <MDBox display="flex" flexWrap="wrap" gap={1}>
            <MDButton
              variant="gradient"
              color="primary"
              size="small"
              disabled={Boolean(busy)}
              onClick={() =>
                runAction("run", adminRunAllPipeline, "Full pipeline started (background).")
              }
            >
              {busy === "run" ? (
                <MDBox display="inline-flex" alignItems="center" gap={1}>
                  <CircularProgress size={14} color="inherit" />
                  Starting…
                </MDBox>
              ) : (
                "Run Full Pipeline"
              )}
            </MDButton>
            <MDButton
              variant="outlined"
              color="error"
              size="small"
              disabled={Boolean(busy)}
              onClick={() => setResetOpen(true)}
            >
              Reset All Stages
            </MDButton>
            <MDButton
              variant="outlined"
              color="secondary"
              size="small"
              disabled={Boolean(busy)}
              onClick={() =>
                runAction("rescan", rescanDuplicates, "Duplicate index rescan complete.")
              }
            >
              {busy === "rescan" ? (
                <MDBox display="inline-flex" alignItems="center" gap={1}>
                  <CircularProgress size={14} color="inherit" />
                  Rescanning…
                </MDBox>
              ) : (
                "Rescan Duplicates"
              )}
            </MDButton>
          </MDBox>
        </Card>

        {loading && !data && (
          <MDTypography variant="button" color="text">
            Loading overview…
          </MDTypography>
        )}

        {data && (
          <>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="Resources" value={String(data.total_resources ?? "—")} />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard
                  label="FAISS ntotal"
                  value={
                    data.faiss_ntotal === null || data.faiss_ntotal === undefined
                      ? "—"
                      : String(data.faiss_ntotal)
                  }
                />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="Stages complete" value={String(data.stages_complete ?? "—")} />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="Pipeline ready" value={data.pipeline_ready ? "Yes" : "No"} />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard
                  label="Searches (24h)"
                  value={String(data.last_search_count_24h ?? "—")}
                />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="Total searches" value={String(data.total_searches ?? "—")} />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard
                  label="Dupes pending"
                  value={String(data.duplicate_candidates_pending ?? "—")}
                />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="CEFR buckets" value={String(cefrKeys || "—")} />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="Eval P@10" value={fmt(evalSnap.sbert_precision_at_10)} />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="Eval Recall@10" value={fmt(evalSnap.sbert_recall_at_10)} />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="Eval MAP" value={fmt(evalSnap.sbert_map)} />
              </Grid>
              <Grid item xs={6} sm={4} md={3} lg={2}>
                <MetricCard label="Eval F1" value={fmt(evalSnap.sbert_f1_macro)} />
              </Grid>
            </Grid>

            <PipelineStagesLine stages={stages} />
          </>
        )}
      </MDBox>

      <Dialog open={resetOpen} onClose={() => !busy && setResetOpen(false)}>
        <DialogTitle>Reset all pipeline stages?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This clears every stage status back to PENDING. Artefacts on disk are not deleted by
            this call, but the monitor will treat the pipeline as not ready until stages are re-run.
            This cannot be undone from the UI.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <MDButton
            variant="outlined"
            color="secondary"
            size="small"
            disabled={busy === "reset"}
            onClick={() => setResetOpen(false)}
          >
            Cancel
          </MDButton>
          <MDButton
            variant="gradient"
            color="error"
            size="small"
            disabled={busy === "reset"}
            onClick={async () => {
              await runAction("reset", adminResetAllPipeline, "All pipeline stages reset.");
              setResetOpen(false);
            }}
          >
            {busy === "reset" ? "Resetting…" : "Reset All Stages"}
          </MDButton>
        </DialogActions>
      </Dialog>

      <Footer />
    </DashboardLayout>
  );
}

export default AdminOverview;
