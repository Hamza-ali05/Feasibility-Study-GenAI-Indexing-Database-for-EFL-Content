import { Fragment, useCallback, useEffect, useMemo, useState } from "react";

import Card from "@mui/material/Card";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";

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

const METHODS = [
  { value: "tfidf", label: "TF-IDF Baseline" },
  { value: "sbert", label: "SBERT" },
  { value: "sbert_metadata", label: "SBERT + Metadata" },
  { value: "sbert_metadata_rag", label: "SBERT + Metadata + RAG" },
];

const STATUS_COLOR = {
  configured: "default",
  running: "info",
  completed: "success",
  failed: "error",
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
  const [expanded, setExpanded] = useState({});
  const [details, setDetails] = useState({});
  const [detailLoading, setDetailLoading] = useState({});

  const [compareOpen, setCompareOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [running, setRunning] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listExperiments();
      setRows(Array.isArray(data) ? data : []);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load experiments";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, []);

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

  const toggleExpand = async (id) => {
    const next = !expanded[id];
    setExpanded((prev) => ({ ...prev, [id]: next }));
    if (next && !details[id]) {
      setDetailLoading((prev) => ({ ...prev, [id]: true }));
      try {
        const detail = await getExperiment(id);
        setDetails((prev) => ({ ...prev, [id]: detail }));
      } catch (err) {
        const detail = err?.response?.data?.detail || err?.message || "Failed to load detail";
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      } finally {
        setDetailLoading((prev) => ({ ...prev, [id]: false }));
      }
    }
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
      const res = await exportExperimentComparison(selectedIds);
      setMsg(
        `Exported ${res.files_generated} file(s) to ${res.output_dir}: ${(res.files || []).join(
          ", "
        )}`
      );
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Export failed";
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
      // Refresh shortly so the new/running entry appears
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

        <Card>
          {loading ? (
            <MDBox display="flex" justifyContent="center" py={6}>
              <CircularProgress color="info" />
            </MDBox>
          ) : (
            <TableContainer sx={{ boxShadow: "none" }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox" />
                    <TableCell width="4%" />
                    <TableCell>Name</TableCell>
                    <TableCell>Method</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">P@10</TableCell>
                    <TableCell align="right">MAP</TableCell>
                    <TableCell align="right">F1</TableCell>
                    <TableCell align="right">Accuracy</TableCell>
                    <TableCell>Date</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={10}>
                        <MDTypography variant="button" color="text">
                          No experiments yet. Run Stage Evaluate or create a New Experiment.
                        </MDTypography>
                      </TableCell>
                    </TableRow>
                  )}
                  {rows.map((row) => {
                    const id = row.experiment_id;
                    const open = Boolean(expanded[id]);
                    const detail = details[id];
                    return (
                      <Fragment key={id}>
                        <TableRow hover selected={Boolean(selected[id])}>
                          <TableCell padding="checkbox">
                            <Checkbox
                              checked={Boolean(selected[id])}
                              onChange={() => toggleSelect(id)}
                              size="small"
                            />
                          </TableCell>
                          <TableCell>
                            <IconButton size="small" onClick={() => toggleExpand(id)}>
                              {open ? (
                                <KeyboardArrowUpIcon fontSize="small" />
                              ) : (
                                <KeyboardArrowDownIcon fontSize="small" />
                              )}
                            </IconButton>
                          </TableCell>
                          <TableCell>
                            <MDTypography
                              variant="button"
                              fontWeight="medium"
                              sx={{ cursor: "pointer" }}
                              onClick={() => toggleExpand(id)}
                            >
                              {row.name}
                            </MDTypography>
                          </TableCell>
                          <TableCell>
                            <MDTypography variant="caption">{row.method}</MDTypography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              label={row.status || "—"}
                              color={STATUS_COLOR[row.status] || "default"}
                            />
                          </TableCell>
                          <TableCell align="right">{fmt(row.precision_at_10)}</TableCell>
                          <TableCell align="right">{fmt(row.map)}</TableCell>
                          <TableCell align="right">{fmt(row.f1_at_10)}</TableCell>
                          <TableCell align="right">{fmt(row.accuracy)}</TableCell>
                          <TableCell>
                            <MDTypography variant="caption">
                              {fmtDate(row.completed_at || row.started_at)}
                            </MDTypography>
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell
                            colSpan={10}
                            sx={{ py: 0, borderBottom: open ? undefined : "none" }}
                          >
                            <Collapse in={open} timeout="auto" unmountOnExit>
                              <MDBox p={2} bgcolor="grey.100" borderRadius="md">
                                {detailLoading[id] && <CircularProgress size={18} color="info" />}
                                {!detailLoading[id] && detail && (
                                  <MDTypography
                                    variant="caption"
                                    color="text"
                                    component="pre"
                                    sx={{ whiteSpace: "pre-wrap", m: 0 }}
                                  >
                                    {JSON.stringify(detail, null, 2)}
                                  </MDTypography>
                                )}
                              </MDBox>
                            </Collapse>
                          </TableCell>
                        </TableRow>
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Card>

        {compareOpen && selectedRows.length >= 2 && (
          <Card sx={{ p: 2, mt: 3 }}>
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
              size="small"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <FormControl fullWidth size="small">
              <InputLabel id="method-label">Method</InputLabel>
              <Select
                labelId="method-label"
                label="Method"
                value={form.method}
                onChange={(e) => setForm({ ...form, method: e.target.value })}
              >
                {METHODS.map((m) => (
                  <MenuItem key={m.value} value={m.value}>
                    {m.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
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
