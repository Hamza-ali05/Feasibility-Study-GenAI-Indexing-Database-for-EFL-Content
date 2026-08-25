import { useCallback, useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControlLabel from "@mui/material/FormControlLabel";
import Grid from "@mui/material/Grid";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";
import MDInput from "components/MDInput";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";
import VerticalBarChart from "examples/Charts/BarCharts/VerticalBarChart";

import {
  exportExperimentComparison,
  getExperiment,
  listExperiments,
  runExperiment,
} from "services/endpoints";
import colors from "assets/theme/base/colors";

const METHODS = [
  { value: "tfidf", label: "TF-IDF Baseline" },
  { value: "sbert", label: "SBERT" },
  { value: "sbert_metadata", label: "SBERT + Metadata" },
  { value: "sbert_metadata_rag", label: "SBERT + Metadata + RAG" },
];

const METHOD_LABEL = Object.fromEntries(METHODS.map((m) => [m.value, m.label]));

const STATUS_COLOR = {
  configured: "default",
  running: "info",
  completed: "success",
  failed: "error",
};

const STATUS_LABEL = {
  configured: "Configured",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

const CHART_COLORS = ["info", "primary", "success", "warning", "error", "secondary"];

function fmt(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(digits);
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return String(iso);
  }
}

function humanizeKey(key) {
  return String(key || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function yesNo(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "—";
}

function methodLabel(value) {
  return METHOD_LABEL[value] || humanizeKey(value) || "—";
}

function DetailItem({ label, value }) {
  return (
    <MDBox>
      <MDTypography variant="caption" color="text" display="block">
        {label}
      </MDTypography>
      <MDTypography variant="button" fontWeight="medium" sx={{ wordBreak: "break-word" }}>
        {value ?? "—"}
      </MDTypography>
    </MDBox>
  );
}

DetailItem.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node,
};

DetailItem.defaultProps = {
  value: "—",
};

function MetricPill({ label, value }) {
  return (
    <MDBox
      px={1.5}
      py={1}
      borderRadius="md"
      sx={{
        backgroundColor: colors.grey[100],
        border: `1px solid ${colors.grey[300]}`,
        minWidth: 96,
      }}
    >
      <MDTypography variant="caption" color="text" display="block">
        {label}
      </MDTypography>
      <MDTypography variant="h6" fontWeight="bold">
        {fmt(value)}
      </MDTypography>
    </MDBox>
  );
}

MetricPill.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
};

function ExperimentCard({ row, detail, detailLoading, selected, onToggle }) {
  const config = detail?.config || {};
  const custom = config.custom_params || {};
  const dataset = detail?.dataset_info || {};
  const retrieval = detail?.results?.retrieval || {};
  const classification = detail?.results?.classification || {};
  const perClass = detail?.results?.per_class_f1 || {};
  const env = detail?.environment || {};

  const pAt10 = row.precision_at_10 ?? retrieval.precision_at_k;
  const mapScore = row.map ?? retrieval.map;
  const f1 = row.f1_at_10 ?? retrieval.f1_at_k;
  const accuracy = row.accuracy ?? classification.accuracy;
  const mrr = retrieval.mrr;
  const recall = retrieval.recall_at_k;

  return (
    <Card sx={{ p: 2.5, mb: 2 }}>
      <MDBox display="flex" alignItems="flex-start" gap={1} mb={1.5}>
        <Checkbox
          checked={selected}
          onChange={onToggle}
          size="small"
          sx={{ mt: 0.25 }}
          inputProps={{ "aria-label": `Select ${row.name}` }}
        />
        <MDBox flex={1} minWidth={0}>
          <MDBox
            display="flex"
            justifyContent="space-between"
            alignItems="flex-start"
            flexWrap="wrap"
            gap={1}
            mb={0.5}
          >
            <MDTypography variant="h6" fontWeight="bold">
              {row.name}
            </MDTypography>
            <Chip
              size="small"
              label={STATUS_LABEL[row.status] || humanizeKey(row.status) || "Unknown"}
              color={STATUS_COLOR[row.status] || "default"}
            />
          </MDBox>
          {(detail?.description || row.description) && (
            <MDTypography variant="body2" color="text" mb={1}>
              {detail?.description || row.description}
            </MDTypography>
          )}
          <MDTypography variant="caption" color="text">
            Method: {methodLabel(row.method || config.retrieval_method)}
            {" · "}
            {fmtDate(
              row.completed_at || row.started_at || detail?.completed_at || detail?.started_at
            )}
          </MDTypography>
        </MDBox>
      </MDBox>

      <MDBox display="flex" flexWrap="wrap" gap={1} mb={2}>
        <MetricPill label="Precision @10" value={pAt10} />
        <MetricPill label="MAP" value={mapScore} />
        <MetricPill label="F1 @10" value={f1} />
        <MetricPill label="Accuracy" value={accuracy} />
        {(mrr !== undefined && mrr !== null) || detailLoading ? (
          <MetricPill label="MRR" value={mrr} />
        ) : null}
        {(recall !== undefined && recall !== null) || detailLoading ? (
          <MetricPill label="Recall @10" value={recall} />
        ) : null}
      </MDBox>

      {detailLoading && (
        <MDBox display="flex" alignItems="center" gap={1} mb={1}>
          <CircularProgress size={16} color="info" />
          <MDTypography variant="caption" color="text">
            Loading experiment details…
          </MDTypography>
        </MDBox>
      )}

      {!detailLoading && detail && (
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <MDTypography variant="button" fontWeight="bold" display="block" mb={1}>
              Setup
            </MDTypography>
            <Grid container spacing={1.5}>
              <Grid item xs={12} sm={6}>
                <DetailItem label="Retrieval method" value={methodLabel(config.retrieval_method)} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <DetailItem
                  label="Embedding model"
                  value={String(config.embedding_model || "—").replace(
                    /^sentence-transformers\//,
                    ""
                  )}
                />
              </Grid>
              <Grid item xs={6} sm={4}>
                <DetailItem label="Classifier" value={humanizeKey(config.classifier)} />
              </Grid>
              <Grid item xs={6} sm={4}>
                <DetailItem label="FAISS index" value={config.faiss_index_type || "—"} />
              </Grid>
              <Grid item xs={6} sm={4}>
                <DetailItem label="Top-k" value={config.top_k ?? "—"} />
              </Grid>
              <Grid item xs={6} sm={4}>
                <DetailItem
                  label="Metadata filters"
                  value={yesNo(config.metadata_filters_enabled)}
                />
              </Grid>
              <Grid item xs={6} sm={4}>
                <DetailItem label="RAG enabled" value={yesNo(config.rag_enabled)} />
              </Grid>
              <Grid item xs={6} sm={4}>
                <DetailItem label="Random seed" value={config.random_seed ?? "—"} />
              </Grid>
              {custom.candidate_pool != null && (
                <Grid item xs={6} sm={4}>
                  <DetailItem label="Candidate pool" value={custom.candidate_pool} />
                </Grid>
              )}
              {custom.note && (
                <Grid item xs={12}>
                  <DetailItem label="Note" value={custom.note} />
                </Grid>
              )}
            </Grid>
          </Grid>

          <Grid item xs={12} md={6}>
            <MDTypography variant="button" fontWeight="bold" display="block" mb={1}>
              Dataset & run
            </MDTypography>
            <Grid container spacing={1.5}>
              <Grid item xs={6} sm={4}>
                <DetailItem
                  label="Total resources"
                  value={
                    dataset.total_resources?.toLocaleString?.() || dataset.total_resources || "—"
                  }
                />
              </Grid>
              <Grid item xs={6} sm={4}>
                <DetailItem
                  label="Train / val / test"
                  value={
                    dataset.train_size != null
                      ? `${dataset.train_size.toLocaleString()} / ${Number(
                          dataset.val_size || 0
                        ).toLocaleString()} / ${Number(dataset.test_size || 0).toLocaleString()}`
                      : "—"
                  }
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <DetailItem label="Dataset hash" value={dataset.dataset_hash || "—"} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <DetailItem label="Started" value={fmtDate(detail.started_at)} />
              </Grid>
              <Grid item xs={12} sm={6}>
                <DetailItem label="Completed" value={fmtDate(detail.completed_at)} />
              </Grid>
              {env.platform?.os && (
                <Grid item xs={12} sm={6}>
                  <DetailItem
                    label="Environment"
                    value={`${env.platform.os}${env.gpu?.available ? " · GPU" : " · CPU"}`}
                  />
                </Grid>
              )}
              {classification.f1_macro != null && (
                <Grid item xs={6} sm={3}>
                  <DetailItem label="Macro F1" value={fmt(classification.f1_macro)} />
                </Grid>
              )}
              {classification.precision_macro != null && (
                <Grid item xs={6} sm={3}>
                  <DetailItem label="Macro precision" value={fmt(classification.precision_macro)} />
                </Grid>
              )}
            </Grid>

            {Object.keys(perClass).length > 0 && (
              <MDBox mt={2}>
                <MDTypography variant="caption" color="text" display="block" mb={0.75}>
                  CEFR F1 scores
                </MDTypography>
                <MDBox display="flex" flexWrap="wrap" gap={0.75}>
                  {["A1", "A2", "B1", "B2", "C1", "C2"]
                    .filter((level) => perClass[level] != null)
                    .map((level) => (
                      <Chip
                        key={level}
                        size="small"
                        variant="outlined"
                        label={`${level}: ${fmt(perClass[level], 3)}`}
                      />
                    ))}
                </MDBox>
              </MDBox>
            )}
          </Grid>

          {detail.notes && (
            <Grid item xs={12}>
              <MDTypography variant="caption" color="text" display="block">
                Notes
              </MDTypography>
              <MDTypography variant="button">{detail.notes}</MDTypography>
            </Grid>
          )}
        </Grid>
      )}
    </Card>
  );
}

ExperimentCard.propTypes = {
  row: PropTypes.object.isRequired,
  detail: PropTypes.object,
  detailLoading: PropTypes.bool,
  selected: PropTypes.bool,
  onToggle: PropTypes.func.isRequired,
};

ExperimentCard.defaultProps = {
  detail: null,
  detailLoading: false,
  selected: false,
};

const EMPTY_FORM = {
  name: "",
  description: "",
  method: "sbert_metadata",
};

function Experiments() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);

  const [selected, setSelected] = useState({});
  const [details, setDetails] = useState({});
  const [detailLoading, setDetailLoading] = useState({});

  const [compareOpen, setCompareOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [running, setRunning] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const loadDetails = useCallback(async (list) => {
    const ids = (list || []).map((r) => r.experiment_id).filter(Boolean);
    await Promise.all(
      ids.map(async (id) => {
        setDetailLoading((prev) => ({ ...prev, [id]: true }));
        try {
          const detail = await getExperiment(id);
          setDetails((prev) => ({ ...prev, [id]: detail }));
        } catch {
          /* keep card usable from summary row */
        } finally {
          setDetailLoading((prev) => ({ ...prev, [id]: false }));
        }
      })
    );
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listExperiments();
      const list = Array.isArray(data) ? data : [];
      setRows(list);
      loadDetails(list);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load experiments";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, [loadDetails]);

  useEffect(() => {
    load();
  }, [load]);

  const selectedIds = useMemo(() => Object.keys(selected).filter((id) => selected[id]), [selected]);

  const selectedRows = useMemo(
    () => rows.filter((r) => selectedIds.includes(r.experiment_id)),
    [rows, selectedIds]
  );

  const comparisonChart = useMemo(() => {
    const labels = ["P@10", "MAP", "F1", "Accuracy"];
    const datasets = selectedRows.map((row, i) => ({
      label: row.name,
      color: CHART_COLORS[i % CHART_COLORS.length],
      data: [
        Number(row.precision_at_10) || 0,
        Number(row.map) || 0,
        Number(row.f1_at_10) || 0,
        Number(row.accuracy) || 0,
      ],
    }));
    return { labels, datasets };
  }, [selectedRows]);

  const toggleSelect = (id) => {
    setSelected((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const onCompare = () => {
    if (selectedIds.length < 2) {
      setError("Select at least two experiments to compare.");
      return;
    }
    setError(null);
    setCompareOpen(true);
  };

  const onExport = async () => {
    if (selectedIds.length < 1) {
      setError("Select at least one experiment to export.");
      return;
    }
    setExporting(true);
    setError(null);
    setMsg(null);
    try {
      const blob = await exportExperimentComparison(selectedIds);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "experiment_comparison.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setMsg("Downloaded experiment_comparison.zip (CSV, LaTeX, and PNG).");
    } catch (err) {
      let detail = err?.message || "Export failed";
      const data = err?.response?.data;
      if (data instanceof Blob) {
        try {
          const text = await data.text();
          const parsed = JSON.parse(text);
          detail = parsed.detail || text;
        } catch {
          detail = "Export failed";
        }
      } else if (data?.detail) {
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setExporting(false);
    }
  };

  const onRun = async () => {
    if (!form.name.trim()) {
      setError("Experiment name is required.");
      return;
    }
    setRunning(true);
    setError(null);
    setMsg(null);
    try {
      const res = await runExperiment({
        name: form.name.trim(),
        description: form.description || "",
        method: form.method,
      });
      setAddOpen(false);
      setForm(EMPTY_FORM);
      setMsg(res.detail || `Started experiment "${res.name}" (${res.method}).`);
      setTimeout(load, 1500);
      setTimeout(load, 8000);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Run failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setRunning(false);
    }
  };

  return (
    <DashboardLayout>
      <DashboardNavbar hideBreadcrumbs />
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
              Experiments
            </MDTypography>
            <MDTypography variant="button" color="text" display="block">
              Feasibility study experiment tracker (TF-IDF · SBERT · Metadata · RAG)
            </MDTypography>
          </MDBox>
          <MDBox display="flex" flexWrap="wrap" gap={1}>
            <MDButton
              variant="outlined"
              color="info"
              size="small"
              disabled={selectedIds.length < 2}
              onClick={onCompare}
            >
              Compare Selected ({selectedIds.length})
            </MDButton>
            <MDButton
              variant="outlined"
              color="secondary"
              size="small"
              disabled={exporting || selectedIds.length < 1}
              onClick={onExport}
            >
              {exporting ? (
                <MDBox display="inline-flex" alignItems="center" gap={1}>
                  <CircularProgress size={14} color="inherit" />
                  Exporting…
                </MDBox>
              ) : (
                "Export Comparison"
              )}
            </MDButton>
            <MDButton
              variant="gradient"
              color="primary"
              size="small"
              onClick={() => {
                setForm(EMPTY_FORM);
                setAddOpen(true);
              }}
            >
              New Experiment
            </MDButton>
          </MDBox>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}
        {msg && (
          <MDBox mb={2}>
            <MDAlert color="success">{msg}</MDAlert>
          </MDBox>
        )}

        {loading ? (
          <Card sx={{ p: 4 }}>
            <MDBox display="flex" justifyContent="center">
              <CircularProgress color="info" />
            </MDBox>
          </Card>
        ) : rows.length === 0 ? (
          <Card sx={{ p: 3 }}>
            <MDTypography variant="button" color="text">
              No experiments yet. Run Stage Evaluate or create a New Experiment.
            </MDTypography>
          </Card>
        ) : (
          rows.map((row) => {
            const id = row.experiment_id;
            return (
              <ExperimentCard
                key={id}
                row={row}
                detail={details[id]}
                detailLoading={Boolean(detailLoading[id])}
                selected={Boolean(selected[id])}
                onToggle={() => toggleSelect(id)}
              />
            );
          })
        )}

        {compareOpen && selectedRows.length >= 2 && (
          <Card sx={{ p: 2, mt: 1 }}>
            <MDBox
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              mb={1}
              flexWrap="wrap"
              gap={1}
            >
              <MDTypography variant="h6">Comparison chart</MDTypography>
              <MDButton
                variant="text"
                color="secondary"
                size="small"
                onClick={() => setCompareOpen(false)}
              >
                Hide
              </MDButton>
            </MDBox>
            <VerticalBarChart
              icon={{ color: "info", component: "science" }}
              title="Selected experiments"
              description="Grouped bars: one cluster per metric, one bar per experiment"
              height="18rem"
              chart={comparisonChart}
            />
          </Card>
        )}
      </MDBox>

      <Dialog open={addOpen} onClose={() => !running && setAddOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>New Experiment</DialogTitle>
        <DialogContent>
          <MDBox display="flex" flexDirection="column" gap={2} mt={1}>
            <MDInput
              label="Name"
              fullWidth
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              label="Description"
              fullWidth
              multiline
              minRows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <TextField
              select
              label="Method"
              fullWidth
              value={form.method}
              onChange={(e) => setForm({ ...form, method: e.target.value })}
              SelectProps={{
                MenuProps: { disableScrollLock: true },
              }}
              sx={{
                "& .MuiOutlinedInput-root": {
                  minHeight: "2.8125rem",
                },
                "& .MuiSelect-select": {
                  display: "flex",
                  alignItems: "center",
                  py: 1.5,
                },
              }}
            >
              {METHODS.map((m) => (
                <MenuItem key={m.value} value={m.value}>
                  {m.label}
                </MenuItem>
              ))}
            </TextField>
            <FormControlLabel
              control={<Checkbox checked disabled />}
              label="Runs in the background using the current train/test artefacts"
            />
          </MDBox>
        </DialogContent>
        <DialogActions>
          <MDButton
            variant="outlined"
            color="secondary"
            disabled={running}
            onClick={() => setAddOpen(false)}
          >
            Cancel
          </MDButton>
          <MDButton
            variant="gradient"
            color="primary"
            disabled={running || !form.name.trim()}
            onClick={onRun}
          >
            {running ? "Starting…" : "Run"}
          </MDButton>
        </DialogActions>
      </Dialog>

      <Footer />
    </DashboardLayout>
  );
}

export default Experiments;
