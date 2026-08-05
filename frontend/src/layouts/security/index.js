/**
 * Security Evaluation — admin page for OWASP-aligned API audits.
 */

import { useCallback, useEffect, useState } from "react";
import PropTypes from "prop-types";

import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";

import MDBox from "components/MDBox";
import MDTypography from "components/MDTypography";
import MDAlert from "components/MDAlert";
import MDButton from "components/MDButton";

import DashboardLayout from "examples/LayoutContainers/DashboardLayout";
import DashboardNavbar from "examples/Navbars/DashboardNavbar";
import Footer from "examples/Footer";

import {
  downloadSecurityMarkdown,
  getSecurityAuditStatus,
  getSecurityReport,
  runSecurityAudit,
} from "services/endpoints";
import colors from "assets/theme/base/colors";

const CATEGORIES = [
  { key: "authentication", label: "Authentication & Authorization" },
  { key: "input_validation", label: "Input Validation" },
  { key: "prompt_injection", label: "Prompt Injection Resistance" },
  { key: "file_upload", label: "File Upload Security" },
  { key: "api_security", label: "API Security Configuration" },
];

const STATUS_COLOR = {
  Pass: "success",
  Fail: "error",
  Partial: "warning",
  "Not Tested": "default",
};

function SummaryCard({ title, value, color }) {
  return (
    <Card sx={{ p: 2, flex: "1 1 140px", minWidth: 140 }}>
      <MDTypography variant="caption" color="text">
        {title}
      </MDTypography>
      <MDTypography variant="h4" fontWeight="bold" color={color || "dark"}>
        {value ?? "—"}
      </MDTypography>
    </Card>
  );
}

SummaryCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  color: PropTypes.string,
};

function CategorySection({ title, items }) {
  const [open, setOpen] = useState(false);
  const list = Array.isArray(items) ? items : [];
  const passed = list.filter((i) => i && i.passed === true).length;
  const total = list.filter((i) => i && typeof i.passed === "boolean").length;

  return (
    <Card sx={{ mb: 1.5, overflow: "hidden" }}>
      <MDBox
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        px={2}
        py={1.25}
        sx={{ cursor: "pointer" }}
        onClick={() => setOpen((v) => !v)}
      >
        <MDBox>
          <MDTypography variant="button" fontWeight="medium">
            {title}
          </MDTypography>
          <MDTypography variant="caption" color="text" display="block">
            {passed}/{total} passed
          </MDTypography>
        </MDBox>
        <IconButton size="small">
          {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
        </IconButton>
      </MDBox>
      <Collapse in={open}>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Result</TableCell>
                <TableCell>Endpoint / Test</TableCell>
                <TableCell>Detail</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {list.map((item, idx) => (
                <TableRow key={idx}>
                  <TableCell>
                    <Chip
                      size="small"
                      label={item.passed ? "PASS" : "FAIL"}
                      color={item.passed ? "success" : "error"}
                    />
                  </TableCell>
                  <TableCell>
                    <MDTypography variant="caption">
                      {item.endpoint || item.test || (item.payload || "").slice(0, 40) || "—"}
                    </MDTypography>
                  </TableCell>
                  <TableCell>
                    <MDTypography variant="caption" color="text">
                      {(item.detail || "").slice(0, 160)}
                    </MDTypography>
                  </TableCell>
                </TableRow>
              ))}
              {!list.length && (
                <TableRow>
                  <TableCell colSpan={3}>
                    <MDTypography variant="caption" color="text">
                      No results in this category.
                    </MDTypography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Collapse>
    </Card>
  );
}

CategorySection.propTypes = {
  title: PropTypes.string.isRequired,
  items: PropTypes.arrayOf(PropTypes.object),
};

function SecurityEvaluation() {
  const [report, setReport] = useState(null);
  const [status, setStatus] = useState({ running: false, current_category: null });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const loadReport = useCallback(async () => {
    try {
      const data = await getSecurityReport();
      setReport(data);
      setError(null);
    } catch (err) {
      if (err?.response?.status === 404) {
        setReport(null);
      } else {
        const detail = err?.response?.data?.detail || err?.message || "Failed to load report";
        setError(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      const s = await getSecurityAuditStatus();
      setStatus(s || {});
      return s;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await refreshStatus();
      await loadReport();
      setLoading(false);
    })();
  }, [loadReport, refreshStatus]);

  // Poll while audit is running
  useEffect(() => {
    if (!status.running) return undefined;
    const id = setInterval(async () => {
      const s = await refreshStatus();
      if (s && !s.running) {
        await loadReport();
      }
    }, 2000);
    return () => clearInterval(id);
  }, [status.running, refreshStatus, loadReport]);

  const handleRun = async () => {
    setError(null);
    try {
      await runSecurityAudit();
      setStatus({ running: true, current_category: "initialising" });
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to start audit";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setError(null);
    try {
      const blob = await downloadSecurityMarkdown();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "security_audit_report.md";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || "Export failed";
      setError(typeof detail === "string" ? detail : JSON.stringify(detail));
    } finally {
      setExporting(false);
    }
  };

  const summary = report?.summary || {};
  const owasp = report?.owasp_mapping || [];
  const categoryLabel = status.current_category
    ? String(status.current_category).replace(/_/g, " ")
    : null;

  return (
    <DashboardLayout>
      <DashboardNavbar />
      <MDBox py={3}>
        <MDBox display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1} mb={2}>
          <MDBox>
            <MDTypography variant="h4" fontWeight="bold">
              Security Evaluation
            </MDTypography>
            <MDTypography variant="button" color="text">
              OWASP-aligned defensive audit of the local EFL IndexDB API (admin only).
            </MDTypography>
          </MDBox>
          <MDBox display="flex" gap={1}>
            <MDButton
              variant="gradient"
              color="primary"
              onClick={handleRun}
              disabled={!!status.running}
            >
              {status.running ? "Audit running…" : "Run Security Audit"}
            </MDButton>
            <MDButton
              variant="outlined"
              color="dark"
              onClick={handleExport}
              disabled={exporting || !report}
            >
              {exporting ? "Exporting…" : "Export Report"}
            </MDButton>
          </MDBox>
        </MDBox>

        {error && (
          <MDBox mb={2}>
            <MDAlert color="error">{error}</MDAlert>
          </MDBox>
        )}

        {status.running && (
          <MDBox mb={2} display="flex" alignItems="center" gap={1.5}>
            <CircularProgress size={22} />
            <MDTypography variant="button" color="text">
              Running category: <strong>{categoryLabel || "…"}</strong>
            </MDTypography>
          </MDBox>
        )}

        {status.error && !status.running && (
          <MDBox mb={2}>
            <MDAlert color="warning">Last audit error: {status.error}</MDAlert>
          </MDBox>
        )}

        {loading ? (
          <MDBox py={4} display="flex" justifyContent="center">
            <CircularProgress />
          </MDBox>
        ) : (
          <>
            <MDBox display="flex" flexWrap="wrap" gap={2} mb={3}>
              <SummaryCard title="Total Tests" value={summary.total_tests} />
              <SummaryCard title="Passed" value={summary.passed} color="success" />
              <SummaryCard title="Failed" value={summary.failed} color="error" />
              <SummaryCard title="Warnings" value={summary.warnings} color="warning" />
            </MDBox>

            <Card sx={{ p: 2, mb: 3 }}>
              <MDTypography variant="h6" fontWeight="medium" mb={1}>
                OWASP Top 10 Assessment
              </MDTypography>
              {!owasp.length ? (
                <MDTypography variant="caption" color="text">
                  No OWASP results yet. Run a security audit to populate this table.
                </MDTypography>
              ) : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>OWASP ID</TableCell>
                        <TableCell>Category</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Findings</TableCell>
                        <TableCell>Recommendations</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {owasp.map((row) => (
                        <TableRow key={row.owasp_id}>
                          <TableCell>{row.owasp_id}</TableCell>
                          <TableCell>{row.owasp_name}</TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              label={row.status}
                              color={STATUS_COLOR[row.status] || "default"}
                            />
                          </TableCell>
                          <TableCell>
                            <MDTypography variant="caption" color="text">
                              {(row.findings || []).slice(0, 2).join("; ") || "—"}
                            </MDTypography>
                          </TableCell>
                          <TableCell>
                            <MDTypography variant="caption" color="text">
                              {(row.recommendations || []).slice(0, 2).join("; ") || "—"}
                            </MDTypography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Card>

            <MDTypography variant="h6" fontWeight="medium" mb={1}>
              Test categories
            </MDTypography>
            {CATEGORIES.map((cat) => (
              <CategorySection
                key={cat.key}
                title={cat.label}
                items={report ? report[cat.key] : []}
              />
            ))}

            {report?.audit_date && (
              <MDTypography variant="caption" color="text" mt={2} display="block">
                Last audit: {report.audit_date} · target {report.target}
              </MDTypography>
            )}
          </>
        )}
      </MDBox>
      <Footer />
    </DashboardLayout>
  );
}

export default SecurityEvaluation;
