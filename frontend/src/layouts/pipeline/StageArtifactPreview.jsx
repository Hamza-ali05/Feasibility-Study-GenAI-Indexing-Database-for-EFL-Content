import { useCallback, useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";
import { Link as RouterLink } from "react-router-dom";

import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Card from "@mui/material/Card";
import Skeleton from "@mui/material/Skeleton";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";
import MDInput from "components/MDInput";

import VerticalBarChart from "examples/Charts/BarCharts/VerticalBarChart";
import PieChart from "examples/Charts/PieChart";
import { MetricCard, CefrBadge, SimilarityBar } from "components/EflShared";
import { SKILL_TYPES, TOPIC_DOMAINS } from "assets/theme/base/eflLabels";

import { API_URL } from "services/apiClient";
import {
  getPipelineArtifact,
  getMetrics,
  getExplainGlobal,
  getExplainLocal,
  getExplainQuality,
  searchResources,
} from "services/endpoints";
import colors from "assets/theme/base/colors";

const CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"];

function staticUrl(path, cacheKey) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const base = (API_URL || "http://localhost:8000").replace(/\/$/, "");
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
  if (!cacheKey) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${encodeURIComponent(cacheKey)}`;
}

/** Column widths that keep Path/File-like first columns readable. */
function columnWidths(columns) {
  const n = columns.length || 1;
  if (n === 1) return ["100%"];
  if (n === 2) return ["70%", "30%"];
  if (n === 3) return ["58%", "21%", "21%"];
  if (n === 4) return ["46%", "14%", "20%", "20%"];
  const rest = Math.floor(55 / (n - 1));
  return [`${100 - rest * (n - 1)}%`, ...Array(n - 1).fill(`${rest}%`)];
}

/**
 * Soft UI sets MuiTableHead to display:block for DataTable flex layouts,
 * which breaks normal HTML tables. Use CSS grid so every pipeline stage
 * keeps headers and cells in the same columns.
 */
function SimpleTable({ columns, rows }) {
  const widths = columnWidths(columns);
  const template = widths.join(" ");
  const minWidth = Math.max(320, columns.length * 140);

  return (
    <MDBox sx={{ width: "100%", overflowX: "auto" }}>
      <MDBox
        role="table"
        sx={{
          width: "100%",
          minWidth,
        }}
      >
        <MDBox
          role="row"
          sx={{
            display: "grid",
            gridTemplateColumns: template,
            alignItems: "end",
            borderBottom: `1px solid ${colors.grey[300]}`,
          }}
        >
          {columns.map((c) => (
            <MDBox
              key={c}
              role="columnheader"
              px={1.5}
              py={1}
              sx={{
                fontSize: "0.75rem",
                fontWeight: 700,
                color: colors.text?.main || "#7b809a",
                whiteSpace: "nowrap",
              }}
            >
              {c}
            </MDBox>
          ))}
        </MDBox>

        {rows.map((row, i) => (
          <MDBox
            key={i}
            role="row"
            sx={{
              display: "grid",
              gridTemplateColumns: template,
              alignItems: "start",
              borderBottom: `1px solid ${colors.grey[200]}`,
            }}
          >
            {row.map((cell, j) => (
              <MDBox
                key={j}
                role="cell"
                px={1.5}
                py={1}
                sx={{
                  fontSize: "0.875rem",
                  color: colors.dark?.main || "#344767",
                  wordBreak: "break-word",
                  overflowWrap: "anywhere",
                }}
              >
                {cell}
              </MDBox>
            ))}
          </MDBox>
        ))}
      </MDBox>
    </MDBox>
  );
}

SimpleTable.propTypes = {
  columns: PropTypes.arrayOf(PropTypes.string).isRequired,
  rows: PropTypes.arrayOf(PropTypes.array).isRequired,
};

function useArtifact(slug, enabled) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    if (!enabled || !slug) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getPipelineArtifact(slug);
      setData(res);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load artefact";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [slug, enabled]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, loading, error, reload };
}

function ArtifactShell({ loading, error, children }) {
  if (loading) {
    return (
      <MDBox>
        <Skeleton height={32} />
        <Skeleton height={120} sx={{ mt: 1 }} />
      </MDBox>
    );
  }
  if (error) {
    return <MDAlert color="info">{error}</MDAlert>;
  }
  return children;
}

ArtifactShell.propTypes = {
  loading: PropTypes.bool,
  error: PropTypes.string,
  children: PropTypes.node,
};

function DiscoverArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("discover", enabled);
  const files = data?.files || [];
  return (
    <ArtifactShell loading={loading} error={error}>
      <MDTypography variant="button" color="text" mb={1} display="block">
        {files.length} discovered file(s)
      </MDTypography>
      <SimpleTable
        columns={["Path", "Ext", "Size (bytes)", "Rows est."]}
        rows={files.map((f) => [
          f.path || "—",
          f.ext || "—",
          f.size_bytes ?? "—",
          f.rows_estimate ?? "—",
        ])}
      />
    </ArtifactShell>
  );
}

function LoadArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("load", enabled);
  const files = data?.files || [];
  return (
    <ArtifactShell loading={loading} error={error}>
      <MDTypography variant="button" mb={1} display="block">
        Total rows: {data?.total_rows ?? "—"}
      </MDTypography>
      <SimpleTable
        columns={["File", "Rows", "Status"]}
        rows={files.map((f) => [
          f.path || f.filename || "—",
          f.rows ?? f.n_rows ?? "—",
          f.status || "—",
        ])}
      />
    </ArtifactShell>
  );
}

function IntegrateArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("integrate", enabled);
  const nulls = data?.null_counts_per_column || {};
  const total = Number(data?.total_rows) || 0;
  const rows = Object.entries(nulls).map(([col, n]) => {
    const count = Number(n) || 0;
    const rate = total ? ((count / total) * 100).toFixed(1) : "—";
    return [col, count, `${rate}%`];
  });
  return (
    <ArtifactShell loading={loading} error={error}>
      <MDTypography variant="button" mb={1} display="block">
        Total rows: {total} · duplicates dropped: {data?.duplicate_resource_ids_dropped ?? "—"}
      </MDTypography>
      <SimpleTable columns={["Column", "Null count", "Null rate"]} rows={rows} />
    </ArtifactShell>
  );
}

function EdaArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("eda", enabled);
  const plots = data?.plot_urls || {};
  const cacheKey = data?.run_at || "";

  const cefrChart = useMemo(() => {
    const dist = data?.cefr_distribution || {};
    return {
      labels: CEFR_ORDER,
      datasets: [
        {
          label: "Resources",
          color: "primary",
          data: CEFR_ORDER.map((l) => Number(dist[l] || 0)),
        },
      ],
    };
  }, [data?.cefr_distribution]);

  const skillChart = useMemo(() => {
    const dist = data?.skill_distribution || {};
    const labels = SKILL_TYPES.filter((l) => Number(dist[l] || 0) > 0);
    const palette = ["info", "primary", "success", "warning", "error", "secondary"];
    return {
      labels,
      datasets: {
        label: "Skill types",
        backgroundColors: labels.map((_, i) => palette[i % palette.length]),
        data: labels.map((l) => Number(dist[l] || 0)),
      },
    };
  }, [data?.skill_distribution]);

  const topicChart = useMemo(() => {
    const dist = data?.topic_distribution || {};
    return {
      labels: TOPIC_DOMAINS,
      datasets: [
        {
          label: "Resources",
          color: "primary",
          data: TOPIC_DOMAINS.map((l) => Number(dist[l] || 0)),
        },
      ],
    };
  }, [data?.topic_distribution]);

  const skillTotal = (skillChart.datasets?.data || []).reduce((sum, n) => sum + Number(n || 0), 0);
  const topicTotal = (topicChart.datasets?.[0]?.data || []).reduce(
    (sum, n) => sum + Number(n || 0),
    0
  );

  return (
    <ArtifactShell loading={loading} error={error}>
      <MDTypography variant="button" mb={1.5} display="block">
        Total resources: {data?.total_resources ?? "—"}
      </MDTypography>
      <MDBox display="grid" gap={2} sx={{ gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
        <VerticalBarChart title="CEFR distribution" height="16rem" chart={cefrChart} />
        {skillTotal > 0 ? (
          <PieChart title="Skill types" height="16rem" chart={skillChart} />
        ) : (
          <Card sx={{ p: 2 }}>
            <MDTypography variant="h6">Skill types</MDTypography>
            <MDTypography variant="button" color="text">
              No skill_type values in the EDA report yet.
            </MDTypography>
          </Card>
        )}
        <VerticalBarChart title="Topic domains" height="16rem" chart={topicChart} />
        {plots.text_length_hist ? (
          <Card sx={{ p: 1 }}>
            <MDTypography variant="caption" color="text" mb={0.5} display="block">
              Text length
            </MDTypography>
            <MDBox
              component="img"
              src={staticUrl(plots.text_length_hist, cacheKey)}
              alt="Text length"
              sx={{ width: "100%", height: "auto", borderRadius: 1 }}
            />
          </Card>
        ) : null}
      </MDBox>
      {topicTotal === 0 && (
        <MDTypography variant="caption" color="text" mt={1} display="block">
          Topic domain counts are zero — re-run EDA after skill/topic labels are attached.
        </MDTypography>
      )}
    </ArtifactShell>
  );
}

function CleanArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("clean", enabled);
  return (
    <ArtifactShell loading={loading} error={error}>
      <SimpleTable
        columns={["Metric", "Value"]}
        rows={[
          ["Rows before", data?.rows_before ?? "—"],
          ["Rows after", data?.rows_after ?? "—"],
          ["Rows dropped", data?.rows_dropped ?? "—"],
        ]}
      />
    </ArtifactShell>
  );
}

function SplitArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("split", enabled);
  const chart = useMemo(() => {
    const dist = data?.cefr_distribution_per_split || {};
    const labels = CEFR_ORDER;
    return {
      labels,
      datasets: [
        {
          label: "Train",
          color: "primary",
          data: labels.map((l) => Number((dist.train || {})[l] || 0)),
        },
        {
          label: "Val",
          color: "info",
          data: labels.map((l) => Number((dist.val || {})[l] || 0)),
        },
        {
          label: "Test",
          color: "success",
          data: labels.map((l) => Number((dist.test || {})[l] || 0)),
        },
      ],
    };
  }, [data?.cefr_distribution_per_split]);

  return (
    <ArtifactShell loading={loading} error={error}>
      <SimpleTable
        columns={["Split", "Size"]}
        rows={[
          ["Train", data?.train_n ?? "—"],
          ["Val", data?.val_n ?? "—"],
          ["Test", data?.test_n ?? "—"],
        ]}
      />
      <MDBox mt={2}>
        <VerticalBarChart title="CEFR per split" height="14rem" chart={chart} />
      </MDBox>
    </ArtifactShell>
  );
}

function PreprocessArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("preprocess", enabled);
  return (
    <ArtifactShell loading={loading} error={error}>
      <SimpleTable
        columns={["Field", "Value"]}
        rows={[
          ["Model", data?.model_name ?? "—"],
          ["Embedding dim", data?.embedding_dim ?? "—"],
          ["Train n", data?.train_n ?? "—"],
          ["Val n", data?.val_n ?? "—"],
          ["Test n", data?.test_n ?? "—"],
          ["Duration (s)", data?.duration_seconds ?? "—"],
        ]}
      />
    </ArtifactShell>
  );
}

function BalanceArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("balance", enabled);
  const before = data?.class_counts_before || {};
  const after = data?.class_counts_after || {};
  const chart = {
    labels: CEFR_ORDER,
    datasets: [
      {
        label: "Before",
        color: "warning",
        data: CEFR_ORDER.map((l) => Number(before[l] || 0)),
      },
      {
        label: "After",
        color: "success",
        data: CEFR_ORDER.map((l) => Number(after[l] || 0)),
      },
    ],
  };
  return (
    <ArtifactShell loading={loading} error={error}>
      <MDTypography variant="button" color="text" mb={1} display="block">
        Strategy: {data?.strategy_applied ?? "—"} · imbalance before:{" "}
        {data?.imbalance_ratio_before ?? "—"}
      </MDTypography>
      <VerticalBarChart title="Class counts before / after" height="14rem" chart={chart} />
    </ArtifactShell>
  );
}

function TrainArtifact({ enabled }) {
  const { data, loading, error } = useArtifact("train", enabled);
  return (
    <ArtifactShell loading={loading} error={error}>
      <SimpleTable
        columns={["Metric", "Value"]}
        rows={[
          ["SBERT train accuracy", data?.classifier_train_accuracy ?? "—"],
          ["TF-IDF train accuracy", data?.tfidf_train_accuracy ?? "—"],
          ["FAISS ntotal", data?.faiss_ntotal ?? "—"],
          ["Duplicate candidates", data?.duplicate_candidates_found ?? "—"],
        ]}
      />
    </ArtifactShell>
  );
}

function EvaluateArtifact({ enabled }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await getMetrics();
        if (!cancelled) setData(res);
      } catch (err) {
        if (!cancelled) {
          const detail = err?.response?.data?.detail || err?.message || "Metrics unavailable";
          setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const sbert = data?.retrieval?.sbert || {};
  const clf = data?.classification?.sbert || {};

  return (
    <ArtifactShell loading={loading} error={error}>
      <MDBox mb={2}>
        <MDButton
          component={RouterLink}
          to="/metrics"
          variant="outlined"
          color="primary"
          size="small"
        >
          Open full Metrics page
        </MDButton>
      </MDBox>
      <MDBox
        display="grid"
        gap={2}
        sx={{ gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" } }}
      >
        <MetricCard
          label="Precision@10"
          value={sbert.precision_at_10 != null ? Number(sbert.precision_at_10).toFixed(3) : "—"}
        />
        <MetricCard
          label="Recall@10"
          value={sbert.recall_at_10 != null ? Number(sbert.recall_at_10).toFixed(3) : "—"}
        />
        <MetricCard label="MAP" value={sbert.map != null ? Number(sbert.map).toFixed(3) : "—"} />
        <MetricCard
          label="F1 macro"
          value={clf.f1_macro != null ? Number(clf.f1_macro).toFixed(3) : "—"}
        />
      </MDBox>
    </ArtifactShell>
  );
}

function ExplainGlobalArtifact({ enabled }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await getExplainGlobal();
        if (!cancelled) setData(res);
      } catch (err) {
        if (!cancelled) {
          const detail =
            err?.response?.data?.detail || err?.message || "Explain Global unavailable";
          setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const features = data?.top_features || [];

  return (
    <ArtifactShell loading={loading} error={error}>
      <MDBox
        display="grid"
        gap={2}
        mb={2}
        sx={{ gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}
      >
        <Card sx={{ p: 1 }}>
          <MDTypography variant="caption" color="text">
            SHAP bar
          </MDTypography>
          <MDBox
            component="img"
            src={staticUrl("/static/explain/global_shap_bar.png")}
            alt="SHAP bar"
            sx={{ width: "100%", height: "auto" }}
          />
        </Card>
        <Card sx={{ p: 1 }}>
          <MDTypography variant="caption" color="text">
            SHAP beeswarm
          </MDTypography>
          <MDBox
            component="img"
            src={staticUrl("/static/explain/global_shap_beeswarm.png")}
            alt="SHAP beeswarm"
            sx={{ width: "100%", height: "auto" }}
          />
        </Card>
      </MDBox>
      <SimpleTable
        columns={["Feature", "Importance"]}
        rows={features.slice(0, 20).map((f) => {
          if (typeof f === "string") return [f, "—"];
          return [
            f.feature || f.name || f[0] || "—",
            f.importance ?? f.mean_abs_shap ?? f[1] ?? "—",
          ];
        })}
      />
    </ArtifactShell>
  );
}

function ExplainLocalArtifact({ enabled }) {
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await getExplainLocal();
        if (!cancelled) setSamples(res?.samples || []);
      } catch (err) {
        if (!cancelled) {
          const detail = err?.response?.data?.detail || err?.message || "Explain Local unavailable";
          setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return (
    <ArtifactShell loading={loading} error={error}>
      {samples.slice(0, 10).map((s, idx) => (
        <Accordion key={s.resource_id || idx} disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <MDTypography variant="button" fontWeight="medium">
              {s.resource_id || `Sample ${idx + 1}`}
              {s.predicted_cefr || s.prediction ? ` → ${s.predicted_cefr || s.prediction}` : ""}
            </MDTypography>
          </AccordionSummary>
          <AccordionDetails>
            <MDTypography
              variant="caption"
              component="pre"
              sx={{ whiteSpace: "pre-wrap", color: colors.text.secondary }}
            >
              {JSON.stringify(s.top_features || s.explanation || s, null, 2)}
            </MDTypography>
          </AccordionDetails>
        </Accordion>
      ))}
      {samples.length === 0 && (
        <MDTypography variant="button" color="text">
          No local explanations in report.
        </MDTypography>
      )}
    </ArtifactShell>
  );
}

function ExplainQualityArtifact({ enabled }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await getExplainQuality();
        if (!cancelled) setData(res);
      } catch (err) {
        if (!cancelled) {
          const detail =
            err?.response?.data?.detail || err?.message || "Explain Quality unavailable";
          setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  const flags = data?.bias_flags || [];

  return (
    <ArtifactShell loading={loading} error={error}>
      <MDBox
        display="grid"
        gap={2}
        mb={2}
        sx={{ gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}
      >
        <MetricCard
          label="Faithfulness"
          value={
            data?.faithfulness_score != null ? Number(data.faithfulness_score).toFixed(3) : "—"
          }
        />
        <MetricCard
          label="Stability"
          value={data?.stability_score != null ? Number(data.stability_score).toFixed(3) : "—"}
        />
      </MDBox>
      <MDTypography variant="h6" mb={1}>
        Bias flags
      </MDTypography>
      {flags.length === 0 ? (
        <MDTypography variant="button" color="text">
          No bias flags reported.
        </MDTypography>
      ) : (
        flags.map((f, i) => (
          <MDBox key={i} py={0.75} sx={{ borderBottom: `1px solid ${colors.grey[300]}` }}>
            <MDTypography variant="caption">
              {typeof f === "string" ? f : JSON.stringify(f)}
            </MDTypography>
          </MDBox>
        ))
      )}
    </ArtifactShell>
  );
}

function PredictArtifact({ enabled }) {
  const [query, setQuery] = useState("EFL reading comprehension practice");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const data = await searchResources({ query: query.trim(), top_k: 10 });
      setResults(data?.results || []);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Search failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  if (!enabled) {
    return (
      <MDAlert color="info">
        Complete earlier stages (especially Train) before using Predict retrieval checks.
      </MDAlert>
    );
  }

  return (
    <MDBox>
      <MDBox display="flex" gap={1} mb={2}>
        <MDBox flex={1}>
          <MDInput
            fullWidth
            label="Ad-hoc retrieval query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
        </MDBox>
        <MDButton variant="gradient" color="primary" onClick={run} disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </MDButton>
      </MDBox>
      {error && <MDAlert color="error">{error}</MDAlert>}
      {results && (
        <SimpleTable
          columns={["#", "Title", "CEFR", "Score"]}
          rows={results.map((r) => [
            r.rank,
            r.title,
            r.cefr_level || "—",
            Number(r.similarity_score || 0).toFixed(3),
          ])}
        />
      )}
      {results && results.length > 0 && (
        <MDBox mt={2}>
          {results.slice(0, 3).map((r) => (
            <MDBox key={r.resource_id} mb={1} display="flex" alignItems="center" gap={1}>
              {r.cefr_level && ["A1", "A2", "B1", "B2", "C1", "C2"].includes(r.cefr_level) && (
                <CefrBadge level={r.cefr_level} />
              )}
              <MDBox flex={1} maxWidth="16rem">
                <SimilarityBar value={Number(r.similarity_score) || 0} />
              </MDBox>
            </MDBox>
          ))}
        </MDBox>
      )}
    </MDBox>
  );
}

const ARTIFACT_SLUG = {
  Discover: "discover",
  Load: "load",
  Integrate: "integrate",
  EDA: "eda",
  Clean: "clean",
  Split: "split",
  Preprocess: "preprocess",
  Balance: "balance",
  Train: "train",
};

function StageArtifactPreview({ stageName, stageStatus }) {
  const enabled = stageStatus === "COMPLETE" || stageStatus === "FAILED";

  const show = stageStatus === "COMPLETE";

  let body = null;
  if (stageName === "Discover") body = <DiscoverArtifact enabled={show} />;
  else if (stageName === "Load") body = <LoadArtifact enabled={show} />;
  else if (stageName === "Integrate") body = <IntegrateArtifact enabled={show} />;
  else if (stageName === "EDA") body = <EdaArtifact enabled={show} />;
  else if (stageName === "Clean") body = <CleanArtifact enabled={show} />;
  else if (stageName === "Split") body = <SplitArtifact enabled={show} />;
  else if (stageName === "Preprocess") body = <PreprocessArtifact enabled={show} />;
  else if (stageName === "Balance") body = <BalanceArtifact enabled={show} />;
  else if (stageName === "Train") body = <TrainArtifact enabled={show} />;
  else if (stageName === "Evaluate") body = <EvaluateArtifact enabled={show} />;
  else if (stageName === "Explain Global") body = <ExplainGlobalArtifact enabled={show} />;
  else if (stageName === "Explain Local") body = <ExplainLocalArtifact enabled={show} />;
  else if (stageName === "Explain Quality") body = <ExplainQualityArtifact enabled={show} />;
  else if (stageName === "Predict")
    body = <PredictArtifact enabled={show || stageStatus === "PENDING"} />;

  return (
    <Card sx={{ p: 2, mt: 2 }}>
      <MDTypography variant="h6" mb={1.5}>
        Stage artefacts
      </MDTypography>
      {!show && stageName !== "Predict" && (
        <MDAlert color="info">
          Run this stage to COMPLETE to load artefacts
          {ARTIFACT_SLUG[stageName]
            ? ` (GET /api/pipeline/artifact/${ARTIFACT_SLUG[stageName]})`
            : ""}
          .
        </MDAlert>
      )}
      {(show || stageName === "Predict") && body}
    </Card>
  );
}

StageArtifactPreview.propTypes = {
  stageName: PropTypes.string.isRequired,
  stageStatus: PropTypes.string,
};

DiscoverArtifact.propTypes = { enabled: PropTypes.bool };
LoadArtifact.propTypes = { enabled: PropTypes.bool };
IntegrateArtifact.propTypes = { enabled: PropTypes.bool };
EdaArtifact.propTypes = { enabled: PropTypes.bool };
CleanArtifact.propTypes = { enabled: PropTypes.bool };
SplitArtifact.propTypes = { enabled: PropTypes.bool };
PreprocessArtifact.propTypes = { enabled: PropTypes.bool };
BalanceArtifact.propTypes = { enabled: PropTypes.bool };
TrainArtifact.propTypes = { enabled: PropTypes.bool };
EvaluateArtifact.propTypes = { enabled: PropTypes.bool };
ExplainGlobalArtifact.propTypes = { enabled: PropTypes.bool };
ExplainLocalArtifact.propTypes = { enabled: PropTypes.bool };
ExplainQualityArtifact.propTypes = { enabled: PropTypes.bool };
PredictArtifact.propTypes = { enabled: PropTypes.bool };

export default StageArtifactPreview;
