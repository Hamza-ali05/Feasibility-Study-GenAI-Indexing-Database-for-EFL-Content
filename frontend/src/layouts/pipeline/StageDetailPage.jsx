import { useCallback, useEffect, useState } from "react";
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
import {
  runPipelineStage,
  resetPipelineStage,
  getPipelineReproducibility,
} from "services/endpoints";
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
  const [repro, setRepro] = useState(null);
  const [reproError, setReproError] = useState(null);

  const status = stage.status || "PENDING";
  const progress =
    stage.progress_pct != null && !Number.isNaN(Number(stage.progress_pct))
      ? Math.max(0, Math.min(100, Number(stage.progress_pct)))
      : status === "RUNNING"
      ? 5
      : status === "COMPLETE"
      ? 100
      : 0;

  useEffect(() => {
    if (stageName !== "Discover") return undefined;
    let cancelled = false;
    (async () => {
      try {
        const data = await getPipelineReproducibility();
        if (!cancelled) {
          setRepro(data);
          setReproError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setRepro(null);
          const detail = err?.response?.data?.detail || err?.message || "Unavailable";
          setReproError(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [stageName, status]);

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

        {stageName === "Discover" && (
          <Card sx={{ p: 2, mt: 2 }}>
            <MDTypography variant="h6" fontWeight="medium" mb={1}>
              Environment
            </MDTypography>
            {reproError && (
              <MDAlert color="warning">{reproError}</MDAlert>
            )}
            {!reproError && !repro && (
              <MDTypography variant="caption" color="text">
                Loading reproducibility snapshot…
              </MDTypography>
            )}
            {repro && (
              <MDBox
                component="dl"
                sx={{
                  m: 0,
                  display: "grid",
                  gridTemplateColumns: { xs: "1fr", sm: "160px 1fr" },
                  rowGap: 1,
                  columnGap: 2,
                }}
              >
                <MDTypography component="dt" variant="caption" fontWeight="bold" color="text">
                  Python
                </MDTypography>
                <MDTypography component="dd" variant="caption" color="text" sx={{ m: 0 }}>
                  {(repro.python_version || "—").split(" ")[0]}
                </MDTypography>

                <MDTypography component="dt" variant="caption" fontWeight="bold" color="text">
                  Key packages
                </MDTypography>
                <MDTypography component="dd" variant="caption" color="text" sx={{ m: 0 }}>
                  {Object.entries(repro.key_packages || {})
                    .slice(0, 8)
                    .map(([k, v]) => `${k} ${v}`)
                    .join(" · ") || "—"}
                </MDTypography>

                <MDTypography component="dt" variant="caption" fontWeight="bold" color="text">
                  Dataset hash
                </MDTypography>
                <MDTypography
                  component="dd"
                  variant="caption"
                  color="text"
                  sx={{ m: 0, wordBreak: "break-all", fontFamily: "monospace" }}
                >
                  {(repro.dataset && repro.dataset.raw_dir_hash) || "—"}
                </MDTypography>

                <MDTypography component="dt" variant="caption" fontWeight="bold" color="text">
                  Total runtime
                </MDTypography>
                <MDTypography component="dd" variant="caption" color="text" sx={{ m: 0 }}>
                  {repro.runtime && repro.runtime.pipeline_total_seconds != null
                    ? `${Number(repro.runtime.pipeline_total_seconds).toFixed(1)} s`
                    : "— (run pipeline stages to record timings)"}
                </MDTypography>
              </MDBox>
            )}
          </Card>
        )}
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
