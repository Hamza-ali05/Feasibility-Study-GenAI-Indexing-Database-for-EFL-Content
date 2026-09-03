import { useCallback, useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";
import Grid from "@mui/material/Grid";

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
import { API_URL } from "services/apiClient";
import StageArtifactPreview from "layouts/pipeline/StageArtifactPreview";
import colors from "assets/theme/base/colors";

const FIG = "/static/research-reports/figures";
const METRICS = "/static/research-reports/metrics";
const BENCH = "/static/research-reports/benchmark";
const EDA = "/static/eda_plots";
const EXPLAIN = "/static/explain";

/**
 * Pictures shown on each pipeline stage page when the files exist.
 * Missing images are hidden automatically (onError).
 */
const STAGE_FIGURES = {
  Discover: [
    {
      id: "pipeline_flowchart",
      title: "Pipeline Flowchart",
      path: `${FIG}/pipeline_flowchart.png`,
    },
    { id: "data_flow_diagram", title: "Data Flow Diagram", path: `${FIG}/data_flow_diagram.png` },
    {
      id: "system_architecture",
      title: "System Architecture",
      path: `${FIG}/system_architecture.png`,
    },
  ],
  Load: [
    { id: "data_flow_diagram", title: "Data Flow Diagram", path: `${FIG}/data_flow_diagram.png` },
    {
      id: "pipeline_flowchart",
      title: "Pipeline Flowchart",
      path: `${FIG}/pipeline_flowchart.png`,
    },
  ],
  Integrate: [
    { id: "data_flow_diagram", title: "Data Flow Diagram", path: `${FIG}/data_flow_diagram.png` },
    { id: "component_diagram", title: "Component Diagram", path: `${FIG}/component_diagram.png` },
  ],
  EDA: [
    { id: "cefr_bar", title: "CEFR Distribution", path: `${EDA}/cefr_bar.png` },
    { id: "skill_pie", title: "Skill Types", path: `${EDA}/skill_pie.png` },
    { id: "topic_bar", title: "Topic Domains", path: `${EDA}/topic_bar.png` },
    { id: "text_length_hist", title: "Text Length", path: `${EDA}/text_length_hist.png` },
  ],
  Clean: [
    {
      id: "pipeline_flowchart",
      title: "Pipeline Flowchart",
      path: `${FIG}/pipeline_flowchart.png`,
    },
    { id: "data_flow_diagram", title: "Data Flow Diagram", path: `${FIG}/data_flow_diagram.png` },
  ],
  Split: [
    {
      id: "pipeline_flowchart",
      title: "Pipeline Flowchart",
      path: `${FIG}/pipeline_flowchart.png`,
    },
  ],
  Preprocess: [
    {
      id: "embedding_pipeline",
      title: "Embedding Pipeline",
      path: `${FIG}/embedding_pipeline.png`,
    },
    {
      id: "pipeline_flowchart",
      title: "Pipeline Flowchart",
      path: `${FIG}/pipeline_flowchart.png`,
    },
  ],
  Balance: [
    {
      id: "pipeline_flowchart",
      title: "Pipeline Flowchart",
      path: `${FIG}/pipeline_flowchart.png`,
    },
  ],
  Train: [
    {
      id: "cefr_classification_flow",
      title: "CEFR Classification Flow",
      path: `${FIG}/cefr_classification_flow.png`,
    },
    {
      id: "embedding_pipeline",
      title: "Embedding Pipeline",
      path: `${FIG}/embedding_pipeline.png`,
    },
    {
      id: "confusion_matrix_sbert",
      title: "Confusion Matrix (SBERT)",
      path: `${METRICS}/confusion_matrix_sbert.png`,
    },
    {
      id: "confusion_matrix_tfidf",
      title: "Confusion Matrix (TF-IDF)",
      path: `${METRICS}/confusion_matrix_tfidf.png`,
    },
  ],
  Evaluate: [
    {
      id: "cefr_classification_flow",
      title: "CEFR Classification Flow",
      path: `${FIG}/cefr_classification_flow.png`,
    },
    {
      id: "retrieval_metrics",
      title: "Retrieval Metrics",
      path: `${METRICS}/retrieval_metrics.png`,
    },
    {
      id: "classification_metrics",
      title: "Classification Metrics",
      path: `${METRICS}/classification_metrics.png`,
    },
    {
      id: "retrieval_comparison",
      title: "Retrieval Comparison",
      path: `${BENCH}/retrieval_comparison.png`,
    },
    {
      id: "classification_comparison",
      title: "Classification Comparison",
      path: `${BENCH}/classification_comparison.png`,
    },
    {
      id: "confusion_matrices",
      title: "Confusion Matrices",
      path: `${BENCH}/confusion_matrices.png`,
    },
  ],
  "Explain Global": [
    { id: "global_shap_bar", title: "Global SHAP (bar)", path: `${EXPLAIN}/global_shap_bar.png` },
    {
      id: "global_shap_beeswarm",
      title: "Global SHAP (beeswarm)",
      path: `${EXPLAIN}/global_shap_beeswarm.png`,
    },
    {
      id: "explainability_summary",
      title: "Explainability Summary",
      path: `${METRICS}/explainability_summary.png`,
    },
  ],
  "Explain Local": [
    {
      id: "explainability_summary",
      title: "Explainability Summary",
      path: `${METRICS}/explainability_summary.png`,
    },
    {
      id: "cefr_classification_flow",
      title: "CEFR Classification Flow",
      path: `${FIG}/cefr_classification_flow.png`,
    },
  ],
  "Explain Quality": [
    {
      id: "explainability_summary",
      title: "Explainability Summary",
      path: `${METRICS}/explainability_summary.png`,
    },
  ],
  Predict: [
    { id: "search_sequence", title: "Search Sequence", path: `${FIG}/search_sequence.png` },
    { id: "rag_sequence", title: "RAG Sequence", path: `${FIG}/rag_sequence.png` },
    {
      id: "cefr_classification_flow",
      title: "CEFR Classification Flow",
      path: `${FIG}/cefr_classification_flow.png`,
    },
  ],
};

function figureUrl(path, cacheKey) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const base = (API_URL || "http://localhost:8000").replace(/\/$/, "");
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
  if (!cacheKey) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${encodeURIComponent(cacheKey)}`;
}

function StageFiguresCard({ stageName }) {
  const candidates = useMemo(() => STAGE_FIGURES[stageName] || [], [stageName]);
  const [ok, setOk] = useState({});
  const [bad, setBad] = useState({});
  const cacheKey = useMemo(() => String(Date.now()), [stageName]);

  useEffect(() => {
    setOk({});
    setBad({});
  }, [stageName]);

  const visible = candidates.filter((img) => ok[img.id]);

  if (!candidates.length) return null;

  return (
    <>
      {candidates.map((img) =>
        ok[img.id] || bad[img.id] ? null : (
          <BoxProbe
            key={`probe-${img.id}`}
            src={figureUrl(img.path, cacheKey)}
            onOk={() => setOk((prev) => ({ ...prev, [img.id]: true }))}
            onBad={() => setBad((prev) => ({ ...prev, [img.id]: true }))}
          />
        )
      )}

      {visible.length > 0 && (
        <Card sx={{ p: 2, mt: 2 }}>
          <MDTypography variant="h6" fontWeight="medium" mb={1.5}>
            Stage figures
          </MDTypography>
          <Grid container spacing={2}>
            {visible.map((img) => (
              <Grid item xs={12} md={visible.length === 1 ? 12 : 6} key={img.id}>
                <MDTypography variant="caption" color="text" mb={0.5} display="block">
                  {img.title}
                </MDTypography>
                <MDBox
                  component="img"
                  src={figureUrl(img.path, cacheKey)}
                  alt={img.title}
                  sx={{
                    width: "100%",
                    maxHeight: 420,
                    objectFit: "contain",
                    background: "#F9F8F5",
                    border: `1px solid ${colors.grey?.[200] || "#D3D1C7"}`,
                    borderRadius: 1,
                  }}
                />
              </Grid>
            ))}
          </Grid>
        </Card>
      )}
    </>
  );
}

function BoxProbe({ src, onOk, onBad }) {
  return (
    <img
      src={src}
      alt=""
      onLoad={onOk}
      onError={onBad}
      style={{ position: "absolute", width: 0, height: 0, opacity: 0, pointerEvents: "none" }}
    />
  );
}

BoxProbe.propTypes = {
  src: PropTypes.string.isRequired,
  onOk: PropTypes.func.isRequired,
  onBad: PropTypes.func.isRequired,
};

StageFiguresCard.propTypes = {
  stageName: PropTypes.string.isRequired,
};

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
          </MDBox>
        </Card>

        <StageArtifactPreview stageName={stageName} stageStatus={status} />

        <StageFiguresCard stageName={stageName} />
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
