
import { useCallback, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDButton from "components/MDButton";
import MDAlert from "components/MDAlert";
import MDProgress from "components/MDProgress";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { StageStatusPill, LiveIndicator } from "components/EflShared";
import { usePipeline } from "context/PipelineContext";
import { runPipelineStage, resetPipelineStage } from "services/endpoints";
import StageArtifactPreview from "layouts/pipeline/StageArtifactPreview";
import colors from "assets/theme/base/colors";

function StageDetailPage({ stageName }) {
  const { stages, connected, hydrateFromStatus } = usePipeline();
  const stage = stages.find((s) => s.name === stageName) || {
    name: stageName,
    status: "PENDING",
    progress_pct: null,
    run_at: null,
    error: null,
  };

  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);

  const status = stage.status || "PENDING";
  const progress =
    stage.progress_pct != null && !Number.isNaN(Number(stage.progress_pct))
      ? Math.max(0, Math.min(100, Number(stage.progress_pct)))
      : status === "RUNNING"
      ? 5
      : status === "COMPLETE"
      ? 100
      : 0;

  const handleRun = useCallback(async () => {
    setBusy(true);
    setActionError(null);
    try {
      await runPipelineStage(stageName);
      await hydrateFromStatus();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Run failed";
      setActionError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusy(false);
    }
  }, [stageName, hydrateFromStatus]);

  const handleResetAndRerun = useCallback(async () => {
    setBusy(true);
    setActionError(null);
    try {
      await resetPipelineStage(stageName);
      await runPipelineStage(stageName);
      await hydrateFromStatus();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Reset/run failed";
      setActionError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setBusy(false);
    }
  }, [stageName, hydrateFromStatus]);

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={1}
          mb={2}
        >
          <MDBox>
            <MDTypography variant="caption" color="text">
              Pipeline Monitor
            </MDTypography>
            <MDTypography variant="h4" fontWeight="bold">
              {stageName}
            </MDTypography>
          </MDBox>
          <LiveIndicator connected={connected} />
        </MDBox>

        <Card sx={{ p: 2, mb: 2 }}>
          <MDBox display="flex" flexWrap="wrap" alignItems="center" gap={2} mb={2}>
            <StageStatusPill status={status} />
            {status === "COMPLETE" && stage.run_at && (
              <MDTypography variant="button" color="text">
                Completed at {stage.run_at}
              </MDTypography>
            )}
          </MDBox>

          {status === "RUNNING" && (
            <MDBox mb={2}>
              <MDProgress color="primary" value={progress} label />
            </MDBox>
          )}

          {status === "FAILED" && stage.error && (
            <MDBox mb={2}>
              <MDAlert color="error">{stage.error}</MDAlert>
            </MDBox>
          )}

          {actionError && (
            <MDBox mb={2}>
              <MDAlert color="error">{actionError}</MDAlert>
            </MDBox>
          )}

          <MDBox display="flex" gap={1} flexWrap="wrap">
            {status === "COMPLETE" ? (
              <MDButton
                variant="gradient"
                color="warning"
                onClick={handleResetAndRerun}
                disabled={busy || status === "RUNNING"}
              >
                {busy ? "Working…" : "Reset & Re-run"}
              </MDButton>
            ) : (
              <MDButton
                variant="gradient"
                color="primary"
                onClick={handleRun}
                disabled={busy || status === "RUNNING" || status === "COMPLETE"}
              >
                {busy ? "Starting…" : "Run this stage"}
              </MDButton>
            )}
            <MDTypography variant="caption" sx={{ color: colors.text.focus, alignSelf: "center" }}>
              Admin JWT required for run / reset
            </MDTypography>
          </MDBox>
        </Card>

        <StageArtifactPreview stageName={stageName} stageStatus={status} />
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

StageDetailPage.propTypes = {
  stageName: PropTypes.oneOf([
    "Discover",
    "Load",
    "Integrate",
    "EDA",
    "Clean",
    "Split",
    "Preprocess",
    "Balance",
    "Train",
    "Evaluate",
    "Explain Global",
    "Explain Local",
    "Explain Quality",
    "Predict",
  ]).isRequired,
};

export default StageDetailPage;
