import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import PropTypes from "prop-types";

import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Card from "@mui/material/Card";
import Checkbox from "@mui/material/Checkbox";
import CircularProgress from "@mui/material/CircularProgress";
import FormControlLabel from "@mui/material/FormControlLabel";
import Grid from "@mui/material/Grid";
import Link from "@mui/material/Link";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import { MetricCard, CefrBadge } from "components/EflShared";
import {
  getMetrics,
  getExplainGlobal,
  getExplainLocal,
  getExplainQuality,
  exportPublicationMetrics,
  listPublicationMetricFiles,
} from "services/endpoints";
import { API_URL } from "services/apiClient";
import colors from "assets/theme/base/colors";

const CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"];

function staticUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const base = (API_URL || "http://localhost:8000").replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

function hexToRgb(hex) {
  const h = hex.replace("#", "");
  const full =
    h.length === 3
      ? h
          .split("")
          .map((c) => c + c)
          .join("")
      : h;
  const n = parseInt(full, 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function lerpHex(fromHex, toHex, t) {
  const clamped = Math.min(1, Math.max(0, t));
  const a = hexToRgb(fromHex);
  const b = hexToRgb(toHex);
  const r = Math.round(a.r + (b.r - a.r) * clamped);
  const g = Math.round(a.g + (b.g - a.g) * clamped);
  const bl = Math.round(a.b + (b.b - a.b) * clamped);
  return `rgb(${r}, ${g}, ${bl})`;
}

function fmt(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(digits);
}

function fmtDelta(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}`;
}

function cefrOk(level) {
  return level && CEFR_ORDER.includes(level);
}

function ConfusionMatrix({ title, matrix, labels }) {
  const labelList = Array.isArray(labels) && labels.length > 0 ? labels : CEFR_ORDER;
  const rows = Array.isArray(matrix) ? matrix : [];
  const maxVal = useMemo(() => {
    let m = 0;
    rows.forEach((row) => {
      (row || []).forEach((v) => {
        const n = Number(v) || 0;
        if (n > m) m = n;
      });
    });
    return m || 1;
  }, [rows]);

  const border = colors.inputBorderColor || colors.grey[300];
  const accent = colors.primary.main;
  const size = Math.max(labelList.length, rows.length, 1);

  if (!rows.length) {
    return (
      <Card sx={{ p: 2, height: "100%" }}>
        <MDTypography variant="h6" mb={1}>
          {title}
        </MDTypography>
        <MDTypography variant="button" color="text">
          Confusion matrix not available in this evaluation report.
        </MDTypography>
      </Card>
    );
  }

  return (
    <Card sx={{ p: 2, height: "100%", overflowX: "auto" }}>
      <MDTypography variant="h6" mb={1.5}>
        {title}
      </MDTypography>
      <MDBox
        display="grid"
        sx={{
          gridTemplateColumns: `auto repeat(${size}, minmax(2.25rem, 1fr))`,
          gap: "2px",
          minWidth: `${2.5 + size * 2.5}rem`,
        }}
      >
        <MDBox />
        {labelList.map((lab) => (
          <MDBox key={`h-${lab}`} textAlign="center" py={0.5}>
            <MDTypography variant="caption" fontWeight="bold">
              {lab}
            </MDTypography>
          </MDBox>
        ))}
        {labelList.map((rowLab, i) => (
          <MDBox key={`r-${rowLab}`} display="contents">
            <MDBox display="flex" alignItems="center" pr={1}>
              <MDTypography variant="caption" fontWeight="bold">
                {rowLab}
              </MDTypography>
            </MDBox>
            {labelList.map((colLab, j) => {
              const value = Number((rows[i] || [])[j]) || 0;
              const intensity = value / maxVal;
              const bg = lerpHex(border, accent, intensity);
              const textColor = intensity > 0.55 ? colors.white.main : colors.text.main;
              return (
                <MDBox
                  key={`${rowLab}-${colLab}`}
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                  minHeight="2.25rem"
                  borderRadius="sm"
                  sx={{ backgroundColor: bg }}
                  title={`${rowLab} → ${colLab}: ${value}`}
                >
                  <MDTypography variant="caption" fontWeight="medium" sx={{ color: textColor }}>
                    {value}
                  </MDTypography>
                </MDBox>
              );
            })}
          </MDBox>
        ))}
      </MDBox>
      <MDTypography variant="caption" color="text" mt={1} display="block">
        Rows = true CEFR · Columns = predicted
      </MDTypography>
    </Card>
  );
}

ConfusionMatrix.propTypes = {
  title: PropTypes.string.isRequired,
  matrix: PropTypes.arrayOf(PropTypes.arrayOf(PropTypes.number)),
  labels: PropTypes.arrayOf(PropTypes.string),
};

function RetrievalClassificationTab({ data, loading, missing, error }) {
  const retrieval = data?.retrieval || {};
  const sbertR = retrieval.sbert || {};
  const tfidfR = retrieval.tfidf || {};
  const delta = retrieval.delta || {};
  const clf = data?.classification || {};
  const sbertC = clf.sbert || {};
  const tfidfC = clf.tfidf || {};

  const retrievalKeys = [
    { key: "precision_at_10", label: "Precision@10" },
    { key: "recall_at_10", label: "Recall@10" },
    { key: "map", label: "MAP" },
    { key: "f1_at_10", label: "F1@10" },
  ];

  return (
    <MDBox pt={2}>
      {loading && (
        <MDTypography variant="button" color="text">
          Loading metrics…
        </MDTypography>
      )}

      {missing && (
        <MDAlert color="info">
          <MDBox>
            <MDTypography variant="button" color="white">
              Run the Evaluate pipeline stage to see metrics
            </MDTypography>
            <MDBox mt={1}>
              <MDButton
                component={RouterLink}
                to="/pipeline/evaluate"
                variant="outlined"
                color="white"
                size="small"
              >
                Open Evaluate stage
              </MDButton>
            </MDBox>
          </MDBox>
        </MDAlert>
      )}

      {error && (
        <MDBox mb={2}>
          <MDAlert color="error">{error}</MDAlert>
        </MDBox>
      )}

      {!loading && data && (
        <>
          <MDTypography variant="h5" fontWeight="medium" mb={1.5}>
            Retrieval (top-10)
          </MDTypography>
          <Grid container spacing={2} mb={1}>
            <Grid item xs={12} md={4}>
              <MDTypography variant="button" fontWeight="bold" color="text">
                SBERT
              </MDTypography>
            </Grid>
            <Grid item xs={12} md={4}>
              <MDTypography variant="button" fontWeight="bold" color="text">
                TF-IDF
              </MDTypography>
            </Grid>
            <Grid item xs={12} md={4}>
              <MDTypography variant="button" fontWeight="bold" color="text">
                Delta (SBERT − TF-IDF)
              </MDTypography>
            </Grid>
          </Grid>
          {retrievalKeys.map(({ key, label }) => {
            const d = delta[key];
            const positive = Number(d) >= 0;
            return (
              <Grid container spacing={2} mb={2} key={key}>
                <Grid item xs={12} sm={4}>
                  <MetricCard label={`SBERT ${label}`} value={fmt(sbertR[key])} />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <MetricCard label={`TF-IDF ${label}`} value={fmt(tfidfR[key])} />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <MetricCard
                    label={`Δ ${label}`}
                    value={fmtDelta(d)}
                    delta={positive ? "SBERT ahead" : "TF-IDF ahead"}
                    positive={positive}
                  />
                </Grid>
              </Grid>
            );
          })}

          <MDTypography variant="h5" fontWeight="medium" mt={3} mb={1.5}>
            Classification (macro)
          </MDTypography>
          <Grid container spacing={2} mb={2}>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard label="SBERT Accuracy" value={fmt(sbertC.accuracy)} />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard label="SBERT Precision" value={fmt(sbertC.precision_macro)} />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard label="SBERT Recall" value={fmt(sbertC.recall_macro)} />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard label="SBERT F1" value={fmt(sbertC.f1_macro)} />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard label="TF-IDF Accuracy" value={fmt(tfidfC.accuracy)} />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard label="TF-IDF Precision" value={fmt(tfidfC.precision_macro)} />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard label="TF-IDF Recall" value={fmt(tfidfC.recall_macro)} />
            </Grid>
            <Grid item xs={12} sm={6} lg={3}>
              <MetricCard label="TF-IDF F1" value={fmt(tfidfC.f1_macro)} />
            </Grid>
          </Grid>

          <MDTypography variant="h5" fontWeight="medium" mt={2} mb={1.5}>
            Confusion matrices
          </MDTypography>
          <Grid container spacing={2}>
            <Grid item xs={12} lg={6}>
              <ConfusionMatrix
                title="SBERT"
                matrix={data.confusion_matrix_sbert}
                labels={data.confusion_matrix_labels}
              />
            </Grid>
            <Grid item xs={12} lg={6}>
              <ConfusionMatrix
                title="TF-IDF"
                matrix={data.confusion_matrix_tfidf}
                labels={data.confusion_matrix_labels}
              />
            </Grid>
          </Grid>
        </>
      )}
    </MDBox>
  );
}

RetrievalClassificationTab.propTypes = {
  data: PropTypes.object,
  loading: PropTypes.bool,
  missing: PropTypes.bool,
  error: PropTypes.string,
};

function ExplainGlobalTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
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
  }, []);

  const features = data?.top_features || [];

  return (
    <MDBox pt={2}>
      {loading && (
        <MDTypography variant="button" color="text">
          Loading Explain Global…
        </MDTypography>
      )}
      {error && (
        <MDAlert color="info">
          <MDBox>
            {error}
            <MDBox mt={1}>
              <MDButton
                component={RouterLink}
                to="/pipeline/explain-global"
                variant="outlined"
                color="white"
                size="small"
              >
                Open Explain Global stage
              </MDButton>
            </MDBox>
          </MDBox>
        </MDAlert>
      )}
      {!loading && data && (
        <>
          <Grid container spacing={2} mb={3}>
            <Grid item xs={12} md={6}>
              <Card sx={{ p: 1.5 }}>
                <MDTypography variant="button" fontWeight="medium" mb={1} display="block">
                  SHAP bar (top dimensions)
                </MDTypography>
                <MDBox
                  component="img"
                  src={staticUrl(data.plot_url || "/static/explain/global_shap_bar.png")}
                  alt="Global SHAP bar"
                  sx={{ width: "100%", height: "auto", borderRadius: 1 }}
                />
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card sx={{ p: 1.5 }}>
                <MDTypography variant="button" fontWeight="medium" mb={1} display="block">
                  SHAP beeswarm
                </MDTypography>
                <MDBox
                  component="img"
                  src={staticUrl("/static/explain/global_shap_beeswarm.png")}
                  alt="Global SHAP beeswarm"
                  sx={{ width: "100%", height: "auto", borderRadius: 1 }}
                />
              </Card>
            </Grid>
          </Grid>

          <MDTypography variant="h6" mb={1.5}>
            Top 20 SHAP features
          </MDTypography>
          <Card sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Rank</TableCell>
                  <TableCell>Feature / dim</TableCell>
                  <TableCell>Mean |SHAP|</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {features.slice(0, 20).map((f, i) => (
                  <TableRow key={f.dimension_index ?? f.feature ?? i}>
                    <TableCell>{f.rank ?? i + 1}</TableCell>
                    <TableCell>
                      {f.feature || f.name || `dim_${f.dimension_index ?? "?"}`}
                    </TableCell>
                    <TableCell>
                      {fmt(f.mean_abs_shap_global ?? f.importance ?? f.mean_abs_shap)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </>
      )}
    </MDBox>
  );
}

function ExplainLocalTab() {
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
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
  }, []);

  return (
    <MDBox pt={2}>
      {loading && (
        <MDTypography variant="button" color="text">
          Loading Explain Local…
        </MDTypography>
      )}
      {error && (
        <MDAlert color="info">
          <MDBox>
            {error}
            <MDBox mt={1}>
              <MDButton
                component={RouterLink}
                to="/pipeline/explain-local"
                variant="outlined"
                color="white"
                size="small"
              >
                Open Explain Local stage
              </MDButton>
            </MDBox>
          </MDBox>
        </MDAlert>
      )}
      {!loading && !error && samples.length === 0 && (
        <MDTypography variant="button" color="text">
          No local explanations in the report.
        </MDTypography>
      )}
      {samples.map((s, idx) => {
        const predicted = s.predicted_cefr || s.prediction;
        const truth = s.true_cefr || s.true_label;
        const mismatch = predicted && truth && predicted !== truth;
        const features = (s.top_features || []).slice(0, 5);

        return (
          <Accordion key={s.resource_id || idx} disableGutters sx={{ mb: 1 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <MDBox display="flex" flexWrap="wrap" alignItems="center" gap={1.5} width="100%">
                <MDTypography variant="button" fontWeight="medium" sx={{ flex: 1, minWidth: 0 }}>
                  {s.title || s.resource_id || `Sample ${idx + 1}`}
                </MDTypography>
                <MDBox display="flex" alignItems="center" gap={1}>
                  <MDTypography variant="caption" color="text">
                    Pred
                  </MDTypography>
                  {cefrOk(predicted) ? (
                    <MDBox
                      sx={
                        mismatch
                          ? {
                              outline: `2px solid ${colors.error.main}`,
                              borderRadius: "0.4rem",
                              lineHeight: 0,
                            }
                          : undefined
                      }
                    >
                      <CefrBadge level={predicted} />
                    </MDBox>
                  ) : (
                    <MDTypography variant="caption">{predicted || "—"}</MDTypography>
                  )}
                  <MDTypography variant="caption" color="text">
                    True
                  </MDTypography>
                  {cefrOk(truth) ? (
                    <CefrBadge level={truth} />
                  ) : (
                    <MDTypography variant="caption">{truth || "—"}</MDTypography>
                  )}
                </MDBox>
              </MDBox>
            </AccordionSummary>
            <AccordionDetails>
              {mismatch && (
                <MDBox mb={1}>
                  <MDAlert color="error">
                    Predicted {predicted} ≠ true {truth}
                  </MDAlert>
                </MDBox>
              )}
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>approx_token</TableCell>
                    <TableCell>Dim</TableCell>
                    <TableCell>Weight</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {features.map((f, fi) => (
                    <TableRow key={`${f.dim}-${fi}`}>
                      <TableCell>{f.approx_token || "—"}</TableCell>
                      <TableCell>{f.dim ?? "—"}</TableCell>
                      <TableCell>{f.weight != null ? Number(f.weight).toFixed(4) : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AccordionDetails>
          </Accordion>
        );
      })}
    </MDBox>
  );
}

function ExplainQualityTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
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
  }, []);

  const flags = data?.bias_flags || [];

  return (
    <MDBox pt={2}>
      {loading && (
        <MDTypography variant="button" color="text">
          Loading Explain Quality…
        </MDTypography>
      )}
      {error && (
        <MDAlert color="info">
          <MDBox>
            {error}
            <MDBox mt={1}>
              <MDButton
                component={RouterLink}
                to="/pipeline/explain-quality"
                variant="outlined"
                color="white"
                size="small"
              >
                Open Explain Quality stage
              </MDButton>
            </MDBox>
          </MDBox>
        </MDAlert>
      )}
      {!loading && data && (
        <>
          <Grid container spacing={2} mb={3}>
            <Grid item xs={12} sm={6}>
              <MetricCard label="Faithfulness Score" value={fmt(data.faithfulness_score)} />
            </Grid>
            <Grid item xs={12} sm={6}>
              <MetricCard label="Stability Score" value={fmt(data.stability_score)} />
            </Grid>
          </Grid>

          <MDTypography variant="h6" mb={1.5}>
            Bias flags (F1 &lt; 0.60)
          </MDTypography>
          {flags.length === 0 ? (
            <MDTypography variant="button" color="text">
              No bias flags reported.
            </MDTypography>
          ) : (
            flags.map((flag, i) => (
              <MDBox key={`${flag}-${i}`} mb={1}>
                <MDAlert color="warning">{flag}</MDAlert>
              </MDBox>
            ))
          )}
        </>
      )}
    </MDBox>
  );
}

function Metrics() {
  const [tab, setTab] = useState(0);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState(null);

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);
  const [exportMsg, setExportMsg] = useState(null);
  const [exportFiles, setExportFiles] = useState([]);

  const loadExportFiles = async () => {
    try {
      const res = await listPublicationMetricFiles();
      setExportFiles(Array.isArray(res?.files) ? res.files : []);
    } catch {
      /* listing is optional until admin is signed in / files exist */
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setMissing(false);
      setError(null);
      try {
        const res = await getMetrics();
        if (!cancelled) setData(res);
      } catch (err) {
        if (cancelled) return;
        if (err?.response?.status === 404) {
          setMissing(true);
          setData(null);
        } else {
          const detail = err?.response?.data?.detail || err?.message || "Failed to load metrics";
          setError(typeof detail === "string" ? detail : JSON.stringify(detail));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    loadExportFiles();
    return () => {
      cancelled = true;
    };
  }, []);

  const onExport = async () => {
    setExporting(true);
    setExportError(null);
    setExportMsg(null);
    try {
      const res = await exportPublicationMetrics();
      setExportMsg(`Generated ${res.files_generated} file(s) in ${res.output_dir}.`);
      await loadExportFiles();
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Export failed";
      setExportError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setExporting(false);
    }
  };

  const fileDownloadHref = (file) => {
    if (file?.download_url) return staticUrl(file.download_url);
    if (file?.filename) {
      return staticUrl(`/static/research-reports/metrics/${file.filename}`);
    }
    return "#";
  };

  const formatSize = (bytes) => {
    const n = Number(bytes) || 0;
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox
          display="flex"
          justifyContent="space-between"
          alignItems="flex-start"
          flexWrap="wrap"
          gap={1}
          mb={2}
        >
          <MDBox>
            <MDTypography variant="h4" fontWeight="bold" mb={0.5}>
              Metrics & Explainability
            </MDTypography>
            <MDTypography variant="button" color="text" display="block">
              Evaluation metrics and model explanations
              {data?.evaluation_run_at ? ` · eval run at ${data.evaluation_run_at}` : ""}
            </MDTypography>
          </MDBox>
          <MDButton
            variant="gradient"
            color="primary"
            size="small"
            disabled={exporting}
            onClick={onExport}
          >
            {exporting ? (
              <MDBox display="inline-flex" alignItems="center" gap={1}>
                <CircularProgress size={14} color="inherit" />
                Exporting…
              </MDBox>
            ) : (
              "Export Publication Tables"
            )}
          </MDButton>
        </MDBox>

        {exportError && (
          <MDBox mb={2}>
            <MDAlert color="error">{exportError}</MDAlert>
          </MDBox>
        )}
        {exportMsg && (
          <MDBox mb={2}>
            <MDAlert color="success">{exportMsg}</MDAlert>
          </MDBox>
        )}

        {exportFiles.length > 0 && (
          <Card sx={{ p: 2, mb: 2 }}>
            <MDTypography variant="h6" mb={1}>
              Publication exports ({exportFiles.length})
            </MDTypography>
            <MDTypography variant="caption" color="text" display="block" mb={1}>
              Download CSV / LaTeX / PNG tables for the dissertation (admin session required to
              regenerate).
            </MDTypography>
            <List dense disablePadding>
              {exportFiles.map((file) => (
                <ListItem
                  key={file.filename || file.path}
                  disableGutters
                  secondaryAction={
                    <MDTypography variant="caption" color="text">
                      {formatSize(file.size)}
                    </MDTypography>
                  }
                >
                  <FormControlLabel
                    control={<Checkbox defaultChecked size="small" disableRipple />}
                    label={
                      <ListItemText
                        primary={
                          <Link
                            href={fileDownloadHref(file)}
                            target="_blank"
                            rel="noopener noreferrer"
                            underline="hover"
                          >
                            {file.filename}
                          </Link>
                        }
                        secondary={
                          file.last_modified ? `Modified ${file.last_modified}` : undefined
                        }
                      />
                    }
                    sx={{ alignItems: "flex-start", m: 0, width: "100%" }}
                  />
                </ListItem>
              ))}
            </List>
          </Card>
        )}

        <Card>
          <Tabs
            value={tab}
            onChange={(_, v) => setTab(v)}
            textColor="primary"
            indicatorColor="primary"
            variant="scrollable"
            scrollButtons="auto"
            sx={{ borderBottom: `1px solid ${colors.grey[300]}`, px: 1 }}
          >
            <Tab label="Retrieval & Classification" />
            <Tab label="Explain Global" />
            <Tab label="Explain Local" />
            <Tab label="Explain Quality" />
          </Tabs>

          <MDBox px={2} pb={2}>
            {tab === 0 && (
              <RetrievalClassificationTab
                data={data}
                loading={loading}
                missing={missing}
                error={error}
              />
            )}
            {tab === 1 && <ExplainGlobalTab />}
            {tab === 2 && <ExplainLocalTab />}
            {tab === 3 && <ExplainQualityTab />}
          </MDBox>
        </Card>
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default Metrics;
